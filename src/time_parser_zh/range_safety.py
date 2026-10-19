"""跨解析器共享的范围连接符安全检查。"""

import re

# 排除“到期/到达”等普通词中的“到”；长连接词必须放在单字“到”之前。
_RANGE_CONNECTOR_PATTERN = re.compile(
    r'直到|直至|截止到|截至|截止|(?<![直截])到(?!期|达|店|处|手|账)|至|~'
)


def _has_multiple_range_connectors(text: str) -> bool:
    """同句有多个范围连接符时，单区间模型不能安全决定结合顺序。"""
    return sum(1 for _ in _RANGE_CONNECTOR_PATTERN.finditer(text)) > 1
