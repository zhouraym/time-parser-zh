"""独立库的公历语义、历史缺陷与零依赖导入回归测试。

所有日期预期均来自固定锚点和公历规则；已知问题保持正确预期，使用
strict xfail 提醒后续修复，不把错误结果作为库的公开契约。
"""

import calendar
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from time_parser_zh import extract_date_range_v2, extract_datetime_point


TODAY = datetime(2026, 10, 19, 15, 30)


@pytest.mark.parametrize("year", [1900, 2000, 2024, 2025, 2026, 2100])
@pytest.mark.parametrize("month", range(1, 13))
@pytest.mark.parametrize("style", ["{year}-{month:02}-{day:02}", "{year}/{month}/{day}", "{year}年{month}月{day}日"])
def test_gregorian_month_end(year: int, month: int, style: str) -> None:
    """验证平年、闰年及世纪年份的真实公历月末。

    Args:
        year: 公历年份。
        month: 月份。
        style: 日期表达格式。

    Returns:
        None。

    Raises:
        AssertionError: 解析结果与真实公历日期不同。
    """
    day = calendar.monthrange(year, month)[1]
    expression = style.format(year=year, month=month, day=day)
    expected = datetime(year, month, day).strftime("%Y-%m-%d")
    result = extract_date_range_v2(expression, today=TODAY)
    assert result.to_tuple() == (expected, expected)
    assert result.recognition_status == "ok"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="原实现仍丢失部分数量、相对年份或范围端点")
@pytest.mark.parametrize("expression, expected", [
    ("大前天", ("2026-10-16", "2026-10-16")),
    ("上上季度", ("2026-04-01", "2026-06-30")),
    ("2025年第一季度", ("2025-01-01", "2025-03-31")),
    ("去年第一季度", ("2025-01-01", "2025-03-31")),
    ("去年上半年", ("2025-01-01", "2025-06-30")),
    ("上上上个月1号", ("2026-07-01", "2026-07-01")),
    ("近十二个月", ("2025-10-19", "2026-10-19")),
    ("统计一下上上上周，按部门汇总", ("2026-09-28", "2026-10-04")),
    ("3月1日到15日", ("2026-03-01", "2026-03-15")),
    ("本周到昨天", (None, None)),
    ("3月到2月", (None, None)),
    ("Q3到Q1", (None, None)),
    ("2026年到2025年", (None, None)),
])
def test_known_calendar_regressions(
    expression: str, expected: tuple[str | None, str | None],
) -> None:
    """保存尚未满足的日历语义预期。

    Args:
        expression: 待支持或修复的时间表达。
        expected: 正确日期区间；无效区间使用空端点。

    Returns:
        None。

    Raises:
        AssertionError: 当前实现仍未满足正确语义。
    """
    assert extract_date_range_v2(expression, today=TODAY).to_tuple() == expected


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="原实现未完整校验时刻或保留日期前缀")
@pytest.mark.parametrize("expression, expected", [
    ("昨晚8点", "2026-10-18 20:00:00"),
    ("上上上周一下午3点", "2026-09-28 15:00:00"),
    ("本周一10点", "2026-10-19 10:00:00"),
    ("去年8月15日下午3点", "2025-08-15 15:00:00"),
    ("14:30:99", None),
    ("下午25:00", None),
    ("下午3:99", None),
])
def test_known_datetime_regressions(expression: str, expected: str | None) -> None:
    """保存完整日期前缀与非法钟点的正确预期。

    Args:
        expression: 待修复的日期时刻表达。
        expected: 正确时刻；非法输入为空。

    Returns:
        None。

    Raises:
        AssertionError: 时刻不符合输入语义。
    """
    assert extract_datetime_point(expression, today=TODAY).datetime == expected


def test_import_without_site_packages() -> None:
    """在禁用 site-packages 的隔离进程验证零依赖与公开接口。

    Args:
        无。

    Returns:
        None。

    Raises:
        AssertionError: 隔离导入或核心解析失败。
        subprocess.TimeoutExpired: 子进程超过三十秒未退出。
    """
    package_parent = Path(__file__).resolve().parents[1] / "src"
    code = """
import sys
from datetime import datetime
sys.path.insert(0, sys.argv[1])
import time_parser_zh
assert 'services' not in sys.modules
for name in time_parser_zh.__all__:
    assert hasattr(time_parser_zh, name), name
assert time_parser_zh.extract_date_range_v2('去年8月', today=datetime(2026, 10, 19)).to_tuple() == ('2025-08-01', '2025-08-31')
assert time_parser_zh.extract_datetime_point('明天下午3点', today=datetime(2026, 10, 19)).datetime == '2026-10-20 15:00:00'
"""
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code, str(package_parent)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr
