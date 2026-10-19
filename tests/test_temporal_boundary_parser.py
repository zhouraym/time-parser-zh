"""Deadline / Boundary 单侧比较语义测试。"""

from datetime import datetime

import pytest

from zh_time_parser import TemporalBoundary, extract_date_range_v2, extract_temporal_boundary

TODAY = datetime(2026, 8, 11, 12, 0)  # 周二


@pytest.mark.parametrize(
    ('text', 'operator', 'value', 'value_type'),
    [
        ('周五之前', '<', '2026-08-14', 'date'),
        ('月底以前', '<', '2026-08-31', 'date'),
        ('三天以内', '<=', '2026-08-14 12:00', 'datetime'),
        ('两小时内', '<=', '2026-08-11 14:00', 'datetime'),
        ('从明天开始', '>=', '2026-08-12', 'date'),
        ('下周以后', '>=', '2026-08-17', 'date'),
        ('截至月底', '<=', '2026-08-31', 'date'),
        ('最迟周三', '<=', '2026-08-12', 'date'),
    ],
)
def test_requested_boundaries(text, operator, value, value_type):
    result = extract_temporal_boundary(text, today=TODAY)
    assert isinstance(result, TemporalBoundary)
    assert (result.operator, result.value, result.value_type) == (operator, value, value_type)
    assert result.recognition_status == 'ok'


@pytest.mark.parametrize(
    ('text', 'duration_value', 'duration_unit'),
    [('三天以内', 3, 'day'), ('两小时内', 2, 'hour')],
)
def test_duration_boundary_preserves_relative_time(text, duration_value, duration_unit):
    result = extract_temporal_boundary(text, today=TODAY)
    assert result.duration is not None
    assert (result.duration.value, result.duration.unit) == (duration_value, duration_unit)
    assert result.duration.direction == 'future'


def test_explicit_datetime_boundary():
    result = extract_temporal_boundary('最迟明天下午3点', today=TODAY)
    assert result.operator == '<='
    assert result.value == '2026-08-12 15:00'
    assert result.value_type == 'datetime'


def test_model_helpers():
    result = extract_temporal_boundary('周五之前', today=TODAY)
    assert repr(result) == 'TemporalBoundary(operator="<", value="2026-08-14")'
    assert result.to_dict()['operator'] == '<'


def test_unrecognized_returns_empty_model():
    result = extract_temporal_boundary('查询客户记录', today=TODAY)
    assert not result
    assert result.recognition_status == 'no_time_phrase'


def test_existing_date_range_core_is_unchanged():
    result = extract_date_range_v2('最近7天', today=TODAY)
    assert (result.start, result.end) == ('2026-08-05', '2026-08-11')
