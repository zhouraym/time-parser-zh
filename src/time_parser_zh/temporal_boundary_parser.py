"""解析“周五之前 / 三天以内 / 从明天开始”等单侧时间边界。"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from time_parser_zh.date_parser import extract_date_range_v2
from time_parser_zh.datetime_parser import extract_datetime_point
from time_parser_zh.models import RelativeTime, TemporalBoundary
from time_parser_zh.relative_time_parser import _DURATION_PATTERN, extract_relative_time
from time_parser_zh.week_parser import _WEEKDAY_MAP


def _parse_endpoint(text: str, today: datetime, week_start: str,
                    edge: str) -> Optional[Tuple[str, str, bool, float]]:
    """解析边界值，edge=start/end 决定范围表达取哪一端。"""
    point = extract_datetime_point(text, today=today, week_start=week_start)
    if point and point.datetime is not None:
        return point.datetime[:16], 'datetime', point.is_relative, point.confidence

    date_range = extract_date_range_v2(text, today=today, week_start=week_start)
    if date_range:
        if edge == 'start':
            value = date_range.start
        else:
            value = date_range.point or date_range.end
        if value is not None:
            return value, 'date', date_range.is_relative, date_range.confidence

    # DateRange 不单独解析“周五”；边界/截止语境下，裸周几取今天起最近一次该星期。
    weekday_match = re.search(r'(?<![本上下这])(?:周|星期|礼拜)\s*([一二三四五六日天1-7])', text)
    if weekday_match:
        weekday = _WEEKDAY_MAP[weekday_match.group(1)]
        days_ahead = (weekday - today.weekday()) % 7
        resolved = today + timedelta(days=days_ahead)
        return resolved.strftime('%Y-%m-%d'), 'date', True, 1.0
    return None


def _result(msg: str, matched_text: str, operator: str,
            endpoint: Tuple[str, str, bool, float],
            duration: Optional[RelativeTime] = None) -> TemporalBoundary:
    value, value_type, is_relative, confidence = endpoint
    return TemporalBoundary(
        operator=operator,
        value=value,
        value_type=value_type,
        duration=duration,
        original_text=msg,
        matched_text=matched_text,
        is_relative=is_relative,
        confidence=confidence,
    )


def extract_temporal_boundary(user_message: str, today: Optional[datetime] = None,
                              week_start: str = 'monday') -> TemporalBoundary:
    """解析单侧时间边界；失败时返回空 ``TemporalBoundary``。"""
    if today is None:
        today = datetime.now()
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')
    if week_start not in ('monday', 'sunday'):
        raise ValueError("week_start 必须是 'monday' 或 'sunday'")
    msg = user_message.strip()
    if not msg:
        return TemporalBoundary(recognition_status='no_time_phrase')

    # 相对锚点的包含式截止：三天以内 / 两小时内。
    match = re.search(rf'(?P<duration>{_DURATION_PATTERN})\s*(?:以内|之内|内)', msg)
    if match:
        duration = extract_relative_time(f"{match.group('duration')}后", anchor=today)
        if duration and duration.resolved_at is not None:
            endpoint = (duration.resolved_at, 'datetime', True, duration.confidence)
            return _result(msg, match.group(0), '<=', endpoint, duration=duration)

    rules = (
        (re.compile(r'从\s*(?P<value>.+?)\s*(?:开始|起)(?:\s|$)'), '>=', 'start'),
        (re.compile(r'(?:截至|截止到|截止)\s*(?P<value>.+)'), '<=', 'end'),
        (re.compile(r'最迟\s*(?P<value>.+)'), '<=', 'end'),
        (re.compile(r'(?P<value>.+?)\s*(?:之前|以前)(?:\s|$)'), '<', 'end'),
        (re.compile(r'(?P<value>.+?)\s*(?:以后|之后)(?:\s|$)'), '>=', 'start'),
    )
    saw_boundary_phrase = False
    for pattern, operator, edge in rules:
        match = pattern.search(msg)
        if not match:
            continue
        saw_boundary_phrase = True
        try:
            parsed_endpoint = _parse_endpoint(match.group('value'), today, week_start, edge)
        except (ValueError, OverflowError, KeyError, IndexError):
            parsed_endpoint = None
        if parsed_endpoint:
            return _result(msg, match.group(0), operator, parsed_endpoint)

    return TemporalBoundary(
        original_text=msg,
        confidence=0.0,
        recognition_status='phrase_not_supported' if saw_boundary_phrase else 'no_time_phrase',
    )
