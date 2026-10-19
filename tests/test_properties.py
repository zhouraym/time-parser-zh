"""基于生成式输入的解析不变量测试。"""

from datetime import datetime

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from zh_time_parser import (
    DateRange,
    extract_ambiguous_temporal,
    extract_comparison_range,
    extract_date_range_v2,
    extract_datetime_point,
    extract_datetime_range,
    extract_relative_time,
    extract_temporal_anchor,
    extract_temporal_boundary,
    extract_temporal_selector,
)

ANCHOR = datetime(2026, 8, 11, 12, 0)
ALPHABET = "年月日号天周季度上下前后今明昨早晚点时分至到从的内外左右0123456789一二三四五六七八九十ABC ,。"


@given(st.text(alphabet=ALPHABET, min_size=0, max_size=120))
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_arbitrary_text_never_causes_unexpected_exception(text: str) -> None:
    """任意字符串可以不识别，但不能让公开解析器崩溃。"""
    extract_date_range_v2(text, today=ANCHOR)
    extract_datetime_point(text, today=ANCHOR)
    extract_datetime_range(text, today=ANCHOR)
    extract_relative_time(text, anchor=ANCHOR)
    extract_temporal_selector(text, today=ANCHOR)
    extract_ambiguous_temporal(text)
    extract_temporal_boundary(text, today=ANCHOR)
    extract_temporal_anchor(text, today=ANCHOR)
    extract_comparison_range(text, today=ANCHOR)


@given(st.text(alphabet=ALPHABET, min_size=0, max_size=120))
@settings(max_examples=300, deadline=None)
def test_successful_date_ranges_are_valid_and_ordered(text: str) -> None:
    result = extract_date_range_v2(text, today=ANCHOR)
    if not result:
        return
    start = datetime.strptime(result.start, "%Y-%m-%d")
    end = datetime.strptime(result.end, "%Y-%m-%d")
    assert start <= end
    assert result.recognition_status == "ok"


@given(
    st.sampled_from(["最近", "近", "过去", "这"]),
    st.sampled_from(["几", "数"]),
    st.sampled_from(["天", "周", "个月", "年"]),
)
@settings(max_examples=80, deadline=None)
def test_vague_counts_never_resolve_to_concrete_range(prefix: str, count: str, unit: str) -> None:
    text = f"{prefix}{count}{unit}"
    ambiguous = extract_ambiguous_temporal(text)
    result = extract_date_range_v2(text, today=ANCHOR)
    assert ambiguous and ambiguous.value is None
    assert not result and result.recognition_status == "ambiguous"


@given(st.sampled_from(["上", "下"]), st.integers(min_value=2, max_value=20))
@settings(max_examples=40, deadline=None)
def test_repeated_month_shift_matches_calendar_algebra(direction: str, count: int) -> None:
    result = extract_date_range_v2(f"{direction * count}个月", today=ANCHOR)
    assert isinstance(result, DateRange) and result
    expected_index = ANCHOR.year * 12 + ANCHOR.month - 1
    expected_index += -count if direction == "上" else count
    expected_year, zero_based_month = divmod(expected_index, 12)
    assert result.start.startswith(f"{expected_year}-{zero_based_month + 1:02d}-01")
