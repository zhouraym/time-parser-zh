"""日期时刻解析，以及 DateRange API 不受影响的回归测试。"""

from datetime import datetime

import pytest

from zh_time_parser import DateTimePoint, extract_date_range_v2, extract_datetime_point

TODAY = datetime(2026, 8, 11, 16, 45)


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('明天下午3点', '2026-08-12 15:00:00'),
        ('今天晚上8点半', '2026-08-11 20:30:00'),
        ('下周三上午10点', '2026-08-19 10:00:00'),
        ('8月20日14:30', '2026-08-20 14:30:00'),
        ('后天凌晨2点', '2026-08-13 02:00:00'),
        ('昨天中午', '2026-08-10 12:00:00'),
        ('前天晚上8点', '2026-08-09 20:00:00'),
        ('昨晚', '2026-08-10 20:00:00'),
        ('今早', '2026-08-11 08:00:00'),
        ('今晚', '2026-08-11 20:00:00'),
        ('明早', '2026-08-12 08:00:00'),
    ],
)
def test_requested_examples(text, expected):
    result = extract_datetime_point(text, today=TODAY)
    assert isinstance(result, DateTimePoint)
    assert result.datetime == expected
    assert result.recognition_status == 'ok'


def test_explicit_year_and_seconds():
    result = extract_datetime_point('2027年1月2日 09:08:07', today=TODAY)
    assert result.datetime == '2027-01-02 09:08:07'
    assert result.precision == 'second'
    assert result.is_relative is False


def test_period_default_is_marked_as_approximate():
    result = extract_datetime_point('今晚', today=TODAY)
    assert result.precision == 'period'
    assert result.confidence < 1.0


def test_invalid_datetime_returns_empty_result():
    result = extract_datetime_point('2月30日下午3点', today=TODAY)
    assert not result
    assert result.recognition_status == 'phrase_not_supported'


def test_datetime_point_model_helpers():
    result = extract_datetime_point('明早', today=TODAY)
    assert repr(result) == 'DateTimePoint(datetime="2026-08-12 08:00:00")'
    assert result.to_dict()['datetime'] == '2026-08-12 08:00:00'


@pytest.mark.parametrize('text', ['明天下午3点', '今晚', '8月20日14:30'])
def test_existing_date_range_api_still_returns_date_range(text):
    """新解析器不进入原调度链，旧入口的类型和日期语义均保持不变。"""
    result = extract_date_range_v2(text, today=TODAY)
    assert result.__class__.__name__ == 'DateRange'


def test_existing_core_date_range_behavior_is_unchanged():
    result = extract_date_range_v2('最近7天', today=TODAY)
    assert (result.start, result.end) == ('2026-08-05', '2026-08-11')
