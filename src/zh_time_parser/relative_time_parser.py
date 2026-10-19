"""相对时长解析：把“半小时后”“两周前”解析为锚点偏移。"""

import calendar
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from zh_time_parser.models import RelativeTime
from zh_time_parser.normalization import _parse_cn_number

_NUMBER = r'(?:\d+|[一二两三四五六七八九十]+)'
_DURATION = rf'(?P<number>{_NUMBER})\s*个?\s*(?P<unit>分钟|分|小时|钟头|天|日|周|星期|礼拜|个月|月)'
_HALF_HOUR = r'(?P<half>半)\s*(?P<half_unit>小时|钟头)'
_DURATION_PATTERN = rf'(?:{_HALF_HOUR}|{_DURATION})'

_FUTURE_SUFFIX = r'(?:以后|之后|后)'
_PAST_SUFFIX = r'(?:以前|之前|前)'

_UNIT_MAP = {
    '分钟': 'minute',
    '分': 'minute',
    '小时': 'hour',
    '钟头': 'hour',
    '天': 'day',
    '日': 'day',
    '周': 'week',
    '星期': 'week',
    '礼拜': 'week',
    '个月': 'month',
    '月': 'month',
}


def _parse_value(match: re.Match) -> Optional[Tuple[int, str]]:
    if match.groupdict().get('half'):
        # “半小时”统一保留为 30 minute，而不是 0.5 hour，便于 JSON 和任务系统消费。
        return 30, 'minute'

    raw_value = match.group('number')
    value = int(raw_value) if raw_value.isdigit() else _parse_cn_number(raw_value)
    unit = _UNIT_MAP.get(match.group('unit'))
    if value is None or value <= 0 or unit is None:
        return None
    return value, unit


def _add_months(anchor: datetime, months: int) -> datetime:
    """按日历月平移；目标月份没有同一天时回退到月末。"""
    month_index = anchor.year * 12 + anchor.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return anchor.replace(year=year, month=month, day=day)


def _resolve(anchor: datetime, value: int, unit: str, direction: str) -> datetime:
    sign = 1 if direction == 'future' else -1
    if unit == 'month':
        return _add_months(anchor, sign * value)
    factors = {
        'minute': timedelta(minutes=value),
        'hour': timedelta(hours=value),
        'day': timedelta(days=value),
        'week': timedelta(weeks=value),
    }
    return anchor + sign * factors[unit]


def extract_relative_time(user_message: str, anchor: Optional[datetime] = None) -> RelativeTime:
    """解析单个相对时长表达，并基于 ``anchor`` 计算目标时刻。"""
    if anchor is None:
        anchor = datetime.now()
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')
    if not isinstance(anchor, datetime):
        raise TypeError('anchor 必须是 datetime')

    msg = user_message.strip()
    if not msg:
        return RelativeTime(recognition_status='no_time_phrase')

    # 后缀形式：半小时后 / 10分钟以后 / 两周前
    match = re.search(rf'(?P<duration>{_DURATION_PATTERN})\s*(?P<direction>{_FUTURE_SUFFIX}|{_PAST_SUFFIX})', msg)
    direction = None
    if match:
        marker = match.group('direction')
        direction = 'past' if re.fullmatch(_PAST_SUFFIX, marker) else 'future'
    else:
        # 前缀形式：过两小时 / 再过三天
        match = re.search(rf'(?:再\s*)?过\s*(?P<duration>{_DURATION_PATTERN})', msg)
        if match:
            direction = 'future'

    if match and direction:
        parsed = _parse_value(match)
        if parsed:
            value, unit = parsed
            try:
                # 当前模型精确到分钟，因此去掉锚点的秒和微秒，输出稳定且可直接用于提醒。
                normalized_anchor = anchor.replace(second=0, microsecond=0)
                resolved = _resolve(normalized_anchor, value, unit, direction)
            except (ValueError, OverflowError):
                resolved = None
            if resolved is not None:
                return RelativeTime(
                    value=value,
                    unit=unit,
                    direction=direction,
                    resolved_at=resolved.strftime('%Y-%m-%d %H:%M'),
                    original_text=match.group(0),
                )

    has_relative_phrase = bool(
        re.search(r'分钟|小时|钟头|天|日|周|星期|礼拜|个月|月', msg)
        and re.search(r'以后|之后|后|以前|之前|前|过', msg)
    )
    return RelativeTime(
        original_text=msg,
        confidence=0.0,
        recognition_status='phrase_not_supported' if has_relative_phrase else 'no_time_phrase',
    )
