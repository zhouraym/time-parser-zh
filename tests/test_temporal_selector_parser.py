"""事件顺序选择器及其与 DateRange 的组合测试。"""

from datetime import datetime

import pytest

from zh_time_parser import TemporalSelector, extract_date_range_v2, extract_temporal_selector

TODAY = datetime(2026, 8, 11)


@pytest.mark.parametrize(
    ('text', 'order', 'limit', 'offset'),
    [
        ('最近一次', 'latest', 1, 0),
        ('上一次', 'latest', 1, 0),
        ('最后一次', 'latest', 1, 0),
        ('第一次', 'earliest', 1, 0),
        ('最早一次', 'earliest', 1, 0),
        ('最近3次', 'latest', 3, 0),
        ('前3次', 'latest', 3, 0),
        ('倒数第二次', 'latest', 1, 1),
    ],
)
def test_requested_selectors(text, order, limit, offset):
    result = extract_temporal_selector(text, today=TODAY)
    assert isinstance(result, TemporalSelector)
    assert (result.order, result.limit, result.offset) == (order, limit, offset)
    assert result.date_range is None


def test_last_year_latest_one_combines_date_range():
    result = extract_temporal_selector('去年最近一次', today=TODAY)
    assert (result.order, result.limit, result.offset) == ('latest', 1, 0)
    assert result.date_range is not None
    assert (result.date_range.start, result.date_range.end) == ('2025-01-01', '2025-12-31')


def test_last_month_latest_three_combines_date_range():
    result = extract_temporal_selector('上个月最近3次', today=TODAY)
    assert (result.order, result.limit) == ('latest', 3)
    assert (result.date_range.start, result.date_range.end) == ('2026-07-01', '2026-07-31')


@pytest.mark.parametrize(
    'text',
    ['在上个月里最近3次', '最近3次在上个月范围内', '于去年期间最近3次'],
)
def test_date_context_connectors_are_normalized(text):
    result = extract_temporal_selector(text, today=TODAY)
    assert result.date_range is not None
    assert result.limit == 3


def test_arbitrary_business_text_does_not_block_selector():
    result = extract_temporal_selector('查询这个客户最近一次联系', today=TODAY)
    assert (result.order, result.limit) == ('latest', 1)
    assert result.date_range is None


def test_to_dict_expands_nested_date_range():
    result = extract_temporal_selector('去年最近一次', today=TODAY)
    payload = result.to_dict()
    assert payload['date_range']['start'] == '2025-01-01'


def test_rank_from_start_is_supported():
    result = extract_temporal_selector('第三次', today=TODAY)
    assert (result.order, result.limit, result.offset) == ('earliest', 1, 2)


def test_empty_result():
    result = extract_temporal_selector('查询客户记录', today=TODAY)
    assert not result
    assert result.recognition_status == 'no_time_phrase'


def test_date_range_core_is_unchanged():
    result = extract_date_range_v2('最近7天', today=TODAY)
    assert (result.start, result.end) == ('2026-08-05', '2026-08-11')
