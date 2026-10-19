"""DateRange 截止点语义的公共 API 回归矩阵。"""

from datetime import datetime
from typing import Tuple

import pytest

from zh_time_parser import extract_date_range_v2


@pytest.mark.parametrize(
    ('text', 'start', 'end', 'point', 'granularity'),
    [
        ('到2027年末', '2027-01-01', '2027-12-31', '2027-12-31', 'year'),
        ('截至12月底', '2026-12-01', '2026-12-31', '2026-12-31', 'month'),
        ('到2026年8月31日', '2026-08-31', '2026-08-31', '2026-08-31', 'day'),
        ('截至8月31日', '2026-08-31', '2026-08-31', '2026-08-31', 'day'),
        ('到本月15号', '2026-08-15', '2026-08-15', '2026-08-15', 'day'),
        ('截至去年底', '2025-01-01', '2025-12-31', '2025-12-31', 'year'),
        ('截至今年底', '2026-01-01', '2026-12-31', '2026-12-31', 'year'),
        ('截至明年底', '2027-01-01', '2027-12-31', '2027-12-31', 'year'),
        ('截至上上月底', '2026-06-01', '2026-06-30', '2026-06-30', 'month'),
        ('截至上个月底', '2026-07-01', '2026-07-31', '2026-07-31', 'month'),
        ('截至下个月底', '2026-09-01', '2026-09-30', '2026-09-30', 'month'),
        ('截至月底', '2026-08-01', '2026-08-31', '2026-08-31', 'month'),
        ('本年底', '2026-01-01', '2026-12-31', '2026-12-31', 'year'),
    ],
)
def test_date_range_as_of_points(
    text: str,
    start: str,
    end: str,
    point: str,
    granularity: str,
    august_anchor: datetime,
) -> None:
    result = extract_date_range_v2(text, today=august_anchor)
    assert (result.start, result.end, result.point) == (start, end, point)
    assert (result.boundary, result.granularity) == ('end', granularity)


@pytest.mark.parametrize(
    'text',
    [
        '截至2026年2月30日',
        '截至2月30日',
        '截至本月32号',
        '截至13月底',
    ],
)
def test_invalid_as_of_points_are_not_fabricated(text: str, august_anchor: datetime) -> None:
    result = extract_date_range_v2(text, today=august_anchor)
    assert not result
    assert result.start is None and result.end is None and result.point is None


@pytest.mark.parametrize(
    ('anchor', 'text', 'expected'),
    [
        (datetime(2026, 1, 15), '截至上上月底', ('2025-11-01', '2025-11-30')),
        (datetime(2026, 1, 15), '截至上个月底', ('2025-12-01', '2025-12-31')),
        (datetime(2026, 12, 15), '截至下个月底', ('2027-01-01', '2027-01-31')),
    ],
)
def test_relative_month_end_crosses_years(
    anchor: datetime,
    text: str,
    expected: Tuple[str, str],
) -> None:
    result = extract_date_range_v2(text, today=anchor)
    assert (result.start, result.end) == expected
