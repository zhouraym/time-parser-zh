"""解析“在昨天的时候 / 到月底的时候”这类 as-of 评估时点。"""

import re
from datetime import datetime
from typing import Optional, Tuple

from time_parser_zh.date_parser import extract_date_range_v2
from time_parser_zh.datetime_parser import extract_datetime_point
from time_parser_zh.models import TemporalAnchor

_ANCHOR_PATTERNS = (
    re.compile(r'(?:到了|等到|在|到)\s*(?P<value>.+?)\s*(?:的)?时候'),
    re.compile(
        r'(?P<value>前天|昨天|昨日|今天|今日|明天|明日|后天|'
        r'(?:这个|本|下个?|上个?)?月(?:底|末)|(?:今年|明年|去年)?(?:年底|年末))\s*(?:的)?时候'
    ),
)


def _parse_anchor_value(text: str, today: datetime,
                        week_start: str) -> Optional[Tuple[str, str, bool, float, datetime]]:
    point = extract_datetime_point(text, today=today, week_start=week_start)
    if point and point.datetime is not None:
        parsed = datetime.strptime(point.datetime, '%Y-%m-%d %H:%M:%S')
        return point.datetime, 'datetime', point.is_relative, point.confidence, parsed

    date_range = extract_date_range_v2(text, today=today, week_start=week_start)
    if not date_range:
        return None

    # 单日表达就是该日期；月底/年末必须取被强调的 point/end，而不是区间起点。
    if date_range.start == date_range.end:
        value = date_range.start
    elif date_range.point:
        value = date_range.point
    elif re.search(r'月底|月末|年底|年末', text):
        value = date_range.end
    else:
        # “在下个月的时候”仍是一个时间段，缺少具体评估日，不在这里替用户选择月初或月末。
        return None
    if value is None:
        return None
    parsed = datetime.strptime(value, '%Y-%m-%d')
    return value, 'date', date_range.is_relative, date_range.confidence, parsed


def extract_temporal_anchor(user_message: str, today: Optional[datetime] = None,
                            week_start: str = 'monday') -> TemporalAnchor:
    """提取 as-of 评估锚点；不生成 ``<`` / ``<=`` 等筛选运算符。"""
    if today is None:
        today = datetime.now()
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')
    if week_start not in ('monday', 'sunday'):
        raise ValueError("week_start 必须是 'monday' 或 'sunday'")
    msg = user_message.strip()
    if not msg:
        return TemporalAnchor(recognition_status='no_time_phrase')

    saw_anchor_phrase = False
    for pattern in _ANCHOR_PATTERNS:
        match = pattern.search(msg)
        if not match:
            continue
        saw_anchor_phrase = True
        try:
            parsed = _parse_anchor_value(match.group('value'), today, week_start)
        except (ValueError, OverflowError, KeyError, IndexError):
            parsed = None
        if parsed:
            value, value_type, is_relative, confidence, comparable = parsed
            reference = today.replace(hour=0, minute=0, second=0, microsecond=0)
            return TemporalAnchor(
                mode='as_of',
                value=value,
                value_type=value_type,
                original_text=msg,
                matched_text=match.group(0),
                is_relative=is_relative,
                is_future=comparable > reference,
                confidence=confidence,
            )

    return TemporalAnchor(
        original_text=msg,
        confidence=0.0,
        recognition_status='phrase_not_supported' if saw_anchor_phrase else 'no_time_phrase',
    )
