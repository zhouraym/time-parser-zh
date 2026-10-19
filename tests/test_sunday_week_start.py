"""week_start='sunday' 在核心与新增解析器中的回归矩阵。"""

from datetime import datetime

from zh_time_parser import (
    extract_date_range_v2,
    extract_datetime_point,
    extract_datetime_range,
    extract_temporal_boundary,
)


def test_this_week_with_sunday_start(sunday_anchor: datetime) -> None:
    result = extract_date_range_v2("本周", today=sunday_anchor, week_start="sunday")
    assert (result.start, result.end) == ("2026-05-24", "2026-05-30")


def test_weekday_range_with_sunday_start(sunday_anchor: datetime) -> None:
    result = extract_date_range_v2("本周一到周五", today=sunday_anchor, week_start="sunday")
    assert (result.start, result.end) == ("2026-05-25", "2026-05-29")
    assert result.week_start == "sunday"


def test_week_to_today_with_sunday_start(sunday_anchor: datetime) -> None:
    result = extract_date_range_v2("本周至今", today=sunday_anchor, week_start="sunday")
    assert (result.start, result.end) == ("2026-05-24", "2026-05-24")


def test_datetime_point_weekday_with_sunday_start(sunday_anchor: datetime) -> None:
    result = extract_datetime_point("下周三上午10点", today=sunday_anchor, week_start="sunday")
    assert result.datetime == "2026-06-03 10:00:00"


def test_datetime_range_with_sunday_start(sunday_anchor: datetime) -> None:
    result = extract_datetime_range(
        "本周一上午10点到本周五下午3点",
        today=sunday_anchor,
        week_start="sunday",
    )
    assert result.start == "2026-05-25 10:00:00"
    assert result.end == "2026-05-29 15:00:00"


def test_boundary_next_week_with_sunday_start(sunday_anchor: datetime) -> None:
    result = extract_temporal_boundary("下周以后", today=sunday_anchor, week_start="sunday")
    assert (result.operator, result.value) == (">=", "2026-05-31")
