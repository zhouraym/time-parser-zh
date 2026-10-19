"""显式与精确日期表达：范围、精确日期、中文日期段、号段。"""

import re
from datetime import datetime
from typing import Optional

from time_parser_zh.models import DateRange
from time_parser_zh.month_parser import _resolve_relative_month_first_day
from time_parser_zh.normalization import (
    _fmt,
    _normalize_date_str,
)


def _parse_explicit_date_range(msg: str) -> Optional[DateRange]:
    """
    范围（最强匹配，最先尝试）：
    - 2026-04-01 至 2026-04-30
    - 从2026/03/01到2026/03/15
    - 2026-04-01 ~ 2026-04-30
    """
    patterns = [
        # 从2026/03/01到2026/03/15  /  自2026-03-01至2026-03-15
        r'(?:从|自)\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*(?:到|至|~)\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        # 2026-04-01 至 2026-04-30
        r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*(?:至|到|~)\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        # 20260401 至 20260415
        r'(\d{8})\s*(?:至|到|~)\s*(\d{8})',
    ]
    for pat in patterns:
        m = re.search(pat, msg)
        if m:
            s, e = m.group(1), m.group(2)
            # 标准化日期格式
            s = _normalize_date_str(s)
            e = _normalize_date_str(e)
            if s and e:
                return DateRange(s, e, range_type='range', original_text=m.group(0),
                                 label=f"{s} ~ {e}")
    return None


def _parse_day_range(msg: str, today: datetime) -> Optional[DateRange]:
    """
    当月号段（口语化）：
    - 5号到15号 / 5号至15号 / 5号~15号 / 5号-15号
    - 5号到今天 / 5号至今 / 1号到今天
    - 5-15 号段（5-15、5/15）
    """
    # X号到/至/~/- Y号（含 Y=今天/今儿 视为 today.day）
    # 注意：前面不能跟"月"，否则会抢 "4月1号到今天" / "上个月1号到今天"
    patterns = [
        # X号 到/至/~/- Y号
        r'(?<![月年])(\d{1,2})\s*号?\s*(?:到|至|~|-)\s*(\d{1,2})\s*号',
        # X号 到/至 今天/今儿
        r'(?<![月年])(\d{1,2})\s*号?\s*(?:到|至|~|-)\s*(?:今天|今儿|今日|当天)',
        # X号 至今
        r'(?<![月年])(\d{1,2})\s*号?\s*至今',
    ]
    for pat in patterns:
        m = re.search(pat, msg)
        if m:
            d1 = int(m.group(1))
            d2_raw = m.group(2) if m.lastindex and m.lastindex >= 2 else None
            if d2_raw is None or d2_raw == '':
                # X号至今 → X号 ~ today.day
                d2 = today.day
            else:
                d2 = today.day if re.search(r'今', d2_raw) else int(d2_raw)
            if not (1 <= d1 <= 31 and 1 <= d2 <= 31):
                return None
            if d1 > d2:
                return None
            try:
                s = datetime(today.year, today.month, d1)
                e = datetime(today.year, today.month, d2)
            except ValueError:
                return None
            return DateRange(_fmt(s), _fmt(e), range_type='range', granularity='day',
                             original_text=m.group(0),
                             label=f'{d1}号到{d2}号' if d2 != today.day else f'{d1}号到今天',
                             is_relative=True)

    # M-D / M/D（5-15 / 5/15 → 当月 5日 ~ 15日）
    # 必须避免抢 4 位年份里的 M-D（2026-04-15）以及 X月前的 1-3
    has_4digit_year = bool(re.search(r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b', msg)) \
        or bool(re.search(r'\b\d{8}\b', msg)) \
        or bool(re.search(r'\d{4}年\d{1,2}月\d{1,2}[日号]?', msg))
    if not has_4digit_year:
        # 只匹配前面不是"-"或"/"或"年"的号段
        m = re.search(r'(?<![\d\-/年])(\d{1,2})[-/](\d{1,2})(?!\d|月)', msg)
        if m:
            d1, d2 = int(m.group(1)), int(m.group(2))
            if 1 <= d1 <= 31 and 1 <= d2 <= 31 and d1 <= d2:
                try:
                    s = datetime(today.year, today.month, d1)
                    e = datetime(today.year, today.month, d2)
                    return DateRange(_fmt(s), _fmt(e), range_type='range', granularity='day',
                                     original_text=m.group(0), label=f'{d1}-{d2}号',
                                     is_relative=True)
                except ValueError:
                    pass
    return None


def _parse_chinese_date_range(msg: str, today: datetime) -> Optional[DateRange]:
    """
    中文日期段（带"月"和"号/日"）：
    - 3月1号到3月15号 / 3月1日至3月15日
    - 从4月5号到4月20号
    - 2026年3月1号至2026年3月31号
    - 3月1号到3月15号
    """
    # 从...到... / 自...至...
    patterns = [
        # 从2026年3月1号到2026年3月31号
        r'(?:从|自)\s*(\d{4})年(\d{1,2})月(\d{1,2})[日号]?\s*'
        r'(?:到|至|~)\s*(\d{4})年(\d{1,2})月(\d{1,2})[日号]?',
        # 2026年3月1号至2026年3月31号
        r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]?\s*'
        r'(?:到|至|~)\s*(\d{4})年(\d{1,2})月(\d{1,2})[日号]?',
        # 从3月5号到3月20号
        r'(?:从|自)\s*(\d{1,2})月(\d{1,2})[日号]?\s*'
        r'(?:到|至|~)\s*(\d{1,2})月(\d{1,2})[日号]?',
        # 3月5号到3月20号 / 3月5号至3月20日
        r'(\d{1,2})月(\d{1,2})[日号]?\s*'
        r'(?:到|至|~)\s*(\d{1,2})月(\d{1,2})[日号]?',
    ]
    for pat in patterns:
        m = re.search(pat, msg)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 6 and len(groups[0]) == 4:
                    # 带年份的格式
                    y1, mo1, d1, y2, mo2, d2 = groups
                    s = datetime(int(y1), int(mo1), int(d1))
                    e = datetime(int(y2), int(mo2), int(d2))
                else:
                    # 4 组：当前年
                    mo1, d1, mo2, d2 = groups
                    s = datetime(today.year, int(mo1), int(d1))
                    e = datetime(today.year, int(mo2), int(d2))
            except ValueError:
                continue
            if s > e:
                continue
            return DateRange(_fmt(s), _fmt(e), range_type='range', granularity='day',
                             original_text=m.group(0), label=f'{_fmt(s)} ~ {_fmt(e)}')
    return None


def _parse_specific_day_to_today(msg: str, today: datetime) -> Optional[DateRange]:
    """
    具体日期 到 今天：
    - 上个月1号到今天 / 上个月1号至今 / 上月15号到今天
    - 下个月1号到今天
    - 4月1号到今天 / 4月1日至今
    - 2026年3月15号到今天
    - 5月1号到今天（即使 5 月就是当月也支持）
    """
    # 1) 2026年X月Y号到今天
    m = re.search(
        r'(\d{4})年(\d{1,2})月(\d{1,2})\s*[日号]\s*(?:到|至|~|-)\s*(?:今天|今儿|今日|当天)',
        msg
    )
    if not m:
        m = re.search(
            r'(\d{4})年(\d{1,2})月(\d{1,2})\s*[日号]?\s*至今',
            msg
        )
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
        if d > today:
            return None
        return DateRange(_fmt(d), _fmt(today), range_type='range', granularity='day',
                         original_text=m.group(0), label=f'{_fmt(d)}至今',
                         is_relative=True)

    # 2) X月Y号到今天 / X月Y号至今（当前年）
    m = re.search(
        r'(?<!\d)(\d{1,2})月(\d{1,2})\s*[日号]\s*(?:到|至|~|-)\s*(?:今天|今儿|今日|当天)',
        msg
    )
    if not m:
        m = re.search(
            r'(?<!\d)(\d{1,2})月(\d{1,2})\s*[日号]?\s*至今',
            msg
        )
    if m:
        mo, day = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= day <= 31:
            try:
                d = datetime(today.year, mo, day)
            except ValueError:
                return None
            return DateRange(_fmt(d), _fmt(today), range_type='range', granularity='day',
                             original_text=m.group(0), label=f'{_fmt(d)}至今',
                             is_relative=True)

    # 3) 上个月/下个月/上月/上上个月/本月 + X号 到今天
    m = re.search(
        r'(上上(?:个?月|月)|上(?:个?月|月)|下(?:个?月|月)|(?:本|这|当)月)\s*'
        r'(\d{1,2})\s*[日号]?\s*(?:到|至|~|-)\s*(?:今天|今儿|今日|当天)',
        msg
    )
    if not m:
        m = re.search(
            r'(上上(?:个?月|月)|上(?:个?月|月)|下(?:个?月|月)|(?:本|这|当)月)\s*'
            r'(\d{1,2})\s*[日号]?\s*至今',
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
            return DateRange(_fmt(d), _fmt(today), range_type='range', granularity='day',
                             original_text=m.group(0),
                             label=f'{token}{day}号至今', is_relative=True)
    return None


def _parse_exact_date(msg: str, today: datetime) -> Optional[DateRange]:
    """
    精确日期：
    - 2026-04-15
    - 2026/04/15
    - 2026年4月15日
    - 2026年04月15日
    - 4月15日 / 4-15 / 4/15
    """
    # 完整 YYYY-MM-DD / YYYY/MM/DD
    m = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', msg)
    if m:
        s = _normalize_date_str(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        if s:
            return DateRange(s, s, range_type='point', granularity='day',
                             original_text=m.group(0), label=s)

    # YYYYMMDD
    m = re.search(r'(?<!\d)(\d{8})(?!\d)', msg)
    if m:
        s = _normalize_date_str(m.group(1))
        if s:
            return DateRange(s, s, range_type='point', granularity='day',
                             original_text=m.group(0), label=s)

    # YYYY年M月D日 / YYYY年MM月DD日
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})[日号]?', msg)
    if m:
        s = _normalize_date_str(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        if s:
            return DateRange(s, s, range_type='point', granularity='day',
                             original_text=m.group(0), label=s)

    # M月D日（当前年）
    m = re.search(r'(?<!\d)(\d{1,2})月(\d{1,2})[日号]?', msg)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                d = datetime(today.year, month, day)
                return DateRange(_fmt(d), _fmt(d), range_type='point', granularity='day',
                                 original_text=m.group(0), label=_fmt(d))
            except ValueError:
                pass

    # M-D / M/D（当前年）
    m = re.search(r'(?<!\d)(\d{1,2})[-/](\d{1,2})(?!\d)', msg)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                d = datetime(today.year, month, day)
                return DateRange(_fmt(d), _fmt(d), range_type='point', granularity='day',
                                 original_text=m.group(0), label=_fmt(d))
            except ValueError:
                pass

    return None
