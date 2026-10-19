"""
time-parser-zh —— 中文自然语言时间表达解析器。

把"昨天"、"上个月"、"最近7天"、"Q1"、"2026-04-01 至 2026-04-30"等中文时间表达
解析成具体的日期范围。纯 Python 标准库实现，无第三方依赖。

基本用法：

    >>> from zh_time_parser import extract_date_range_v2
    >>> from datetime import datetime
    >>> r = extract_date_range_v2("上个月", today=datetime(2026, 5, 24))
    >>> r.start, r.end
    ('2026-04-01', '2026-04-30')

传入固定的 today 可获得可重复的结果：

    >>> from datetime import datetime
    >>> r = extract_date_range_v2("上个月", today=datetime(2026, 5, 24))
    >>> r.start, r.end
    ('2026-04-01', '2026-04-30')

解析同比/环比时使用 extract_comparison_range()，它返回**两个**区间：

    >>> from zh_time_parser import extract_comparison_range
    >>> c = extract_comparison_range("Q2同比", today=datetime(2026, 8, 9))
    >>> c.current.start, c.current.end
    ('2026-04-01', '2026-06-30')
    >>> c.comparison.start, c.comparison.end
    ('2025-04-01', '2025-06-30')
"""

from zh_time_parser.ambiguous_temporal_parser import extract_ambiguous_temporal
from zh_time_parser.comparison_parser import extract_comparison_range
from zh_time_parser.date_parser import (
    DateRange,
    extract_date_range,
    extract_date_range_v2,
    parse_time_expression,
)
from zh_time_parser.datetime_parser import extract_datetime_point
from zh_time_parser.datetime_range_parser import extract_datetime_range
from zh_time_parser.models import (
    AmbiguousTemporal,
    ComparisonRange,
    DateTimePoint,
    DateTimeRange,
    RelativeTime,
    TemporalAnchor,
    TemporalBoundary,
    TemporalSelector,
)
from zh_time_parser.relative_time_parser import extract_relative_time
from zh_time_parser.temporal_anchor_parser import extract_temporal_anchor
from zh_time_parser.temporal_boundary_parser import extract_temporal_boundary
from zh_time_parser.temporal_selector_parser import extract_temporal_selector

# 单一版本来源：setuptools 从本属性生成包元数据。
__version__ = "1.0.0"

__all__ = [
    "DateRange",
    "DateTimePoint",
    "DateTimeRange",
    "RelativeTime",
    "TemporalSelector",
    "AmbiguousTemporal",
    "TemporalBoundary",
    "TemporalAnchor",
    "ComparisonRange",
    "extract_date_range_v2",
    "extract_datetime_point",
    "extract_datetime_range",
    "extract_relative_time",
    "extract_temporal_selector",
    "extract_ambiguous_temporal",
    "extract_temporal_boundary",
    "extract_temporal_anchor",
    "extract_date_range",
    "extract_comparison_range",
    "parse_time_expression",
    "__version__",
]
