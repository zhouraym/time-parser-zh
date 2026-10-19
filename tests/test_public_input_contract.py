"""公开 API 的无效输入与参数校验契约。"""

from datetime import datetime

import pytest

from zh_time_parser import (
    extract_ambiguous_temporal,
    extract_comparison_range,
    extract_date_range,
    extract_date_range_v2,
    extract_datetime_point,
    extract_datetime_range,
    extract_relative_time,
    extract_temporal_anchor,
    extract_temporal_boundary,
    extract_temporal_selector,
    parse_time_expression,
)

TODAY = datetime(2026, 8, 11, 12, 0)
INVALID_INPUTS = [None, 123, [], {}]


@pytest.mark.parametrize(
    'parser',
    [
        extract_date_range_v2,
        extract_datetime_point,
        extract_datetime_range,
        extract_relative_time,
        extract_temporal_selector,
        extract_ambiguous_temporal,
        extract_temporal_boundary,
        extract_temporal_anchor,
        extract_date_range,
        parse_time_expression,
    ],
)
@pytest.mark.parametrize('invalid', INVALID_INPUTS)
def test_public_parsers_reject_non_string_input(parser, invalid):
    with pytest.raises(TypeError):
        parser(invalid)


def test_comparison_preserves_none_as_no_comparison_contract():
    assert extract_comparison_range(None, today=TODAY) is None


@pytest.mark.parametrize('invalid', [123, [], {}])
def test_comparison_rejects_other_non_string_input(invalid):
    with pytest.raises(TypeError):
        extract_comparison_range(invalid, today=TODAY)


@pytest.mark.parametrize(
    ('parser', 'text'),
    [
        (extract_date_range_v2, '本周'),
        (extract_datetime_point, '下周三上午10点'),
        (extract_datetime_range, '本周一上午10点到本周五下午3点'),
        (extract_temporal_selector, '上周最近一次'),
        (extract_temporal_boundary, '下周以后'),
        (extract_temporal_anchor, '在昨天的时候'),
        (extract_comparison_range, '本周同比'),
    ],
)
def test_week_aware_parsers_reject_invalid_week_start(parser, text):
    with pytest.raises(ValueError):
        parser(text, today=TODAY, week_start='friday')
