"""自然月重复位移、月份链及季度后月份测试。"""

from datetime import datetime

import pytest

from zh_time_parser import extract_date_range_v2

TODAY = datetime(2026, 8, 11)


@pytest.mark.parametrize(
    ('text', 'start', 'end'),
    [
        ('上上月', '2026-06-01', '2026-06-30'),
        ('上上上个月', '2026-05-01', '2026-05-31'),
        ('下下下个月', '2026-11-01', '2026-11-30'),
        ('上个月的下个月', '2026-08-01', '2026-08-11'),
        ('上上个月的下个月', '2026-07-01', '2026-07-31'),
        ('上个月的下下个月', '2026-09-01', '2026-09-30'),
        ('一季度后的下一个月', '2026-04-01', '2026-04-30'),
        ('一季度后的一个月', '2026-04-01', '2026-04-30'),
        ('Q4后的一个月', '2027-01-01', '2027-01-31'),
        ('2025年第四季度后的一个月', '2026-01-01', '2026-01-31'),
        ('上季度后的一个月', '2026-07-01', '2026-07-31'),
    ],
)
def test_composed_month_shift(text, start, end):
    result = extract_date_range_v2(text, today=TODAY)
    assert (result.start, result.end) == (start, end)
    assert result.granularity == 'month'
    assert result.recognition_status == 'ok'


def test_explicit_quarter_year_is_not_relative():
    result = extract_date_range_v2('2025年第四季度后的一个月', today=TODAY)
    assert result.is_relative is False


def test_repeated_month_crosses_year():
    result = extract_date_range_v2('上上上个月', today=datetime(2026, 2, 10))
    assert (result.start, result.end) == ('2025-11-01', '2025-11-30')


def test_existing_simple_month_behavior_is_unchanged():
    result = extract_date_range_v2('上个月', today=TODAY)
    assert (result.start, result.end) == ('2026-07-01', '2026-07-31')
