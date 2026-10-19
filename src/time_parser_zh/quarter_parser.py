"""季度相关表达：本季度/上季度、Q1、跨季度范围、季度内段。"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from time_parser_zh.models import DateRange
from time_parser_zh.normalization import (
    _fmt,
    _is_valid_year,
)


def _parse_quarter(msg: str, today: datetime) -> Optional[DateRange]:
    """
    季度：
    - Q1/Q2/Q3/Q4 / q1/.../q4
    - 2026Q1 / 2026年Q1
    - 本季度/这季度/这季
    - 上季度/上季/上上季度
    - 下季度/下季
    - 第一季度/第二季度/...
    - 季度至今/Q1至今（本季度第一天到今天）
    """
    # 2026Q1
    m = re.search(r'(\d{4})年?Q([1-4])(?:至今)?', msg, re.IGNORECASE)
    if m:
        year, q = int(m.group(1)), int(m.group(2))
        if _is_valid_year(year):
            s, e = _quarter_range(year, q)
            if '至今' in m.group(0):
                e = _fmt(today)
            return DateRange(s, e, range_type='quarter', granularity='quarter',
                             original_text=m.group(0), label=f"{year}Q{q}",
                             confidence=0.95 if '至今' not in m.group(0) else 0.85)

    # Q1至今（无年份 → 本年）
    m = re.search(r'Q([1-4])(?:至今)?', msg, re.IGNORECASE)
    if m:
        q = int(m.group(1))
        s, e = _quarter_range(today.year, q)
        if '至今' in m.group(0):
            e = _fmt(today)
        return DateRange(s, e, range_type='quarter', granularity='quarter',
                         original_text=m.group(0), label=f"Q{q}（本年）", is_relative=True)

    # 第一季度/第二季度/.../第四季度
    m = re.search(r'第([一二三四1-4])季度(?:至今)?', msg)
    if m:
        q = '一二三四'.index(m.group(1)) + 1 if not m.group(1).isdigit() else int(m.group(1))
        s, e = _quarter_range(today.year, q)
        if '至今' in m.group(0):
            e = _fmt(today)
        return DateRange(s, e, range_type='quarter', granularity='quarter',
                         original_text=m.group(0), label=f"Q{q}", is_relative=True)

    # 本季度/这季度/这个季度/这季
    if re.search(r'(本|这|当前)(?:个)?季度', msg) or re.search(r'(本|这|当前)季(?![一二三四1-4度])', msg):
        q = (today.month - 1) // 3 + 1
        s, e = _quarter_range(today.year, q)
        return DateRange(s, e, range_type='quarter', granularity='quarter',
                         original_text='本季度', label=f"Q{q}（本季度）", is_relative=True)

    # 上季度/上季/上个季度
    if re.search(r'上季度|上季|上个季度', msg):
        q = (today.month - 1) // 3  # 0 表示上个季度是去年的 Q4
        year = today.year
        if q == 0:
            q = 4
            year -= 1
        s, e = _quarter_range(year, q)
        return DateRange(s, e, range_type='quarter', granularity='quarter',
                         original_text='上季度', label=f"Q{q}（上季度）", is_relative=True)

    # 下季度/下季
    if re.search(r'下季度|下季|下个季度', msg):
        q = (today.month - 1) // 3 + 2
        year = today.year
        if q > 4:
            q -= 4
            year += 1
        s, e = _quarter_range(year, q)
        return DateRange(s, e, range_type='quarter', granularity='quarter',
                         original_text='下季度', label=f"Q{q}（下季度）", is_relative=True)

    # 去年同期/上年同期 → yoy，调用方自行处理
    if re.search(r'(去年|上年)同期', msg):
        return DateRange(None, None, range_type='yoy', label='去年同期',
                         is_relative=True, confidence=0.0)

    return None


def _quarter_range(year: int, q: int) -> Tuple[str, str]:
    """Q1=1-3月，Q2=4-6月，Q3=7-9月，Q4=10-12月"""
    start_month = (q - 1) * 3 + 1
    end_month = start_month + 2
    s = datetime(year, start_month, 1)
    if end_month == 12:
        e = datetime(year, 12, 31)
    else:
        e = datetime(year, end_month + 1, 1) - timedelta(days=1)
    return _fmt(s), _fmt(e)


def _resolve_quarter_token(token: str, today: datetime) -> Optional[Tuple[int, int, str]]:
    """
    把单个季度 token 解析成 (year, quarter, label)。
    支持：Q1/Q2/Q3/Q4、2026Q1、2026年Q1、2026年第一季度、
          本季度/这季度/当前季度、上季度/上季、下季度/下季、
          上上季度、第一季度/第二季度/.../第四季度
    返回 None 表示不是季度 token。
    """
    t = token.strip()
    if not t:
        return None

    # 1) 2026Q1 / 2026年Q1
    m = re.fullmatch(r'(\d{4})\s*年?\s*Q([1-4])', t, re.IGNORECASE)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        if _is_valid_year(y):
            return y, q, f"{y}Q{q}"

    # 2) 2026年第一季度
    m = re.fullmatch(r'(\d{4})\s*年\s*第([一二三四1-4])\s*季度', t)
    if m:
        y = int(m.group(1))
        q_raw = m.group(2)
        q = '一二三四'.index(q_raw) + 1 if not q_raw.isdigit() else int(q_raw)
        if _is_valid_year(y):
            return y, q, f"{y}Q{q}"

    # 3) Q1~Q4
    m = re.fullmatch(r'Q([1-4])', t, re.IGNORECASE)
    if m:
        return today.year, int(m.group(1)), f"Q{m.group(1)}（本年）"

    # 4) 第一季度~第四季度 / 一季度~四季度
    m = re.fullmatch(r'第?([一二三四1-4])\s*季度', t)
    if m:
        q_raw = m.group(1)
        q = '一二三四'.index(q_raw) + 1 if not q_raw.isdigit() else int(q_raw)
        return today.year, q, f"Q{q}（本年）"

    # 5) 本季度/这季度/当前季度
    if re.fullmatch(r'(本|这|当前)季度', t):
        q = (today.month - 1) // 3 + 1
        return today.year, q, f"{today.year}Q{q}（本季度）"

    # 6) 上季度/上季/上个季度
    if re.fullmatch(r'上(个?季度|季度|季)', t):
        q = (today.month - 1) // 3
        y = today.year
        if q == 0:
            q, y = 4, y - 1
        return y, q, f"{y}Q{q}（上季度）"

    # 7) 上上季度
    if re.fullmatch(r'上上(个?季度|季度|季)', t):
        q = (today.month - 1) // 3
        y = today.year
        # 倒退 2 个季度
        for _ in range(1):
            q -= 1
            if q == 0:
                q, y = 4, y - 1
        return y, q, f"{y}Q{q}（上上季度）"

    # 8) 下季度/下季/下个季度
    if re.fullmatch(r'下(个?季度|季度|季)', t):
        q = (today.month - 1) // 3 + 2
        y = today.year
        if q > 4:
            q, y = q - 4, y + 1
        return y, q, f"{y}Q{q}（下季度）"

    return None


def _parse_quarter_range(msg: str, today: datetime) -> Optional[DateRange]:
    """
    跨季度范围 / 季度+至今：
    - Q1到Q2 / Q1至Q2 / Q1~Q2
    - 2026Q1到2026Q3 / 2026Q1至2026Q3
    - 一季度到二季度 / 第一季度至第三季度
    - 上季度到本季度 / 上季度至本季度
    - Q1至今 / Q1到今天（也支持 2026Q1至今、上一季度至今）
    """
    # 季度+至今（先匹配，否则后面的"到Q2"会先吃掉）
    ytd_patterns = [
        # 2026Q1至今 / 2026年Q1至今
        r'(\d{4}\s*年?\s*Q[1-4])\s*(?:至今|到今天|到今)',
        # Q1至今
        r'(Q[1-4])\s*(?:至今|到今天|到今)',
        # 第一季度至今
        r'(第[一二三四1-4]\s*季度)\s*(?:至今|到今天|到今)',
        # 本季度/这季度/上季度/上上季度/下季度 + 至今
        r'((?:本|这|当前)季度)\s*(?:至今|到今天|到今)',
        r'((?:上上(个?季度|季|季度))|(?:上(个?季度|季|季度))|(?:下(个?季度|季|季度)))\s*(?:至今|到今天|到今)',
    ]
    for pat in ytd_patterns:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            res = _resolve_quarter_token(m.group(1), today)
            if res:
                y, q, label = res
                s, _ = _quarter_range(y, q)
                return DateRange(s, _fmt(today), range_type='quarter', granularity='quarter',
                                 original_text=m.group(0), label=f"{label}至今",
                                 is_relative=True, confidence=0.9)

    # 跨季度范围
    cross_patterns = [
        # 2026Q1 到/至/~ 2026Q3
        r'(\d{4}\s*年?\s*Q[1-4])\s*(?:到|至|~|-)\s*(\d{4}\s*年?\s*Q[1-4])',
        # Q1 到/至/~ Q2
        r'(Q[1-4])\s*(?:到|至|~|-)\s*(Q[1-4])',
        # 第一季度 至/到/~/ 第二季度 / 一季度至三季度
        r'(第?[一二三四1-4]\s*季度)\s*(?:到|至|~|-)\s*(第?[一二三四1-4]\s*季度)',
        # 本季度/上季度/上上季度/下季度 到/至 本季度/上季度/...
        r'((?:本|这|当前)季度|上(?:个?季度|季|季度)|上上(?:个?季度|季|季度)|下(?:个?季度|季|季度))'
        r'\s*(?:到|至|~|-)\s*'
        r'((?:本|这|当前)季度|上(?:个?季度|季|季度)|上上(?:个?季度|季|季度)|下(?:个?季度|季|季度))',
    ]
    for pat in cross_patterns:
        m = re.search(pat, msg, re.IGNORECASE)
        if m:
            left = _resolve_quarter_token(m.group(1), today)
            right = _resolve_quarter_token(m.group(2), today)
            if left and right:
                ly, lq, ll = left
                ry, rq, rl = right
                # 统一到同一参照：把"本年无年份"补成年份
                # 如果两端年份不同且都未显式带年，视为以 left 的年份为基准
                if ly != ry and not re.search(r'\d{4}', m.group(1)) and not re.search(r'\d{4}', m.group(2)):
                    ry = ly
                ls, _ = _quarter_range(ly, lq)
                _, re_end = _quarter_range(ry, rq)
                # 校验顺序
                if (ly, lq) > (ry, rq):
                    return None
                return DateRange(ls, re_end, range_type='quarter', granularity='quarter',
                                 original_text=m.group(0), label=f"{ll} 到 {rl}")
    return None


def _parse_quarter_span(msg: str, today: datetime) -> Optional[DateRange]:
    """
    季度内段：季度初到季度末 / Q1初到Q1末
    """
    # 匹配 "Q1初到Q1末" / "本季度初到本季度末"
    m = re.search(r'(Q[1-4]|(?:本|这|当前)季度|上(?:个?季度|季|季度)|上上(?:个?季度|季|季度)'
                  r'|下(?:个?季度|季|季度)|第[一二三四1-4]\s*季度)'
                  r'\s*(?:初|头|第一天|1号|一号)\s*(?:到|至|~|-)\s*'
                  r'\1\s*(?:末|尾|最后一天)',
                  msg, re.IGNORECASE)
    if m:
        token = m.group(1)
        res = _resolve_quarter_token(token, today)
        if res:
            y, q, label = res
            s, e = _quarter_range(y, q)
            return DateRange(s, e, range_type='quarter', granularity='quarter',
                             original_text=m.group(0), label=f'{label}全季')
    return None
