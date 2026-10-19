"""年份相关表达：今年/去年、年初至今、上半年/下半年、跨年范围。"""

import re
from datetime import datetime
from typing import Optional, Tuple

from zh_time_parser.models import DateRange
from zh_time_parser.normalization import (
    _fmt,
    _is_valid_year,
)


def _half_year_range(year: int, h: int) -> Tuple[str, str]:
    """H1 = 1-1 ~ 6-30，H2 = 7-1 ~ 12-31。返回 ('YYYY-MM-DD', 'YYYY-MM-DD')。"""
    if h == 1:
        return f'{year}-01-01', f'{year}-06-30'
    return f'{year}-07-01', f'{year}-12-31'


# H1/H2 词形。整体分成两支，保证「年份前缀」与「孤立字母 H」互不干扰：
#
#   A. 带年份：2025H1 / 2025 H1 / 2025年H1 / 2025年上半年
#      年份自身要求 (?<!\d) 防止从 "12025" 中间截取。
#   B. 不带年份：H1 / h1 / 上半年
#      字母式要求前面**不是**字母或数字，避免 "ABH1"、"12H1" 这类误识别；
#      后面不能紧跟数字，避免 "H12" 被当成 H1。
#
# 这样 "2025H1" 走 A 支（H 前的 5 属于被消费的年份），而裸文本里的
# "Hello"、孤立 "H"、"H0/H3/H9" 都不会命中任何一支。
_HX_CORE = r'(?:[Hh]([12])(?!\d)|(上|下)半年)'
_HX_WITH_YEAR = r'(?<!\d)(\d{4})\s*年?\s*' + _HX_CORE
_HX_NO_YEAR = r'(?:(?<![A-Za-z\d])[Hh]([12])(?!\d)|(上|下)半年)'
# 组序：1=年份 2=字母半年(带年) 3=中文半年(带年) 4=字母半年(无年) 5=中文半年(无年)
_HX_TOKEN = r'(?:' + _HX_WITH_YEAR + r'|' + _HX_NO_YEAR + r')'
_HX_GROUPS = 5  # _HX_TOKEN 内部捕获组数量，供范围模式计算右侧偏移


def _resolve_half_year_token(text: str, today: datetime) -> Optional[Tuple[int, int, bool]]:
    """
    把单个「半年 token」解析成 (year, half, has_explicit_year)。

    支持：H1/h1/H2/h2、上半年/下半年、2025H1、2025 H1、2025年H1、2025年上半年。
    返回 None 表示不是半年 token。
    """
    m = re.fullmatch(_HX_TOKEN, text.strip())
    if not m:
        return None
    return _half_year_from_groups(m.groups(), today)


def _half_year_from_groups(groups: Tuple[Optional[str], ...],
                           today: datetime) -> Optional[Tuple[int, int, bool]]:
    """
    从 _HX_TOKEN 的 5 个捕获组解出 (year, half, has_explicit_year)。
    groups 顺序：年份、字母半年(带年)、中文半年(带年)、字母半年(无年)、中文半年(无年)。
    """
    year_raw, letter_y, cn_y, letter_n, cn_n = groups[:_HX_GROUPS]
    letter_half = letter_y or letter_n
    cn_half = cn_y or cn_n
    if letter_half:
        h = int(letter_half)
    elif cn_half:
        h = 1 if cn_half == '上' else 2
    else:
        return None
    if year_raw:
        y = int(year_raw)
        if not _is_valid_year(y):
            return None
        return y, h, True
    return today.year, h, False


def _parse_half_year_hx(msg: str, today: datetime) -> Optional[DateRange]:
    """
    H1/H2 自然半年（含中文「上半年/下半年」的等价写法与半年范围）。

    - H1 / h1 / 2025H1 / 2025 H1 / 2025年H1  → 上半年
    - H2 / h2 / 2025H2 / 2025 H2 / 2025年H2  → 下半年
    - H1到H2 / H1至H2 / H1~H2                → 当年全年
    - 2025H1到2025H2                          → 该年全年

    刻意**不**支持跨年份的 2025H2到2026H1（起止顺序校验与测试尚未补全）。

    注意：本解析器只处理「字母式 H1/H2」以及「带年份的中文半年」。
    不带年份的「上半年/下半年」仍交给 _parse_half_year 处理，
    以完整保留其原有行为（含「上半年至今」等变体）。
    """
    # ── 1) 半年范围：H1到H2 / 2025H1至2025H2 ──────────────────
    # 必须先于单个 H1 匹配，否则 "H1到H2" 会被前半段截获。
    range_pat = _HX_TOKEN + r'\s*(?:到|至|~|-)\s*' + _HX_TOKEN
    m = re.search(range_pat, msg)
    if m:
        g = m.groups()
        left = _half_year_from_groups(g[:_HX_GROUPS], today)
        right = _half_year_from_groups(g[_HX_GROUPS:2 * _HX_GROUPS], today)
        if left and right:
            ly, lh, l_explicit = left
            ry, rh, r_explicit = right
            # 暂不支持跨年份半年范围：两端年份必须一致
            if ly == ry and lh < rh:
                s, _ = _half_year_range(ly, lh)
                _, e = _half_year_range(ry, rh)
                explicit = l_explicit or r_explicit
                return DateRange(s, e, range_type='range', granularity='half_year',
                                 original_text=m.group(0),
                                 label=f'{ly}H{lh}~{ry}H{rh}',
                                 is_relative=not explicit)
            return None

    # ── 2) 单个半年：H1 / 2025H2 / 2025年上半年 ───────────────
    # 中文「上半年/下半年」只有在**带年份**时才由本解析器接管；
    # 不带年份的走原 _parse_half_year，保持旧行为不变。
    for m in re.finditer(_HX_TOKEN, msg):
        g = m.groups()
        year_raw, cn_no_year = g[0], g[4]
        if cn_no_year and not year_raw:
            continue  # 裸「上半年/下半年」→ 交给 _parse_half_year，保持旧行为
        res = _half_year_from_groups(g, today)
        if not res:
            continue
        y, h, explicit = res
        s, e = _half_year_range(y, h)
        return DateRange(s, e, range_type='range', granularity='half_year',
                         original_text=m.group(0), label=f'{y}H{h}',
                         is_relative=not explicit)

    return None


def _parse_half_year(msg: str, today: datetime) -> Optional[DateRange]:
    """
    半年/全年 范围：
    - 上半年至今 / 上半年到今天
    - 下半年至今
    - 上半年 / 下半年（指整段）
    - 全年至今 / 今年至今
    """
    this_year = today.year
    # 上半年
    if re.search(r'上半年', msg):
        s = datetime(this_year, 1, 1)
        e_full = datetime(this_year, 6, 30)
        if re.search(r'(至今|到今天|到今)', msg):
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='month',
                             original_text='上半年至今', label='上半年至今', is_relative=True)
        return DateRange(_fmt(s), _fmt(e_full), range_type='range', granularity='month',
                         original_text='上半年', label=f'{this_year}上半年',
                         is_relative=True)
    # 下半年
    if re.search(r'下半年', msg):
        s = datetime(this_year, 7, 1)
        e_full = datetime(this_year, 12, 31)
        if re.search(r'(至今|到今天|到今)', msg):
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='month',
                             original_text='下半年至今', label='下半年至今', is_relative=True)
        return DateRange(_fmt(s), _fmt(e_full), range_type='range', granularity='month',
                         original_text='下半年', label=f'{this_year}下半年',
                         is_relative=True)
    # 全年至今 / 全年 / 今年至今
    if re.search(r'(今年|全年|本年).*?(至今|到今天|到今)', msg) or re.search(r'全年至今', msg):
        s = datetime(this_year, 1, 1)
        return DateRange(_fmt(s), _fmt(today), range_type='ytd', granularity='year',
                         original_text='全年至今', label='全年至今', is_relative=True)
    return None


def _resolve_year_token(token: str, today: datetime) -> Optional[Tuple[int, str]]:
    """
    把单个'年 token'解析为 (year, label)。
    支持：今年/本年、去年/上年、前年、明年/来年、2025年、25年、2025
    """
    t = token.strip()
    if re.fullmatch(r'(今年|本年|这一年|这年)', t):
        return today.year, '今年'
    if re.fullmatch(r'(去年|上年|上一年)', t):
        return today.year - 1, '去年'
    if re.fullmatch(r'前年', t):
        return today.year - 2, '前年'
    if re.fullmatch(r'(明年|来年|下一年)', t):
        return today.year + 1, '明年'
    m = re.fullmatch(r'(\d{4})年?', t)
    if m:
        y = int(m.group(1))
        if _is_valid_year(y):
            return y, f'{y}年'
    m = re.fullmatch(r'(\d{2})年', t)
    if m:
        y = 2000 + int(m.group(1))
        if _is_valid_year(y):
            return y, f'{y}年'
    return None


def _parse_year_range(msg: str, today: datetime) -> Optional[DateRange]:
    """
    跨年范围：
    - 去年到今年 / 前年到今年 / 去年至今年
    - 2025年到2026年 / 2025到2026年 / 2024-2026年
    - 25年到26年
    """
    # 优先匹配带年份数字的格式
    cross_patterns = [
        # 2025年 到/至/~ 2026年
        r'((?:\d{4})\s*年?)\s*(?:到|至|~|-)\s*((?:\d{4})\s*年?)',
        # 25年 到/至/~ 26年
        r'((?:\d{2})\s*年)\s*(?:到|至|~|-)\s*((?:\d{2})\s*年)',
        # 中文相对年（前年/去年/今年/明年）之间
        r'(前年|去年|上年|上一年|今年|本年|明年|来年|下一年)\s*(?:到|至|~|-)\s*'
        r'(前年|去年|上年|上一年|今年|本年|明年|来年|下一年)',
        # 数字年 到 中文相对年（如 2025年到今年）
        r'((?:\d{4})\s*年?|(?:\d{2})\s*年)\s*(?:到|至|~|-)\s*'
        r'(前年|去年|上年|上一年|今年|本年|明年|来年|下一年)',
        # 中文相对年 到 数字年（如 去年到2026年）
        r'(前年|去年|上年|上一年|今年|本年|明年|来年|下一年)\s*(?:到|至|~|-)\s*'
        r'((?:\d{4})\s*年?|(?:\d{2})\s*年)',
    ]
    for pat in cross_patterns:
        m = re.search(pat, msg)
        if m:
            left = _resolve_year_token(m.group(1), today)
            right = _resolve_year_token(m.group(2), today)
            if left and right:
                ly, ll = left
                ry, rl = right
                if ly > ry:
                    return None
                # 终止年的端点：今年→今天，其它年→12-31
                if rl == '今年':
                    end_str = _fmt(today)
                else:
                    end_str = f'{ry}-12-31'
                return DateRange(f'{ly}-01-01', end_str, range_type='range',
                                 granularity='year', original_text=m.group(0),
                                 label=f'{ll}到{rl}',
                                 is_relative=(ll in ('今年', '去年', '前年', '明年')
                                              or rl in ('今年', '去年', '前年', '明年')))
    return None


def _parse_year(msg: str, today: datetime) -> Optional[DateRange]:
    """
    今年/本年/这一年 → 今年 1-1 ~ 今天
    去年/上年 → 去年 1-1 ~ 去年 12-31
    前年 → 前年 1-1 ~ 前年 12-31
    明年/来年 → 明年 1-1 ~ 明年 12-31
    年初/年初至今/YTD → 今年 1-1 ~ 今天
    年末 → 今年 1-1 ~ 12-31（注意年末是"到年底"）
    X年 / XX年
    """
    # 今年/本年/这一年
    if re.search(r'(今年|本年|这一年|这年)', msg):
        s = datetime(today.year, 1, 1)
        return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='year',
                         original_text='今年', label='今年', is_relative=True)

    # 去年/上年
    if re.search(r'(去年|上年|上一年)', msg):
        y = today.year - 1
        return DateRange(f'{y}-01-01', f'{y}-12-31', range_type='range', granularity='year',
                         original_text='去年', label='去年', is_relative=True)

    # 前年
    if re.search(r'(前年)', msg):
        y = today.year - 2
        return DateRange(f'{y}-01-01', f'{y}-12-31', range_type='range', granularity='year',
                         original_text='前年', label='前年', is_relative=True)

    # 明年/来年
    if re.search(r'(明年|来年|下一年)', msg):
        y = today.year + 1
        return DateRange(f'{y}-01-01', f'{y}-12-31', range_type='range', granularity='year',
                         original_text='明年', label='明年', is_relative=True)

    # 年初/年初至今/YTD
    if re.search(r'年初(?:至今)?|YTD|ytd|今年截至(?:现在)?', msg):
        s = datetime(today.year, 1, 1)
        return DateRange(_fmt(s), _fmt(today), range_type='ytd', granularity='year',
                         original_text='年初至今', label='年初至今', is_relative=True)

    # X 年至今 / X 年到现在 / X 年到今天（先匹配 4 位再匹配 2 位）
    m = re.search(r'(?<!\d)(\d{4})年(?:至今|到现在|到今天|到目前|起到今天)', msg)
    if m:
        y = int(m.group(1))
        if _is_valid_year(y):
            return DateRange(f'{y}-01-01', _fmt(today), range_type='ytd', granularity='year',
                             original_text=m.group(0), label=f'{y}年至今', is_relative=True)
    m = re.search(r'(?<!\d)(\d{2})年(?:至今|到现在|到今天|到目前|起到今天)', msg)
    if m:
        y = 2000 + int(m.group(1))
        if _is_valid_year(y):
            return DateRange(f'{y}-01-01', _fmt(today), range_type='ytd', granularity='year',
                             original_text=m.group(0), label=f'{y}年至今', is_relative=True)

    # 年末/年底（注意：年末一般指"到年底"的范围）
    if re.search(r'年末|年底', msg):
        s = datetime(today.year, 1, 1)
        return DateRange(_fmt(s), f'{today.year}-12-31', range_type='range', granularity='year',
                         original_text='年末', label='年末', is_relative=True)

    # X年（4 位数） / XX年（2 位数）
    m = re.search(r'(?<!\d)(\d{4})年(?![\d月])', msg)
    if m:
        y = int(m.group(1))
        if _is_valid_year(y):
            return DateRange(f'{y}-01-01', f'{y}-12-31', range_type='range', granularity='year',
                             original_text=m.group(0), label=f'{y}年')

    m = re.search(r'(?<!\d)(\d{2})年(?![\d月])', msg)
    if m:
        y = 2000 + int(m.group(1))
        if _is_valid_year(y):
            return DateRange(f'{y}-01-01', f'{y}-12-31', range_type='range', granularity='year',
                             original_text=m.group(0), label=f'{y}年')

    return None
