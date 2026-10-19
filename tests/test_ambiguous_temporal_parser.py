"""模糊时间只识别语义、不猜具体值的测试。"""

from datetime import datetime

import pytest

from zh_time_parser import AmbiguousTemporal, extract_ambiguous_temporal, extract_date_range_v2

TODAY = datetime(2026, 8, 11)


@pytest.mark.parametrize(
    ('text', 'temporal_type', 'direction', 'unit'),
    [
        ('最近几天', 'date_range', 'recent', 'day'),
        ('最近一段时间', 'date_range', 'recent', None),
        ('前段时间', 'date_range', 'past', None),
        ('过几天', 'relative_time', 'future', 'day'),
        ('晚一点', 'relative_time', 'future', None),
        ('月底左右', 'datetime_point', 'around', 'month'),
        ('近期', 'date_range', 'recent', None),
        ('过段时间', 'relative_time', 'future', None),
        ('不久以后', 'relative_time', 'future', None),
        ('很早以前', 'date_range', 'past', None),
        ('前些日子', 'date_range', 'past', 'day'),
        ('这阵子', 'date_range', 'recent', None),
        ('月初前后', 'datetime_point', 'around', 'month'),
    ],
)
def test_requested_ambiguous_expressions(text, temporal_type, direction, unit):
    result = extract_ambiguous_temporal(text)
    assert isinstance(result, AmbiguousTemporal)
    assert result.status == 'ambiguous'
    assert result.type == temporal_type
    assert result.direction == direction
    assert result.unit == unit
    assert result.value is None


def test_example_payload():
    result = extract_ambiguous_temporal('最近几天')
    assert result.to_dict() == {
        'type': 'date_range',
        'status': 'ambiguous',
        'direction': 'recent',
        'unit': 'day',
        'value': None,
        'original_text': '最近几天',
        'matched_text': '最近几天',
        'confidence': 1.0,
    }


@pytest.mark.parametrize('text', ['最近几天', '最近一段时间', '前段时间', '月底左右', '近期'])
def test_date_range_refuses_to_guess(text):
    result = extract_date_range_v2(text, today=TODAY)
    assert not result
    assert result.start is None and result.end is None
    assert result.recognition_status == 'ambiguous'
    assert 'extract_ambiguous_temporal' in result.label


def test_specific_value_still_uses_date_range():
    result = extract_date_range_v2('最近7天', today=TODAY)
    assert (result.start, result.end) == ('2026-08-05', '2026-08-11')
    assert result.recognition_status == 'ok'


@pytest.mark.parametrize(
    ('text', 'temporal_type', 'direction', 'unit'),
    [
        ('最近几周', 'date_range', 'recent', 'week'),
        ('最近几个月', 'date_range', 'recent', 'month'),
        ('近几年', 'date_range', 'recent', 'year'),
        ('前几年', 'date_range', 'past', 'year'),
        ('过几小时', 'relative_time', 'future', 'hour'),
        ('再过几分钟', 'relative_time', 'future', 'minute'),
    ],
)
def test_vague_count_never_becomes_two(text, temporal_type, direction, unit):
    ambiguous = extract_ambiguous_temporal(text)
    assert (ambiguous.type, ambiguous.direction, ambiguous.unit, ambiguous.value) == (
        temporal_type, direction, unit, None,
    )


@pytest.mark.parametrize('text', ['最近几周', '最近几个月', '近几年', '前几年'])
def test_vague_count_is_blocked_from_date_range(text):
    result = extract_date_range_v2(text, today=TODAY)
    assert not result
    assert result.recognition_status == 'ambiguous'


def test_unrelated_text_returns_empty_ambiguous_model():
    result = extract_ambiguous_temporal('查询客户记录')
    assert not result
    assert result.status == 'no_time_phrase'
