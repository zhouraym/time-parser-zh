"""中文日期时刻解析器。

本模块刻意不接入 DateRange 调度链；调用方只有显式调用
``extract_datetime_point`` 时才会得到 DateTimePoint，确保原 API 契约不变。
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from time_parser_zh.models import DateTimePoint
from time_parser_zh.normalization import _parse_cn_number
from time_parser_zh.week_parser import _WEEKDAY_MAP, _week_range

_PERIOD_PATTERN = re.compile(r'凌晨|早上|早晨|上午|中午|下午|晚上|晚间|今早|今晚|明早|明晚|昨晚')
_DATE_CUE_PATTERN = re.compile(
    r'前天|昨天|昨日|昨晚|今天|今日|今早|今晚|明天|明日|明早|明晚|后天|'
    r'(?:本|这|上上|下下|上|下)?(?:周|星期|礼拜)|'
    r'\d{4}\s*[-/年]|\d{1,2}\s*月\s*\d{1,2}\s*[日号]?'
)


def _number(value: str) -> Optional[int]:
    value = value.replace('〇', '零')
    if value == '零':
        return 0
    return _parse_cn_number(value)


def _resolve_date(msg: str, today: datetime, week_start: str) -> Optional[Tuple[datetime, bool]]:
    """返回目标日期和它是否依赖 today。"""
    # YYYY-MM-DD / YYYY年M月D日 / YYYY/M/D
    match = re.search(r'(?<!\d)(\d{4})\s*(?:年|[-/])\s*(\d{1,2})\s*(?:月|[-/])\s*(\d{1,2})\s*[日号]?', msg)
    if match:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))), False

    # 未写年份的 M月D日，沿用 DateRange 的口径：使用 today 所在年份。
    match = re.search(r'(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?', msg)
    if match:
        return datetime(today.year, int(match.group(1)), int(match.group(2))), True

    # 周几。下周三表示下一个自然周的星期三。
    match = re.search(
        r'((?:本|这|上上|下下|上|下)?(?:周|星期|礼拜))\s*([一二三四五六日天1-7])',
        msg,
    )
    if match:
        token, weekday = match.group(1), _WEEKDAY_MAP[match.group(2)]
        if token.startswith('上上'):
            offset = -2
        elif token.startswith('下下'):
            offset = 2
        elif token.startswith('上'):
            offset = -1
        elif token.startswith('下'):
            offset = 1
        else:
            offset = 0
        start, _ = _week_range(today, offset, week_start)
        # _week_range 的起点会随 week_start 改变，weekday 则是固定的周一索引。
        day_offset = weekday if week_start == 'monday' else (weekday + 1) % 7
        return start + timedelta(days=day_offset), True

    relative_days = (
        (r'前天', -2),
        (r'昨天|昨日|昨晚', -1),
        (r'后天', 2),
        (r'明天|明日|明早|明晚', 1),
        (r'今天|今日|今早|今晚', 0),
    )
    for pattern, offset in relative_days:
        if re.search(pattern, msg):
            return today + timedelta(days=offset), True

    # 只有钟点、没有日期时，解释为今天；存在无法解析的日期提示时拒绝猜测。
    if _DATE_CUE_PATTERN.search(msg):
        return None
    return today, True


def _apply_period(hour: int, period: Optional[str]) -> Optional[int]:
    if not 0 <= hour <= 23:
        return None
    if not period or hour > 12:
        return hour
    if period in ('凌晨', '早上', '早晨', '上午', '今早', '明早'):
        return 0 if hour == 12 else hour
    if period == '中午':
        return hour + 12 if 1 <= hour <= 10 else hour
    if period in ('下午', '晚上', '晚间', '今晚', '明晚'):
        return hour + 12 if 1 <= hour <= 11 else hour
    return hour


def _resolve_time(msg: str) -> Optional[Tuple[int, int, int, str, float]]:
    period_match = _PERIOD_PATTERN.search(msg)
    period = period_match.group(0) if period_match else None

    # 14:30 / 14:30:20（兼容全角冒号）
    match = re.search(r'(?<!\d)([01]?\d|2[0-3])\s*[:：]\s*([0-5]\d)(?:\s*[:：]\s*([0-5]\d))?', msg)
    if match:
        hour = _apply_period(int(match.group(1)), period)
        if hour is None:
            return None
        second = int(match.group(3) or 0)
        precision = 'second' if match.group(3) is not None else 'minute'
        return hour, int(match.group(2)), second, precision, 1.0

    # 下午3点 / 晚上八点半 / 10点一刻 / 2时30分
    match = re.search(
        r'([零〇一二两三四五六七八九十\d]{1,3})\s*(?:点|时)'
        r'(?:(半)|(一刻)|(三刻)|([零〇一二两三四五六七八九十\d]{1,3})\s*分?)?',
        msg,
    )
    if match:
        raw_hour = _number(match.group(1))
        if raw_hour is None:
            return None
        hour = _apply_period(raw_hour, period)
        if hour is None:
            return None
        if match.group(2):
            minute = 30
        elif match.group(3):
            minute = 15
        elif match.group(4):
            minute = 45
        elif match.group(5):
            parsed_minute = _number(match.group(5))
            if parsed_minute is None or not 0 <= parsed_minute <= 59:
                return None
            minute = parsed_minute
        else:
            minute = 0
        return hour, minute, 0, 'minute', 1.0

    # 没有钟点的时段词使用稳定默认值，并通过 precision/confidence 标明这是约定值。
    defaults = {
        '凌晨': (2, 0), '早上': (8, 0), '早晨': (8, 0), '上午': (9, 0),
        '今早': (8, 0), '明早': (8, 0), '中午': (12, 0), '下午': (15, 0),
        '晚上': (20, 0), '晚间': (20, 0), '昨晚': (20, 0),
        '今晚': (20, 0), '明晚': (20, 0),
    }
    if period in defaults:
        hour, minute = defaults[period]
        return hour, minute, 0, 'period', 0.7
    return None


def extract_datetime_point(user_message: str, today: Optional[datetime] = None,
                           week_start: str = 'monday') -> DateTimePoint:
    """从中文文本提取一个日期时刻，失败时返回空 ``DateTimePoint``。"""
    if today is None:
        today = datetime.now()
    if week_start not in ('monday', 'sunday'):
        raise ValueError("week_start 必须是 'monday' 或 'sunday'")
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')

    msg = user_message.strip()
    if not msg:
        return DateTimePoint(recognition_status='no_time_phrase')

    try:
        time_parts = _resolve_time(msg)
        date_parts = _resolve_date(msg, today, week_start) if time_parts else None
    except (ValueError, OverflowError, KeyError, IndexError):
        time_parts = date_parts = None

    if time_parts and date_parts:
        hour, minute, second, precision, confidence = time_parts
        date_value, is_relative = date_parts
        value = date_value.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return DateTimePoint(
            datetime=value.strftime('%Y-%m-%d %H:%M:%S'),
            original_text=msg,
            label=msg,
            is_relative=is_relative,
            precision=precision,
            confidence=confidence,
        )

    has_time_phrase = bool(_PERIOD_PATTERN.search(msg) or re.search(r'\d\s*[:：点时]', msg))
    return DateTimePoint(
        original_text=msg,
        label='未识别',
        confidence=0.0,
        recognition_status='phrase_not_supported' if has_time_phrase else 'no_time_phrase',
    )
