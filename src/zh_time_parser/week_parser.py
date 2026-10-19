"""周相关表达：重复上/下偏移、周内日期、跨周范围及周至今。"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from zh_time_parser.models import DateRange
from zh_time_parser.normalization import _fmt

_WEEK_TOKEN = r'(?:上+|下+|本|这|当前)(?:个)?(?:周|星期|礼拜)'
_WEEK_OR_BARE = rf'(?:{_WEEK_TOKEN}|周|星期|礼拜)'
_TOKEN_BOUNDARY = r'(?<![本这上下前当个])'
_WEEKDAY = r'[一二三四五六日天1-7]'
_WEEKDAY_MAP = {
    '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6, '天': 6,
    '1': 0, '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6,
}


def _week_range(
    ref_date: datetime, offset_weeks: int = 0, week_start: str = 'monday',
) -> Tuple[datetime, datetime]:
    """计算指定偏移周的自然周范围。

    Args:
        ref_date: 基准日期。
        offset_weeks: 相对本周的偏移周数。
        week_start: monday 或 sunday。

    Returns:
        该周第一天和最后一天。

    Raises:
        OverflowError: 偏移超出 datetime 的有效范围。
    """
    days_since_start = ref_date.weekday()
    if week_start == 'sunday':
        days_since_start = (days_since_start + 1) % 7
    start = ref_date - timedelta(days=days_since_start) + timedelta(weeks=offset_weeks)
    return start, start + timedelta(days=6)


def _weekday_offset(weekday: int, week_start: str) -> int:
    """把固定星期索引转换为指定周起始日下的偏移。

    Args:
        weekday: 周一为 0、周日为 6 的星期索引。
        week_start: monday 或 sunday。

    Returns:
        距周起始日的天数。

    Raises:
        无。
    """
    return weekday if week_start == 'monday' else (weekday + 1) % 7


def _resolve_week_offset(token: str) -> Optional[int]:
    """按完整周词中上/下的重复次数计算偏移。

    Args:
        token: 本周、上上上周、下下个星期等周词；空串表示本周。

    Returns:
        偏移周数，不支持的周词返回 None。

    Raises:
        无。
    """
    token = token.strip()
    if not token or re.fullmatch(r'(?:本|这|当前)?(?:个)?(?:周|星期|礼拜)', token):
        return 0
    match = re.fullmatch(r'(上+|下+)(?:个)?(?:周|星期|礼拜)', token)
    if match:
        direction = match.group(1)
        return len(direction) * (-1 if direction[0] == '上' else 1)
    return None


def _parse_week_day_range(
    msg: str, today: datetime, week_start: str = 'monday',
) -> Optional[DateRange]:
    """解析周内或跨周日期范围，右端省略周词时继承左端。

    Args:
        msg: 用户消息，例如上上上周一到周五、上周五到本周一。
        today: 基准时刻。
        week_start: monday 或 sunday。

    Returns:
        日期范围、明确无效的范围，或不匹配时的 None。

    Raises:
        OverflowError: 周偏移超出 datetime 范围。
    """
    pattern = (
        rf'{_TOKEN_BOUNDARY}(?P<left>{_WEEK_OR_BARE})\s*'
        rf'(?:周|星期|礼拜)?\s*(?P<day1>{_WEEKDAY})'
        rf'\s*(?:到|至|~|-)\s*(?:(?P<right>{_WEEK_OR_BARE})\s*)?'
        rf'(?:周|星期|礼拜)?\s*(?P<day2>{_WEEKDAY})(?!\d)'
    )
    match = re.search(pattern, msg)
    if not match:
        return None
    left_token, right_token = match.group('left'), match.group('right')
    left_offset = _resolve_week_offset(left_token)
    # 裸“周五/星期五”与省略周词一样，继承左侧所在周。
    right_offset = (
        _resolve_week_offset(right_token)
        if right_token and re.fullmatch(_WEEK_TOKEN, right_token) else left_offset
    )
    if left_offset is None or right_offset is None:
        return None
    left_week, _ = _week_range(today, left_offset, week_start)
    right_week, _ = _week_range(today, right_offset, week_start)
    start = left_week + timedelta(days=_weekday_offset(_WEEKDAY_MAP[match.group('day1')], week_start))
    end = right_week + timedelta(days=_weekday_offset(_WEEKDAY_MAP[match.group('day2')], week_start))
    if start.date() > end.date():
        return DateRange(original_text=match.group(), confidence=0.0, recognition_status='phrase_not_supported')
    return DateRange(
        _fmt(start), _fmt(end), granularity='day', original_text=match.group(),
        label=match.group(), is_relative=True, week_start=week_start,
    )


def _parse_week_to_today(
    msg: str, today: datetime, week_start: str = 'monday',
) -> Optional[DateRange]:
    """解析任意重复周偏移的周起点至今。

    Args:
        msg: 用户消息，例如上上上周至今。
        today: 基准时刻。
        week_start: monday 或 sunday。

    Returns:
        日期范围；未来周至今返回失败结果；不匹配返回 None。

    Raises:
        OverflowError: 周偏移超出 datetime 范围。
    """
    match = re.search(
        rf'{_TOKEN_BOUNDARY}({_WEEK_TOKEN})\s*'
        r'(?:(?:到|至|~|-)\s*)?(?:今天|今儿|今日|当天|至今)', msg,
    )
    if not match:
        return None
    offset = _resolve_week_offset(match.group(1))
    if offset is None:
        return None
    start, _ = _week_range(today, offset, week_start)
    if start.date() > today.date():
        return DateRange(original_text=match.group(), confidence=0.0, recognition_status='phrase_not_supported')
    return DateRange(
        _fmt(start), _fmt(today), granularity='day', original_text=match.group(),
        label=match.group(), is_relative=True, week_start=week_start,
    )


def _parse_week(
    msg: str, today: datetime, week_start: str = 'monday',
) -> Optional[DateRange]:
    """解析完整周词、跨周范围或指定周几，避免从重复前缀中截取子串。

    Args:
        msg: 用户消息。
        today: 基准时刻。
        week_start: monday 或 sunday。

    Returns:
        匹配的日期范围或单日；不匹配返回 None。

    Raises:
        OverflowError: 周偏移超出 datetime 范围。
    """
    match = re.search(
        rf'{_TOKEN_BOUNDARY}(?P<left>{_WEEK_TOKEN})'
        rf'(?:\s*(?P<weekday>{_WEEKDAY})(?!\d)|'
        rf'\s*(?:到|至|~|-)\s*(?P<right>{_WEEK_TOKEN}))?', msg,
    )
    if not match:
        return None
    offset = _resolve_week_offset(match.group('left'))
    if offset is None:
        return None
    start, end = _week_range(today, offset, week_start)
    range_type, granularity = 'range', 'week'
    if match.group('weekday'):
        start += timedelta(days=_weekday_offset(_WEEKDAY_MAP[match.group('weekday')], week_start))
        end = start
        range_type, granularity = 'point', 'day'
    elif match.group('right'):
        right_offset = _resolve_week_offset(match.group('right'))
        if right_offset is None:
            return None
        if offset > right_offset:
            return DateRange(original_text=match.group(), confidence=0.0, recognition_status='phrase_not_supported')
        _, end = _week_range(today, right_offset, week_start)
    return DateRange(
        _fmt(start), _fmt(end), range_type=range_type, granularity=granularity,
        original_text=match.group(), label=match.group(), is_relative=True, week_start=week_start,
    )
