"""带时刻区间、单侧边界及日期型旧系统投影测试。"""

from datetime import datetime

import pytest

from zh_time_parser import DateTimeRange, extract_date_range_v2, extract_datetime_range

TODAY = datetime(2026, 8, 11, 12, 0)


def test_range_ending_yesterday_noon():
    result = extract_datetime_range('8月1日至昨天中午', today=TODAY)
    assert isinstance(result, DateTimeRange)
    assert result.start == '2026-08-01 00:00:00'
    assert result.end == '2026-08-10 12:00:00'
    assert result.to_date_tuple() == ('2026-08-01', '2026-08-10')
    assert result.precision_lost is True


def test_end_boundary_only():
    result = extract_datetime_range('直到昨天中午', today=TODAY)
    assert result.start is None
    assert result.end == '2026-08-10 12:00:00'
    assert result.to_date_tuple() == (None, '2026-08-10')
    assert result.precision_lost is True


def test_plain_date_range_has_no_precision_loss():
    result = extract_datetime_range('8-1至8-10', today=TODAY)
    assert result.start == '2026-08-01 00:00:00'
    assert result.end == '2026-08-10 23:59:59'
    assert result.to_date_tuple() == ('2026-08-01', '2026-08-10')
    assert result.precision_lost is False


def test_completed_days_projection_avoids_over_including_afternoon():
    result = extract_datetime_range('8月1日至昨天中午', today=TODAY)
    assert result.to_date_tuple(policy='completed_days') == ('2026-08-01', '2026-08-09')


def test_reject_lossy_policy():
    result = extract_datetime_range('8月1日至昨天中午', today=TODAY)
    with pytest.raises(ValueError, match='无法无损投影'):
        result.to_date_tuple(policy='reject_lossy')


def test_full_datetime_range():
    result = extract_datetime_range('今天上午10点到今天下午3点', today=TODAY)
    assert result.start == '2026-08-11 10:00:00'
    assert result.end == '2026-08-11 15:00:00'
    assert result.precision_lost is True


def test_date_range_core_is_still_unchanged():
    result = extract_date_range_v2('最近7天', today=TODAY)
    assert (result.start, result.end) == ('2026-08-05', '2026-08-11')
