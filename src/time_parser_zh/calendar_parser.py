"""解析带年份的日历组合，保留年月日及范围端点之间的继承关系。

无年份的表达交给原有解析器；已识别但无效的组合返回失败结果，避免降级
为其中的月份、年份或“今天”，从而悄悄改变用户指定的日期。
"""

import re
from datetime import datetime
from typing import Optional, Tuple

from time_parser_zh.models import DateRange
from time_parser_zh.normalization import _fmt, _full_month_range, _parse_cn_number
from time_parser_zh.year_parser import _resolve_year_token

_YEAR = r'(?:\d{4}\s*年|\d{2}\s*年|今年|本年|这一年|这年|去年|上年|上一年|前年|明年|来年|下一年)'
_NUMBER = r'(?:\d+|[一二三四五六七八九十]+)'
_MONTH_DATE = rf'(?:{_YEAR}\s*(?:的\s*)?)?{_NUMBER}\s*月份?(?:\s*(?:{_NUMBER}\s*[日号]?|初|底|末))?'
_CONNECTOR = r'(?:到(?!期|达|店|处|手|账)|至(?!今)|~|～|—|-)'
_TODAY = r'(?:至今|到今天|到现在|到今|到目前|今天|今日|今儿|现在)'
_EXPRESSION = re.compile(
    rf'(?<![\d一二三四五六七八九十])(?P<left>{_MONTH_DATE})'
    rf'(?:\s*(?P<connector>{_CONNECTOR})\s*'
    rf'(?P<right>{_MONTH_DATE}|{_NUMBER}\s*[日号]|{_TODAY})'
    rf'|\s*(?P<to_today>{_TODAY}))?'
)
_ENDPOINT = re.compile(
    rf'(?:(?P<year>{_YEAR})\s*(?:的\s*)?)?'
    rf'(?P<month>{_NUMBER})\s*月份?'
    rf'(?:\s*(?P<day>{_NUMBER})\s*[日号]?|(?P<boundary>初|底|末))?'
)


def _resolve_calendar_endpoint(
    token: str, today: datetime, inherited_year: int, inherited_month: int,
) -> Tuple[datetime, datetime, str, bool]:
    """把一个日历端点解析为起止日期、粒度及相对性。

    Args:
        token: 年月日、年月、月日或省略年月的日号。
        today: 解析相对年份的基准时刻。
        inherited_year: 省略年份时继承的年份。
        inherited_month: 仅有日号时继承的月份。

    Returns:
        起始日期、结束日期、粒度和是否使用了相对年份。

    Raises:
        ValueError: 年份、月份、日号或端点格式无效。
    """
    match = _ENDPOINT.fullmatch(token)
    if not match:
        day_token = re.fullmatch(rf'({_NUMBER})\s*[日号]', token)
        day = _parse_cn_number(day_token.group(1)) if day_token else None
        if day is None:
            raise ValueError('日历端点无效')
        point = datetime(inherited_year, inherited_month, day)
        return point, point, 'day', False

    year = inherited_year
    relative = False
    if match.group('year'):
        year_token = re.sub(r'\s+', '', match.group('year'))
        resolved = _resolve_year_token(year_token, today)
        if resolved is None:
            raise ValueError('年份无效')
        year = resolved[0]
        relative = not year_token[0].isdigit()
    month = _parse_cn_number(match.group('month'))
    if month is None or not 1 <= month <= 12:
        raise ValueError('月份无效')
    start, end = _full_month_range(year, month)
    if match.group('day'):
        day = _parse_cn_number(match.group('day'))
        if day is None:
            raise ValueError('日号无效')
        start = end = datetime(year, month, day)
    elif match.group('boundary'):
        start = end = start if match.group('boundary') == '初' else end
    else:
        return start, end, 'month', relative
    return start, end, 'day', relative


def _parse_calendar_expression(msg: str, today: datetime) -> Optional[DateRange]:
    """优先解析带年份的完整日历表达，并阻止无效表达被局部规则截获。

    Args:
        msg: 用户原始消息。
        today: 相对日期的基准时刻。

    Returns:
        成功或明确失败的 DateRange；不含年份的表达返回 None。

    Raises:
        无。非法日期会转为 phrase_not_supported。
    """
    for match in _EXPRESSION.finditer(msg):
        if not re.search(_YEAR, match.group(0)):
            continue
        original = match.group(0)
        try:
            left = match.group('left')
            right = match.group('right')
            # “8月到2025年9月”与“2025年8月到9月”共享指定年份。
            year = today.year
            if not re.search(_YEAR, left) and right:
                right_year = re.match(_YEAR, right)
                if right_year:
                    resolved = _resolve_year_token(re.sub(r'\s+', '', right_year.group()), today)
                    if resolved is None:
                        raise ValueError('年份无效')
                    year = resolved[0]
            start, end, granularity, relative = _resolve_calendar_endpoint(
                left, today, year, today.month,
            )
            if match.group('to_today') or (right and re.fullmatch(_TODAY, right)):
                end = today
                relative = True
            elif right:
                _, end, right_granularity, right_relative = _resolve_calendar_endpoint(
                    right, today, start.year, start.month,
                )
                granularity = 'day' if 'day' in (granularity, right_granularity) else 'month'
                relative = relative or right_relative
            elif re.match(rf'\s*{_CONNECTOR}', msg[match.end():]):
                raise ValueError('范围结束端点不受支持')
            # 比较日历日期，忽略 today 所带时刻；不自动猜测跨年或交换端点。
            if start.date() > end.date():
                raise ValueError('起始日期晚于结束日期')
        except (ValueError, OverflowError):
            return DateRange(
                original_text=original, label='日历日期或范围无效', range_type='unknown',
                confidence=0.0, recognition_status='phrase_not_supported',
            )
        is_range = bool(right or match.group('to_today') or granularity == 'month')
        result = DateRange(
            _fmt(start), _fmt(end), range_type='range' if is_range else 'point',
            granularity=granularity, original_text=original, label=original,
            is_relative=relative,
        )
        if re.search(r'(?:到|截至|截止)\s*$', msg[:match.start()]):
            result.point = result.end
            result.boundary = 'end'
        return result
    return None
