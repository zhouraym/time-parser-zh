"""比较解析器误识别回归测试。

覆盖本次修复的四类问题：
1. 单独的「环」不再误触发环比（环境/环节/循环/环岛）。
2. 默认比较周期仅用于独立默认表达；剥离后仍有实质时间文本但无法解析 → None。
3. 同时含「同比」与「环比」→ None（单次调用只支持一种比较类型）。
4. extract_date_range_v2 对明确比较表达返回 phrase_not_supported，不误解为普通区间。
"""

from datetime import datetime

import pytest

from zh_time_parser import (
    ComparisonRange,
    DateRange,
    extract_comparison_range,
    extract_date_range_v2,
)
from zh_time_parser.comparison_parser import _detect_comparison_type

TODAY = datetime(2026, 8, 9)


# ─────────────────────────────────────────────────────────
# 一、收紧比较词识别：单独的「环」不得触发环比
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "环境数据",
    "环节分析",
    "循环统计",
    "环岛记录",
])
def test_lone_huan_not_recognized(text):
    """独立的「环」字（环境/环节/循环/环岛）不应被识别为环比。"""
    assert extract_comparison_range(text, today=TODAY) is None
    # 检测层也不应给出比较类型
    assert _detect_comparison_type(text) is None
    # 普通日期解析也不应受影响（这些不是日期表达，保持原有 no_time_phrase 行为）
    assert extract_date_range_v2(text, today=TODAY).recognition_status in (
        'no_time_phrase', 'phrase_not_supported'
    )


# ─────────────────────────────────────────────────────────
# 二、限制默认比较周期的使用条件
# ─────────────────────────────────────────────────────────

# 这些含比较词、但剥离后仍有实质时间文本却无法解析 → 必须返回 None
@pytest.mark.parametrize("text", [
    "前阵子同比",
    "前阵子环比",
    "不支持的时间同比",
    "不支持的时间环比",
    "第五季度同比",
    "H3环比",
])
def test_unparseable_period_no_default(text):
    assert extract_comparison_range(text, today=TODAY) is None


# 这些独立默认表达（可带少量噪声/询问后缀）应正常返回默认周期
@pytest.mark.parametrize("text,expect_type", [
    ("同比", "yoy"),
    ("环比", "previous_period"),
    ("去年同期", "yoy"),
    ("上年同期", "yoy"),
    ("同期", "yoy"),
    ("同比是多少", "yoy"),
    ("环比情况", "previous_period"),
    ("看一下同比", "yoy"),
    ("去年同期怎么样", "yoy"),
])
def test_standalone_default_ok(text, expect_type):
    r = extract_comparison_range(text, today=TODAY)
    assert isinstance(r, ComparisonRange)
    assert r.comparison_type == expect_type
    assert r.current and r.comparison


# 明确带时间锚点的比较表达应正常
@pytest.mark.parametrize("text,expect_type", [
    ("本月同比", "yoy"),
    ("上个月环比", "previous_period"),
    ("Q2同比", "yoy"),
    ("H1环比", "previous_period"),
])
def test_anchored_comparison_ok(text, expect_type):
    r = extract_comparison_range(text, today=TODAY)
    assert isinstance(r, ComparisonRange)
    assert r.comparison_type == expect_type
    assert r.current and r.comparison


# ─────────────────────────────────────────────────────────
# 三、同时含同比与环比 → 返回 None
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "同比环比都要",
    "本月同比和环比",
    "Q2同比、环比",
    "同比及环比",
])
def test_both_yoy_and_mom_returns_none(text):
    assert extract_comparison_range(text, today=TODAY) is None
    # 检测层同样返回 None（不擅自选一个）
    assert _detect_comparison_type(text) is None


# ─────────────────────────────────────────────────────────
# 四、extract_date_range_v2 不误解比较表达
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "去年同期",
    "上月环比",
    "同比",
    "环比",
    "较上年同期",
    "比上期",
    "较上期",
])
def test_v2_protects_comparison_phrase(text):
    r = extract_date_range_v2(text, today=TODAY)
    assert isinstance(r, DateRange)
    assert r.recognition_status == 'phrase_not_supported'
    assert r.start is None and r.end is None
    assert r.range_type == 'unknown'
    assert 'extract_comparison_range' in r.label
