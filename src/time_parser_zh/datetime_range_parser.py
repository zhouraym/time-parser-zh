"""带时刻的日期区间，以及“直到昨天中午”这类单侧结束边界。"""

import re
from datetime import datetime
from typing import Optional, Tuple

from time_parser_zh.date_parser import extract_date_range_v2
from time_parser_zh.datetime_parser import extract_datetime_point
from time_parser_zh.models import DateTimeRange
from time_parser_zh.range_safety import _has_multiple_range_connectors


def _parse_endpoint(text: str, today: datetime, week_start: str,
                    is_end: bool) -> Optional[Tuple[datetime, bool, bool, float]]:
    """返回 datetime、是否相对、是否含明确时刻、置信度。"""
    point = extract_datetime_point(text, today=today, week_start=week_start)
    if point and point.datetime is not None:
        return (
            datetime.strptime(point.datetime, '%Y-%m-%d %H:%M:%S'),
            point.is_relative,
            True,
            point.confidence,
        )

    # 区间端点常见的 M-D / M/D 简写。
    shorthand = re.search(r'(?<!\d)(\d{1,2})\s*[-/]\s*(\d{1,2})(?!\d)', text)
    if shorthand:
        value = datetime(today.year, int(shorthand.group(1)), int(shorthand.group(2)))
        if is_end:
            value = value.replace(hour=23, minute=59, second=59)
        return value, True, False, 1.0

    date_range = extract_date_range_v2(text, today=today, week_start=week_start)
    if not date_range or date_range.start is None or date_range.start != date_range.end:
        return None
    value = datetime.strptime(date_range.start, '%Y-%m-%d')
    if is_end:
        value = value.replace(hour=23, minute=59, second=59)
    return value, date_range.is_relative, False, date_range.confidence


def _build_result(msg: str, start_parts, end_parts) -> DateTimeRange:
    start = start_parts[0] if start_parts else None
    end = end_parts[0] if end_parts else None
    start_has_time = start_parts[2] if start_parts else False
    end_has_time = end_parts[2] if end_parts else False
    precision_lost = bool(
        (start_has_time and start and start.time() != datetime.min.time())
        or (end_has_time and end and end.time() != datetime.max.replace(microsecond=0).time())
    )
    confidences = [parts[3] for parts in (start_parts, end_parts) if parts]
    return DateTimeRange(
        start=start.strftime('%Y-%m-%d %H:%M:%S') if start else None,
        end=end.strftime('%Y-%m-%d %H:%M:%S') if end else None,
        date_start=start.strftime('%Y-%m-%d') if start else None,
        date_end=end.strftime('%Y-%m-%d') if end else None,
        precision_lost=precision_lost,
        original_text=msg,
        is_relative=any(parts[1] for parts in (start_parts, end_parts) if parts),
        confidence=min(confidences) if confidences else 0.0,
    )


def extract_datetime_range(user_message: str, today: Optional[datetime] = None,
                           week_start: str = 'monday') -> DateTimeRange:
    """解析日期时刻区间或单侧“直到/截至”结束边界。"""
    if today is None:
        today = datetime.now()
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')
    if week_start not in ('monday', 'sunday'):
        raise ValueError("week_start 必须是 'monday' 或 'sunday'")
    msg = user_message.strip()
    if not msg:
        return DateTimeRange(recognition_status='no_time_phrase')

    if _has_multiple_range_connectors(msg):
        return DateTimeRange(
            original_text=msg,
            confidence=0.0,
            recognition_status='phrase_not_supported',
        )

    # 完整区间：8月1日至昨天中午 / 从8-1到8-10 / 8月1日直到昨天中午。
    match = re.search(
        r'(?:从\s*)?(?P<start>.+?)\s*(?:直到|直至|截止到|截至|截止|到|至|~)\s*(?P<end>.+)',
        msg,
    )
    if match:
        try:
            start_parts = _parse_endpoint(match.group('start'), today, week_start, is_end=False)
            end_parts = _parse_endpoint(match.group('end'), today, week_start, is_end=True)
        except (ValueError, OverflowError, KeyError, IndexError):
            start_parts = end_parts = None
        if start_parts and end_parts and start_parts[0] <= end_parts[0]:
            return _build_result(match.group(0), start_parts, end_parts)

    # 单侧结束边界：直到昨天中午 / 截至明天下午3点。
    match = re.search(r'(?:直到|直至|截止到|截至|截止|到)\s*(?P<end>.+)', msg)
    if match:
        try:
            end_parts = _parse_endpoint(match.group('end'), today, week_start, is_end=True)
        except (ValueError, OverflowError, KeyError, IndexError):
            end_parts = None
        if end_parts:
            return _build_result(match.group(0), None, end_parts)

    return DateTimeRange(
        original_text=msg,
        confidence=0.0,
        recognition_status='phrase_not_supported',
    )
