"""as-of 评估锚点与筛选 Boundary 的语义隔离测试。"""

from datetime import datetime

from zh_time_parser import (
    TemporalAnchor,
    extract_date_range_v2,
    extract_temporal_anchor,
    extract_temporal_boundary,
)

TODAY = datetime(2026, 8, 11, 12, 0)


def test_yesterday_as_of_anchor():
    result = extract_temporal_anchor('在昨天的时候', today=TODAY)
    assert isinstance(result, TemporalAnchor)
    assert result.mode == 'as_of'
    assert result.value == '2026-08-10'
    assert result.value_type == 'date'
    assert result.is_future is False


def test_month_end_as_of_anchor_in_full_business_sentence():
    result = extract_temporal_anchor('到这个月底的时候客户欠款超期金额是多少', today=TODAY)
    assert result.mode == 'as_of'
    assert result.value == '2026-08-31'
    assert result.value_type == 'date'
    assert result.is_future is True


def test_explicit_datetime_anchor():
    result = extract_temporal_anchor('在昨天下午3点的时候查看状态', today=TODAY)
    assert result.value == '2026-08-10 15:00:00'
    assert result.value_type == 'datetime'


def test_boundary_expression_is_not_anchor():
    result = extract_temporal_anchor('截至昨天', today=TODAY)
    assert not result
    boundary = extract_temporal_boundary('截至昨天', today=TODAY)
    assert (boundary.operator, boundary.value) == ('<=', '2026-08-10')


def test_period_without_specific_anchor_is_not_guessed():
    result = extract_temporal_anchor('在下个月的时候', today=TODAY)
    assert not result
    assert result.recognition_status == 'phrase_not_supported'


def test_model_helpers():
    result = extract_temporal_anchor('在昨天的时候', today=TODAY)
    assert repr(result) == 'TemporalAnchor(mode="as_of", value="2026-08-10")'
    assert result.to_dict()['mode'] == 'as_of'


def test_existing_date_range_behavior_is_unchanged():
    """独立入口不改变旧 DateRange 对同一文本的既有结果。"""
    result = extract_date_range_v2('到这个月底的时候', today=TODAY)
    assert (result.start, result.end) == ('2026-08-01', '2026-08-31')
    assert result.point == '2026-08-31'


def test_existing_date_range_core_regression():
    result = extract_date_range_v2('最近7天', today=TODAY)
    assert (result.start, result.end) == ('2026-08-05', '2026-08-11')
