"""可组合的自然月位移表达：重复上/下、月份链、季度后的月份。"""

import re
from datetime import datetime
from typing import Optional, Tuple

from time_parser_zh.models import DateRange
from time_parser_zh.normalization import _fmt, _full_month_range

_MONTH_TERM = r'(?:上+|下+|本|这)(?:一?个)?月'
_MONTH_CHAIN_PATTERN = re.compile(rf'(?P<expr>{_MONTH_TERM}(?:\s*的\s*{_MONTH_TERM})+)')
_REPEATED_MONTH_PATTERN = re.compile(
    r'(?<![上下])(?P<expr>(?P<direction>上{2,}|下{2,})(?:一?个)?月)(?![上下])'
)


def _shift_year_month(year: int, month: int, offset: int) -> Tuple[int, int]:
    index = year * 12 + month - 1 + offset
    shifted_year, zero_based_month = divmod(index, 12)
    return shifted_year, zero_based_month + 1


def _month_offset(direction: str) -> int:
    if direction in ('本', '这'):
        return 0
    sign = -1 if direction.startswith('上') else 1
    return sign * len(direction)


def _month_result(today: datetime, offset: int, original_text: str) -> DateRange:
    year, month = _shift_year_month(today.year, today.month, offset)
    start, end = _full_month_range(year, month)
    # 与既有“本月”口径一致：组合位移最终回到当前月时按 MTD 截止今天。
    if offset == 0:
        end = today
    return DateRange(
        _fmt(start), _fmt(end),
        range_type='range', granularity='month',
        original_text=original_text,
        label=f'{year}-{month:02d}',
        is_relative=True,
    )


def _parse_month_chain(msg: str, today: datetime) -> Optional[DateRange]:
    match = _MONTH_CHAIN_PATTERN.search(msg)
    if not match:
        return None
    directions = re.findall(r'(上+|下+|本|这)(?:一?个)?月', match.group('expr'))
    if len(directions) < 2:
        return None
    offset = sum(_month_offset(direction) for direction in directions)
    return _month_result(today, offset, match.group('expr'))


def _parse_repeated_month(msg: str, today: datetime) -> Optional[DateRange]:
    match = _REPEATED_MONTH_PATTERN.search(msg)
    if not match:
        return None
    offset = _month_offset(match.group('direction'))
    return _month_result(today, offset, match.group('expr'))


_QUARTER_AFTER_MONTH_PATTERN = re.compile(
    r'(?P<expr>'
    r'(?:(?P<year>\d{4})\s*年?\s*)?'
    r'(?:第?\s*(?P<q_cn>[一二三四1-4])\s*季度|[Qq]\s*(?P<q_digit>[1-4]))'
    r'\s*后\s*(?:的)?\s*(?:下\s*(?:一|1)?|(?:一|1))\s*个?月'
    r')'
)
_RELATIVE_QUARTER_AFTER_MONTH_PATTERN = re.compile(
    r'(?P<expr>(?P<relative>本|这|上|下)(?:个)?季度'
    r'\s*后\s*(?:的)?\s*(?:下\s*(?:一|1)?|(?:一|1))\s*个?月)'
)


def _quarter_number(raw: str) -> int:
    return int(raw) if raw.isdigit() else '一二三四'.index(raw) + 1


def _month_after_quarter(year: int, quarter: int, original_text: str,
                         is_relative: bool) -> DateRange:
    month_after = quarter * 3 + 1
    if month_after == 13:
        year += 1
        month_after = 1
    start, end = _full_month_range(year, month_after)
    return DateRange(
        _fmt(start), _fmt(end),
        range_type='range', granularity='month',
        original_text=original_text,
        label=f'{year}-{month_after:02d}',
        is_relative=is_relative,
    )


def _parse_quarter_after_month(msg: str, today: datetime) -> Optional[DateRange]:
    match = _QUARTER_AFTER_MONTH_PATTERN.search(msg)
    if match:
        quarter = _quarter_number(match.group('q_cn') or match.group('q_digit'))
        year = int(match.group('year')) if match.group('year') else today.year
        return _month_after_quarter(year, quarter, match.group('expr'), match.group('year') is None)

    match = _RELATIVE_QUARTER_AFTER_MONTH_PATTERN.search(msg)
    if not match:
        return None
    current_index = today.year * 4 + (today.month - 1) // 3
    relative = match.group('relative')
    offset = {'本': 0, '这': 0, '上': -1, '下': 1}[relative]
    target_index = current_index + offset
    year, zero_based_quarter = divmod(target_index, 4)
    return _month_after_quarter(year, zero_based_quarter + 1, match.group('expr'), True)


def _parse_temporal_shift(msg: str, today: datetime) -> Optional[DateRange]:
    """按强到弱顺序解析组合月份表达。"""
    return (
        _parse_month_chain(msg, today)
        or _parse_repeated_month(msg, today)
        or _parse_quarter_after_month(msg, today)
    )
