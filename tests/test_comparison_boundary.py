"""比较词边界修复回归测试（2026-08 第二轮）。

覆盖：
1. 同比边界：同期生/同期刊/同期声/同比例/同比例计算 不得误识别为同比。
2. 环比边界：环比例/环比较 不得误触发环比；环比率 仍正常。
3. 独立默认表达严格白名单：允许的有限前缀/后缀正常，夹带无关文本返回 None。
4. extract_date_range_v2 边界：同比例/同期生/同期刊/同期声 维持 no_time_phrase；
   明确比较表达仍是 phrase_not_supported。
5. 同时含同比与环比仍返回 None。
"""

from datetime import datetime

import pytest

from zh_time_parser import extract_comparison_range, extract_date_range_v2

TODAY = datetime(2026, 8, 9)


# ─────────────────────────────────────────────────────────
# 一、同比边界：近似词不得误识别
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "同期生数据", "同期刊", "同期声", "同比例", "同比例计算",
])
def test_yoy_boundary_not_recognized(text):
    assert extract_comparison_range(text, today=TODAY) is None
    assert extract_date_range_v2(text, today=TODAY).recognition_status == 'no_time_phrase'


# ─────────────────────────────────────────────────────────
# 二、环比边界
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["环比例", "环比较"])
def test_mom_boundary_not_recognized(text):
    """环比例/环比较 不是「环比」，不得触发。"""
    assert extract_comparison_range(text, today=TODAY) is None


@pytest.mark.parametrize("text,expect", [
    ("环比率", "previous_period"),
    ("本月环比", "previous_period"),
    ("Q2环比", "previous_period"),
    ("环比", "previous_period"),
])
def test_mom_normal_still_ok(text, expect):
    """环比率 及常见环比表达保持正常。"""
    r = extract_comparison_range(text, today=TODAY)
    assert isinstance(r, object) and r is not None
    assert r.comparison_type == expect


# ─────────────────────────────────────────────────────────
# 三、独立默认表达严格白名单
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expect_type", [
    ("同比", "yoy"),
    ("环比", "previous_period"),
    ("同期", "yoy"),
    ("去年同期", "yoy"),
    ("上年同期", "yoy"),
    ("同比是多少", "yoy"),
    ("环比情况", "previous_period"),
    ("看一下同比", "yoy"),
    ("帮我查同比数据", "yoy"),
    ("去年同期怎么样", "yoy"),
    ("请查询环比结果", "previous_period"),
    ("环比率", "previous_period"),
])
def test_standalone_default_whitelist_ok(text, expect_type):
    r = extract_comparison_range(text, today=TODAY)
    assert r is not None
    assert r.comparison_type == expect_type
    assert r.current and r.comparison


@pytest.mark.parametrize("text", [
    "同期生", "同期刊", "同期声", "同比例", "同比例计算",
    "环比例", "环比较",
    "前阵子同比", "第五季度同比", "H3环比",
])
def test_standalone_default_whitelist_rejects(text):
    """夹带无关文本或非白名单形态 → 不命中默认周期。"""
    assert extract_comparison_range(text, today=TODAY) is None


# ─────────────────────────────────────────────────────────
# 四、extract_date_range_v2 边界
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "同比例", "同期生数据", "同期刊", "同期声",
])
def test_v2_ordinary_no_time_phrase(text):
    r = extract_date_range_v2(text, today=TODAY)
    assert r.recognition_status == 'no_time_phrase'
    assert r.start is None and r.end is None


@pytest.mark.parametrize("text", ["同比", "环比", "去年同期", "上月环比", "Q2同比"])
def test_v2_comparison_phrase_unsupported(text):
    r = extract_date_range_v2(text, today=TODAY)
    assert r.recognition_status == 'phrase_not_supported'
    assert r.range_type == 'unknown'
    assert 'extract_comparison_range' in r.label


# ─────────────────────────────────────────────────────────
# 五、同时含同比与环比仍返回 None
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", [
    "同比环比都要", "本月同比和环比", "Q2同比、环比", "同比及环比",
])
def test_both_yoy_and_mom_returns_none(text):
    assert extract_comparison_range(text, today=TODAY) is None


# ─────────────────────────────────────────────────────────
# 六、带锚点比较保持正常
# ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expect_type", [
    ("本月同比", "yoy"),
    ("上月环比", "previous_period"),
    ("Q2同比", "yoy"),
    ("H1环比", "previous_period"),
])
def test_anchored_comparison_ok(text, expect_type):
    r = extract_comparison_range(text, today=TODAY)
    assert r is not None
    assert r.comparison_type == expect_type
    assert r.current and r.comparison
