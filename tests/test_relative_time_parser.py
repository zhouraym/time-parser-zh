"""锚点 + 时长形式的 RelativeTime 解析测试。"""

from datetime import datetime

import pytest

from zh_time_parser import RelativeTime, extract_date_range_v2, extract_relative_time

ANCHOR = datetime(2026, 8, 11, 12, 0)


@pytest.mark.parametrize(
    ('text', 'value', 'unit', 'direction', 'resolved_at'),
    [
        ('半小时后', 30, 'minute', 'future', '2026-08-11 12:30'),
        ('10分钟后', 10, 'minute', 'future', '2026-08-11 12:10'),
        ('3天后', 3, 'day', 'future', '2026-08-14 12:00'),
        ('两周前', 2, 'week', 'past', '2026-07-28 12:00'),
        ('一个月以后', 1, 'month', 'future', '2026-09-11 12:00'),
        ('过两小时', 2, 'hour', 'future', '2026-08-11 14:00'),
        ('再过三天', 3, 'day', 'future', '2026-08-14 12:00'),
    ],
)
def test_requested_examples(text, value, unit, direction, resolved_at):
    result = extract_relative_time(text, anchor=ANCHOR)
    assert isinstance(result, RelativeTime)
    assert (result.value, result.unit, result.direction, result.resolved_at) == (
        value,
        unit,
        direction,
        resolved_at,
    )
    assert result.recognition_status == 'ok'


def test_month_end_uses_calendar_arithmetic():
    result = extract_relative_time('一个月后', anchor=datetime(2026, 1, 31, 9, 30))
    assert result.resolved_at == '2026-02-28 09:30'


def test_month_past_crosses_year():
    result = extract_relative_time('两个月前', anchor=datetime(2026, 1, 15, 9, 30))
    assert result.resolved_at == '2025-11-15 09:30'


def test_anchor_seconds_are_normalized_to_model_precision():
    result = extract_relative_time('10分钟后', anchor=datetime(2026, 8, 11, 12, 0, 45, 123))
    assert result.resolved_at == '2026-08-11 12:10'


def test_model_helpers():
    result = extract_relative_time('半小时后', anchor=ANCHOR)
    assert repr(result) == (
        'RelativeTime(value=30, unit="minute", direction="future", '
        'resolved_at="2026-08-11 12:30")'
    )
    assert result.to_dict()['value'] == 30
    assert bool(result)


def test_unrecognized_expression_returns_empty_model():
    result = extract_relative_time('过一会儿', anchor=ANCHOR)
    assert not result
    assert result.recognition_status == 'no_time_phrase'


@pytest.mark.parametrize('text', ['半小时后', '3天后', '两周前', '一个月以后'])
def test_date_range_api_type_is_unchanged(text):
    result = extract_date_range_v2(text, today=ANCHOR)
    assert result.__class__.__name__ == 'DateRange'


def test_date_range_core_regression():
    result = extract_date_range_v2('最近7天', today=ANCHOR)
    assert (result.start, result.end) == ('2026-08-05', '2026-08-11')
