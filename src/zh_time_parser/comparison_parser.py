"""
同比 / 环比解析：把「本月同比」「Q2环比」这类表达解析成**两个**区间。

设计要点
────────
1. 本模块**不复制**季度/半年/月份的日历计算逻辑。它先从原句里剥掉
   「同比/环比/同期」这类比较词，把剩余文本交给既有的
   extract_date_range_v2() 得出 current 区间，再按粒度做日历平移
   得出 comparison 区间。

2. 平移一律走日历算术（年/月加减 + 各月真实天数），
   **不使用**固定 365 天做同比，也**不使用**固定 30 天做月环比。

3. 粒度由 current.granularity / range_type 推断：
   half_year → 半年、quarter → 季度、year → 年、其余按月/自定义天段处理。

4. 无法确定比较语义时返回 None，不抛异常、不编造区间。
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from zh_time_parser.models import (
    COMPARISON_PREVIOUS_PERIOD,
    COMPARISON_YOY,
    ComparisonRange,
    DateRange,
)
from zh_time_parser.normalization import _days_in_month, _fmt

# ─────────────────────────────────────────────────────────
#  比较词识别
# ─────────────────────────────────────────────────────────
# 同比：与去年同一日历位置比。「去年同期/上年同期/同期」都归此类。
# 边界收紧：用负向前瞻排除「同比例」「同期生/同期刊/同期声」等普通词。
_YOY_PAT = r'同比(?!例)|去年同期|上年同期|较去年同期|比去年同期|同期(?!生|刊|声)'
# 环比：与紧邻的前一个同粒度周期比。
# 只保留明确触发词（环比 / 较上期 / 比上期），并排除「环比例」
# （「环比较」不含连续的「环比」子串，天然不命中）。
# 注意：不再包含单独的「环」——否则「环境/环节/循环/环岛」会被误判为环比。
_MOM_PAT = r'环比(?!例)|较上期|比上期'

# 需要从原句中剥离的比较词残留（否则会干扰基础日期解析，
# 例如「今年同比去年」若不剥离，会被年份范围解析成 今年→去年）。
_STRIP_PAT = re.compile(
    r'同比去年同期|同比去年|较去年同期|比去年同期|去年同期|上年同期|'
    r'同比(?!例)|环比(?!例)|较上期|比上期|同期(?!生|刊|声)|'
    r'相比|对比|比较'
)


def _detect_comparison_type(msg: str) -> Optional[str]:
    """
    判断消息表达的是同比还是环比。都没有则返回 None。

    同时包含「同比」与「环比」时返回 None——单次调用只支持一种比较类型，
    同时请求两种会丢失意图，不应擅自选一个。
    """
    has_yoy = re.search(_YOY_PAT, msg) is not None
    has_mom = re.search(_MOM_PAT, msg) is not None
    if has_yoy and has_mom:
        return None
    if has_yoy:
        return COMPARISON_YOY
    if has_mom:
        return COMPARISON_PREVIOUS_PERIOD
    return None


def _strip_comparison_words(msg: str) -> str:
    """
    去掉比较词，只留下时间短语本身。

    例："上个月同比" → "上个月"；"今年同比去年" → "今年"；"Q2环比" → "Q2"。
    这一步是必要的：残留的「去年」「同期」会让基础解析器给出错误的 current。
    """
    return _STRIP_PAT.sub('', msg).strip()


# ─────────────────────────────────────────────────────────
#  独立默认表达：严格首尾锚定白名单
# ─────────────────────────────────────────────────────────
# 默认比较周期（「同比」「环比」单独出现等）**仅**在原始输入精确匹配以下形态时采用，
# 不再依赖「剩余文本是否含时间词」这类过宽推断。「同期生/同期刊/同期声/同比例/
# 环比例/环比较/前阵子同比」等都因无法完整首尾匹配而被拒绝，回退到 None。
#
# 允许的核心表达：同比 / 环比 / 同期 / 去年同期 / 上年同期
# 允许前缀（可选，最多一个）：看 / 看一下 / 查询 / 查一下 / 帮我看 / 帮我查 / 请看 / 请查询
# 允许后缀（可选，最多一个）：是多少 / 情况 / 怎么样 / 如何 / 数据 / 结果 / 指标 / 数值
# 允许结尾标点：？?。！
# 任意无关文本或额外字都会破坏首尾锚定 → 不命中。
_STANDALONE_DEFAULT_PAT = re.compile(
    r'^'
    r'\s*'
    r'(?:看一下|请查询|查询|查一下|帮我看|帮我查|请看|看)?'
    r'\s*'
    r'(?:去年同期|上年同期|同比|环比|同期)(?:率)?'
    r'\s*'
    r'(?:是多少|情况|怎么样|如何|数据|结果|指标|数值)?'
    r'\s*'
    r'[？?。！!]*'
    r'\s*'
    r'$'
)


def _is_standalone_default(msg: str) -> bool:
    """
    判断原句是否为「独立默认表达」——即只带有限前缀/后缀/标点的单独同比/环比/同期，
    本就是独立的默认周期请求。

    只有这类表达才允许在无法解析出明确本期时回退到默认周期；
    只要原句首尾之外还夹带任何其它文本（如「前阵子」「第五季度」「H3」
    「同期生」「同比例」「环比例」），都不匹配白名单，必须返回 None，
    不得编造默认周期。
    """
    return bool(_STANDALONE_DEFAULT_PAT.match(msg))


# ─────────────────────────────────────────────────────────
#  日历平移工具（全部基于真实日历，无固定天数）
# ─────────────────────────────────────────────────────────

def _shift_year(date_str: str, years: int) -> str:
    """
    把 'YYYY-MM-DD' 平移整数年，保持月/日不变。

    闰年安全：上一年度没有 2 月 29 日时回退到 2 月 28 日。
    """
    d = datetime.strptime(date_str, '%Y-%m-%d')
    y = d.year + years
    day = min(d.day, _days_in_month(y, d.month))
    return _fmt(datetime(y, d.month, day))


def _add_months(year: int, month: int, delta: int) -> Tuple[int, int]:
    """(year, month) 加减若干月，返回规范化后的 (year, month)。"""
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, idx % 12 + 1


def _is_full_month_span(start: datetime, end: datetime) -> bool:
    """判断区间是否恰好覆盖一个完整自然月。"""
    return (start.day == 1
            and start.year == end.year
            and start.month == end.month
            and end.day == _days_in_month(end.year, end.month))


def _shift_month_block(start: datetime, end: datetime, delta: int) -> Tuple[str, str]:
    """
    把「月」粒度区间平移 delta 个月。

    - 完整自然月 → 平移后仍取目标月的完整范围（各月真实天数，
      所以 3 月 31 天平移到 2 月会正确变成 28/29 天）。
    - 进行中的月（如 8-01~8-09）→ 保持「相同已过天数」，
      平移后取目标月 1 号 ~ 同一天号（超出目标月天数时截到月末）。
    """
    y, m = _add_months(start.year, start.month, delta)
    if _is_full_month_span(start, end):
        return _fmt(datetime(y, m, 1)), _fmt(datetime(y, m, _days_in_month(y, m)))
    last = _days_in_month(y, m)
    new_start = datetime(y, m, min(start.day, last))
    new_end = datetime(y, m, min(end.day, last))
    return _fmt(new_start), _fmt(new_end)


def _shift_quarter(start: datetime, end: datetime, delta_q: int) -> Tuple[str, str]:
    """把季度区间平移 delta_q 个季度（等价于平移 3*delta_q 个月的完整块）。"""
    y, m = _add_months(start.year, start.month, delta_q * 3)
    end_y, end_m = _add_months(y, m, 2)
    return _fmt(datetime(y, m, 1)), _fmt(datetime(end_y, end_m, _days_in_month(end_y, end_m)))


def _shift_half_year(start: datetime, delta_h: int) -> Tuple[str, str]:
    """把半年区间平移 delta_h 个半年（H1↔H2，跨年自动进位）。"""
    h = 1 if start.month <= 6 else 2
    idx = start.year * 2 + (h - 1) + delta_h
    y, h_new = idx // 2, idx % 2 + 1
    if h_new == 1:
        return f'{y}-01-01', f'{y}-06-30'
    return f'{y}-07-01', f'{y}-12-31'


# ─────────────────────────────────────────────────────────
#  粒度判定
# ─────────────────────────────────────────────────────────

def _infer_granularity(dr: DateRange) -> str:
    """
    推断 current 区间的周期粒度，用于决定环比该往前挪多少。
    返回 'half_year' / 'quarter' / 'year' / 'month' / 'day'。
    """
    if dr.granularity == 'half_year':
        return 'half_year'
    if dr.granularity == 'quarter' or dr.range_type == 'quarter':
        return 'quarter'
    if dr.granularity == 'year':
        return 'year'
    if dr.granularity == 'month':
        return 'month'
    return 'day'


def _default_current(today: datetime, comparison_type: str) -> Tuple[DateRange, str]:
    """
    「同比」「环比」单独出现时的默认本期区间。

    - 同比默认：今年 1-1 ~ 今天（年初至今），与去年同期比。
    - 环比默认：本月 1 号 ~ 今天，与上月相同已过天数比。
    """
    if comparison_type == COMPARISON_YOY:
        dr = DateRange(f'{today.year}-01-01', _fmt(today), range_type='range',
                       granularity='year', original_text='今年至今',
                       label='今年至今', is_relative=True)
        return dr, 'year'
    dr = DateRange(_fmt(today.replace(day=1)), _fmt(today), range_type='range',
                   granularity='month', original_text='本月至今',
                   label='本月至今', is_relative=True)
    return dr, 'month'


# ─────────────────────────────────────────────────────────
#  对比期计算
# ─────────────────────────────────────────────────────────

def _build_comparison(current: DateRange, gran: str,
                      comparison_type: str) -> Optional[DateRange]:
    """
    根据本期区间与粒度算出对比期区间。无法计算时返回 None。
    """
    if current.start is None or current.end is None:
        return None
    start = datetime.strptime(current.start, '%Y-%m-%d')
    end = datetime.strptime(current.end, '%Y-%m-%d')

    if comparison_type == COMPARISON_YOY:
        # 同比：整体平移一年，日历位置不变（闰年由 _shift_year 处理）
        s, e = _shift_year(current.start, -1), _shift_year(current.end, -1)
        label_suffix = '同比'
    else:
        # 环比：按粒度往前挪一个完整周期
        if gran == 'half_year':
            s, e = _shift_half_year(start, -1)
        elif gran == 'quarter':
            s, e = _shift_quarter(start, end, -1)
        elif gran == 'year':
            s, e = _shift_year(current.start, -1), _shift_year(current.end, -1)
        elif gran == 'month':
            s, e = _shift_month_block(start, end, -1)
        else:
            # 自定义天段（如「最近7天」）：往前挪等长的一段，
            # 用真实天数计算，不使用固定 30/365。
            span = (end - start).days + 1
            new_end = start - timedelta(days=1)
            new_start = new_end - timedelta(days=span - 1)
            s, e = _fmt(new_start), _fmt(new_end)
        label_suffix = '环比'

    return DateRange(s, e, range_type='range', granularity=current.granularity,
                     original_text=current.original_text,
                     label=f'{current.label}{label_suffix}期',
                     is_relative=current.is_relative)


# ─────────────────────────────────────────────────────────
#  公开入口
# ─────────────────────────────────────────────────────────

def extract_comparison_range(user_message: str, today: Optional[datetime] = None,
                             week_start: str = 'monday') -> Optional[ComparisonRange]:
    """
    解析同比 / 环比表达，返回 ComparisonRange（本期 + 对比期）。

    同比（comparison_type='yoy'）
        当前区间与**上一年度相同日历位置**的区间比较。
        例：本月同比（today=2026-08-09）
            current    2026-08-01 ~ 2026-08-09
            comparison 2025-08-01 ~ 2025-08-09

    环比（comparison_type='previous_period'）
        与**紧邻的同粒度前一周期**比较。进行中的周期使用相同已过天数，
        避免拿 9 天和完整上月比。
        例：本月环比（today=2026-08-09）
            current    2026-08-01 ~ 2026-08-09
            comparison 2026-07-01 ~ 2026-07-09

    无法确定比较语义（没有比较词，或时间短语无法解析）时返回 None，
    不抛异常、不编造区间。
    """
    # 延迟导入：date_parser 顶层不依赖本模块，这里反向引用以复用全部解析能力，
    # 放在函数内可避免 import 期循环依赖。
    from zh_time_parser.date_parser import extract_date_range_v2

    if user_message is None:
        return None
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str 或 None')
    if week_start not in ('monday', 'sunday'):
        raise ValueError("week_start 必须是 'monday' 或 'sunday'")
    if today is None:
        today = datetime.now()

    msg = user_message.strip()
    if not msg:
        return None

    comparison_type = _detect_comparison_type(msg)
    if comparison_type is None:
        return None

    # 剥离比较词，用剩余文本确定本期区间
    stripped = _strip_comparison_words(msg)
    current: Optional[DateRange] = None
    if stripped:
        parsed = extract_date_range_v2(stripped, today=today, week_start=week_start)
        if parsed and parsed.recognition_status == 'ok':
            current = parsed

    if current is None:
        # 剥离后没有任何有效时间区间。
        # 只有在「原式本就是独立默认表达」（同比/环比/去年同期/同期单独出现，
        # 可带少量无语义标点或询问后缀）时才回退到默认周期；
        # 若剥离后仍存在实质性时间文本但无法解析（如「前阵子同比」「H3环比」、
        # 「第五季度同比」），必须返回 None，不编造默认周期。
        if not _is_standalone_default(msg):
            return None
        current, gran = _default_current(today, comparison_type)
    else:
        gran = _infer_granularity(current)

    comparison = _build_comparison(current, gran, comparison_type)
    if comparison is None or not comparison:
        return None

    kind = '同比' if comparison_type == COMPARISON_YOY else '环比'
    return ComparisonRange(
        current=current,
        comparison=comparison,
        comparison_type=comparison_type,
        original_text=msg,
        label=f'{current.label} {kind} {comparison.start}~{comparison.end}',
        confidence=current.confidence,
    )
