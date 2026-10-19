"""跨测试模块共享的语义化时间锚点。"""

from datetime import datetime

import pytest


@pytest.fixture
def august_anchor() -> datetime:
    """普通月中锚点：2026-08-11（周二）。"""
    return datetime(2026, 8, 11, 12, 0)


@pytest.fixture
def sunday_anchor() -> datetime:
    """周日起始边界锚点：2026-05-24（周日）。"""
    return datetime(2026, 5, 24, 12, 0)


@pytest.fixture
def leap_day_anchor() -> datetime:
    """闰日锚点，用于日历平移边界。"""
    return datetime(2024, 2, 29, 12, 0)
