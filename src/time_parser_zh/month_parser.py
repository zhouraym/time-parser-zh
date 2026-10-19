"""月份相关表达：本月/上个月、X月到Y月、月初月末、相对月+具体日。"""

import re
from datetime import datetime
from typing import Optional, Tuple

from time_parser_zh.models import DateRange
from time_parser_zh.normalization import (
    _days_in_month,
    _fmt,
    _full_month_range,
    _n_months_before_range,
)


def _resolve_month_token(token: str, today: datetime) -> Optional[Tuple[int, int, str]]:
    """
    把单个"月 token"解析成 (year, month, label)。
    支持：本月/这月/当月、上个月/上月/上上个月、下个月/下月、
          X月 / X月份（如 3月）
    """
    t = token.strip()
    if not t:
        return None

    # 本月/这月/当月
    if re.fullmatch(r'(本|这|当)月', t):
        return today.year, today.month, '本月'

    # 上上个月
    if re.fullmatch(r'上上(个?月|月)', t):
        y, m = today.year, today.month - 2
        while m <= 0:
            m += 12
            y -= 1
        return y, m, '上上个月'

    # 上个月/上月
    if re.fullmatch(r'上(个?月|月)', t):
        y, m = today.year, today.month - 1
        if m == 0:
            m, y = 12, y - 1
        return y, m, '上个月'

    # 下个月/下月
    if re.fullmatch(r'下(个?月|月)', t):
        y, m = today.year, today.month + 1
        if m == 13:
            m, y = 1, y + 1
        return y, m, '下个月'

    # X月 / X月份
    match = re.fullmatch(r'(\d{1,2})\s*月份?', t)
    if match:
        month = int(match.group(1))
        if 1 <= month <= 12:
            return today.year, month, f'{month}月'

    return None


def _parse_month_to_today(msg: str, today: datetime) -> Optional[DateRange]:
    """
    月份起点 到 今天：
    - 上个月到今天 / 上个月至今 / 上月到今天 / 上月至今
    - 上上个月到今天 / 上上个月至今
    - 下个月到今天
    - 本月到今天（≈ 本月，但 label 不同）
    - X月到今天 / 3月至今
    """
    patterns = [
        # 上上个月至今 / 上上个月到今天
        (r'上上(个?月|月)\s*(?:至今|到今天|到今)', 2, '上上个月至今'),
        # 上个月至今 / 上个月到今天 / 上月至今 / 上月到今天
        (r'上(个?月|月)\s*(?:至今|到今天|到今)', 1, '上个月至今'),
        # 下个月至今 / 下个月到今天
        (r'下(个?月|月)\s*(?:至今|到今天|到今)', -1, '下个月至今'),
        # 本月至今 / 本月到今天 / 这个月到今天
        (r'(本|这|当)月\s*(?:至今|到今天|到今)', 0, '本月至今'),
    ]
    for pat, offset, label in patterns:
        m = re.search(pat, msg)
        if m:
            if offset == 0:
                s = today.replace(day=1)
            else:
                first, _ = _n_months_before_range(today, offset)
                s = first
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='day',
                             original_text=m.group(0), label=label, is_relative=True)

    # X月到今天 / 3月至今（如 3月至今 → 3月1日 ~ 今天）
    m = re.search(r'(\d{1,2})\s*月\s*(?:至今|到今天|到今)', msg)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            s = datetime(today.year, month, 1)
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='month',
                             original_text=m.group(0), label=f'{month}月至今',
                             is_relative=True)
    return None


def _parse_month_span(msg: str, today: datetime) -> Optional[DateRange]:
    """
    月内段：月初到月末 / 本月初到本月末
    """
    # 用两段定位：先找"头"再找"尾"，中间允许任意非换行字符作连接
    head_pat = r'(本月|这个月|当月)?\s*(月初|1号|一号)'
    sep_pat = r'[^，。！？\n]{0,5}(?:到|至|~|-)[^，。！？\n]{0,5}'
    tail_pat = r'(?:本月|这个月|当月)?\s*(月末|月底|最后一天)'
    m = re.search(head_pat + sep_pat + tail_pat, msg)
    if m:
        s = today.replace(day=1)
        last_day = _days_in_month(today.year, today.month)
        e = today.replace(day=last_day)
        return DateRange(_fmt(s), _fmt(e), range_type='range', granularity='month',
                         original_text=m.group(0), label='本月月初到月末')
    return None


def _resolve_relative_month_first_day(token: str, today: datetime) -> Optional[Tuple[int, int]]:
    """
    把"本月/上个月/上月/上上个月/下个月"等相对月词解析为 (year, month)。
    返回 None 表示不是相对月词。
    """
    t = token.strip()
    if re.fullmatch(r'(本|这|当)月', t) or re.fullmatch(r'本月份', t):
        return today.year, today.month
    if re.fullmatch(r'上上(个?月|月)', t):
        y, m = today.year, today.month - 2
        while m <= 0:
            m += 12
            y -= 1
        return y, m
    if re.fullmatch(r'上(个?月|月)', t):
        y, m = today.year, today.month - 1
        if m == 0:
            m, y = 12, y - 1
        return y, m
    if re.fullmatch(r'下(个?月|月)', t):
        y, m = today.year, today.month + 1
        if m == 13:
            m, y = 1, y + 1
        return y, m
    return None


def _parse_relative_month_day(msg: str, today: datetime) -> Optional[DateRange]:
    """
    相对月 + 具体日（单点）：
    - 上个月1号 / 上个月15号 / 上月1日
    - 上上个月10号
    - 下个月1号 / 下月15号
    - 本月15号 / 这个月10号
    """
    m = re.search(
        r'(上上(?:个?月|月)|上(?:个?月|月)|下(?:个?月|月)|(?:本|这|当)月)\s*(\d{1,2})\s*[日号]',
        msg
    )
    if m:
        token = m.group(1)
        day = int(m.group(2))
        res = _resolve_relative_month_first_day(token, today)
        if res and 1 <= day <= 31:
            y, mo = res
            try:
                d = datetime(y, mo, day)
            except ValueError:
                return None
            return DateRange(_fmt(d), _fmt(d), range_type='point', granularity='day',
                             original_text=m.group(0), label=_fmt(d), is_relative=True)
    return None


def _parse_month(msg: str, today: datetime) -> Optional[DateRange]:
    """
    本月/这个月/当月/这月 → 当月 1 号 ~ 今天
    上个月/上月/上上月 → 上个月 1 号 ~ 上个月最后一天
    下个月/下月 → 下个月 1 号 ~ 下个月最后一天
    X月（不带"本/上/下"）→ 当前年的 X 月
    X月到Y月 / X-Y月 → 跨月范围
    """
    # 本月/这个月/当月/这月（支持"这个月""本个月"等含"个"写法）
    if re.search(r'(本|这|当)\s*个?\s*月(?!底|末|初)', msg):
        s = today.replace(day=1)
        return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='month',
                         original_text='本月', label='本月', is_relative=True)

    # 上上个月
    if re.search(r'上上(个?月|月)', msg):
        first, last = _n_months_before_range(today, 2)
        return DateRange(_fmt(first), _fmt(last), range_type='range', granularity='month',
                         original_text='上上个月', label='上上个月', is_relative=True)

    # 上个月/上月
    if re.search(r'上(个?月|月)(?!底|末|初)', msg):
        first, last = _n_months_before_range(today, 1)
        return DateRange(_fmt(first), _fmt(last), range_type='range', granularity='month',
                         original_text='上个月', label='上个月', is_relative=True)

    # 下个月/下月
    if re.search(r'下(个?月|月)', msg):
        if today.month == 12:
            first = datetime(today.year + 1, 1, 1)
            last = datetime(today.year + 1, 1, 31)
        else:
            first = datetime(today.year, today.month + 1, 1)
            last_day = _days_in_month(today.year, today.month + 1)
            last = datetime(today.year, today.month + 1, last_day)
        return DateRange(_fmt(first), _fmt(last), range_type='range', granularity='month',
                         original_text='下个月', label='下个月', is_relative=True)

    # 月初/月初至今（避免抢"本月初到本月末"）
    if (re.search(r'本月(初|1号|一号)|月初(?:至今)?', msg)
            and not re.search(r'(?:到|至|~|-)\s*(月末|月底|最后一天)', msg)):
        s = today.replace(day=1)
        return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='month',
                         original_text='月初', label='本月月初', is_relative=True)

    # 月末/月底
    if re.search(r'本月(末|底|最后一天)|月底', msg):
        s = today.replace(day=1)
        last_day = _days_in_month(today.year, today.month)
        e = today.replace(day=last_day)
        return DateRange(_fmt(s), _fmt(e), range_type='range', granularity='month',
                         original_text='月末', label='本月月末', is_relative=True)

    # X月到Y月 / X月-Y月 / X至Y月 / X~Y月 / X-Y月
    cross_patterns = [
        r'(\d{1,2})\s*月\s*(?:到|至|~|-)\s*(\d{1,2})\s*月',   # 3月到5月 / 3月-5月
        r'(\d{1,2})\s*月?\s*-\s*(\d{1,2})\s*月',              # 1-3月 / 1月-3月
        r'(\d{1,2})\s*~\s*(\d{1,2})\s*月',                    # 3~5月
    ]
    for pat in cross_patterns:
        m = re.search(pat, msg)
        if m:
            m1, m2 = int(m.group(1)), int(m.group(2))
            if 1 <= m1 <= 12 and 1 <= m2 <= 12 and m1 <= m2:
                s, e = _full_month_range(today.year, m1)[0], _full_month_range(today.year, m2)[1]
                return DateRange(_fmt(s), _fmt(e), range_type='range', granularity='month',
                                 original_text=m.group(0), label=f'{m1}月到{m2}月')

    # 单 X 月（如"3月数据"、"3月份数据"）
    m = re.search(r'(?<![\d/])(\d{1,2})\s*月(?![\d/])', msg)
    if m:
        m1 = int(m.group(1))
        if 1 <= m1 <= 12:
            s, e = _full_month_range(today.year, m1)
            return DateRange(_fmt(s), _fmt(e), range_type='range', granularity='month',
                             original_text=m.group(0), label=f'{m1}月')

    return None
