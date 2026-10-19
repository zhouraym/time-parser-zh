"""防止超长输入触发灾难性正则回溯或静默部分匹配。"""

from datetime import datetime

import pytest

from zh_time_parser import extract_date_range_v2, extract_datetime_range

ANCHOR = datetime(2026, 8, 11, 12, 0)


@pytest.mark.timeout(2)
@pytest.mark.parametrize(
    "text",
    [
        "普通业务文本" * 5000,
        "从3月" + "到5月" * 2000 + "到昨天",
        ("上" * 1000) + "个月",
        ("2026-01-01至" * 1000) + "2026-12-31",
    ],
    ids=["plain-text", "many-connectors", "many-month-shifts", "many-explicit-ranges"],
)
def test_pathological_date_inputs_finish_within_budget(text: str) -> None:
    extract_date_range_v2(text, today=ANCHOR)


@pytest.mark.timeout(2)
def test_pathological_datetime_range_finishes_within_budget() -> None:
    result = extract_datetime_range("从3月" + "到5月" * 2000 + "到昨天", today=ANCHOR)
    assert not result
