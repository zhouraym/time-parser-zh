"""识别模糊时间意图，但不擅自补齐具体日期或时长。"""

import re
from typing import Optional, Tuple

from time_parser_zh.models import AmbiguousTemporal

_VAGUE_UNIT_MAP = {
    '分钟': 'minute', '分': 'minute',
    '小时': 'hour', '钟头': 'hour',
    '天': 'day', '日': 'day',
    '周': 'week', '星期': 'week', '礼拜': 'week',
    '个月': 'month', '月': 'month',
    '年': 'year',
}
_VAGUE_UNIT = r'分钟|分|小时|钟头|天|日|周|星期|礼拜|个月|月|年'

# pattern, type, direction, unit
_RULES: Tuple[Tuple[re.Pattern, str, str, Optional[str]], ...] = (
    (re.compile(r'这\s*(?:几|些)\s*天'), 'date_range', 'recent', 'day'),
    (re.compile(r'最近\s*(?:一|这)\s*段时间|最近一阵子'), 'date_range', 'recent', None),
    (re.compile(r'前\s*(?:一|这)?\s*段时间|前阵子'), 'date_range', 'past', None),
    (re.compile(r'过\s*(?:一)?\s*段时间|再过一阵(?:子)?|不久以后|很久以后'),
     'relative_time', 'future', None),
    (re.compile(r'很早以前|很久以前'), 'date_range', 'past', None),
    (re.compile(r'前些日子|前些天'), 'date_range', 'past', 'day'),
    (re.compile(r'这阵子|这段时间'), 'date_range', 'recent', None),
    (re.compile(r'晚\s*(?:一)?点'), 'relative_time', 'future', None),
    (re.compile(r'月底\s*(?:左右|前后)'), 'datetime_point', 'around', 'month'),
    (re.compile(r'月初\s*(?:左右|前后)'), 'datetime_point', 'around', 'month'),
    (re.compile(r'年底\s*(?:左右|前后)'), 'datetime_point', 'around', 'year'),
    (re.compile(r'近期'), 'date_range', 'recent', None),
)


def extract_ambiguous_temporal(user_message: str) -> AmbiguousTemporal:
    """返回模糊时间的结构化语义；不解析出任何具体日期或数值。"""
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')
    msg = user_message.strip()
    if not msg:
        return AmbiguousTemporal()

    # 含“几/数”的数量表达统一保留为 value=None，覆盖所有常用时间单位。
    match = re.search(rf'(?:最近|近|过去|这)\s*(?:几|数)\s*(?P<unit>{_VAGUE_UNIT})', msg)
    if match:
        return AmbiguousTemporal(
            type='date_range', status='ambiguous', direction='recent',
            unit=_VAGUE_UNIT_MAP[match.group('unit')], value=None,
            original_text=msg, matched_text=match.group(0),
        )
    match = re.search(rf'前\s*(?:几|数)\s*(?P<unit>{_VAGUE_UNIT})', msg)
    if match:
        return AmbiguousTemporal(
            type='date_range', status='ambiguous', direction='past',
            unit=_VAGUE_UNIT_MAP[match.group('unit')], value=None,
            original_text=msg, matched_text=match.group(0),
        )
    match = re.search(rf'(?:再\s*)?过\s*(?:几|数)\s*(?P<unit>{_VAGUE_UNIT})', msg)
    if match:
        return AmbiguousTemporal(
            type='relative_time', status='ambiguous', direction='future',
            unit=_VAGUE_UNIT_MAP[match.group('unit')], value=None,
            original_text=msg, matched_text=match.group(0),
        )

    for pattern, temporal_type, direction, unit in _RULES:
        match = pattern.search(msg)
        if match:
            return AmbiguousTemporal(
                type=temporal_type,
                status='ambiguous',
                direction=direction,
                unit=unit,
                value=None,
                original_text=msg,
                matched_text=match.group(0),
            )
    return AmbiguousTemporal(original_text=msg, confidence=0.0)
