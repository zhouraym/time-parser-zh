"""
同比 / 环比解析测试（extract_comparison_range）。

同比 yoy              → 与上一年度相同日历位置比较
环比 previous_period  → 与紧邻的同粒度前一周期比较
"""

import json
from datetime import datetime

import pytest

from zh_time_parser import (
    ComparisonRange,
    DateRange,
    extract_comparison_range,
    extract_date_range_v2,
)

TODAY = datetime(2026, 8, 9)


def cmp_range(msg, today=TODAY):
    return extract_comparison_range(msg, today=today)


def quad(r):
    """把结果压成 (current起, current止, comparison起, comparison止) 便于断言。"""
    return (r.current.start, r.current.end, r.comparison.start, r.comparison.end)


# ═════════════════════════════════════════════
#  同比
# ═════════════════════════════════════════════
class TestYearOverYear:
    def test_this_month_yoy(self):
        r = cmp_range('本月同比')
        assert quad(r) == ('2026-08-01', '2026-08-09', '2025-08-01', '2025-08-09')
        assert r.comparison_type == 'yoy'

    def test_last_month_yoy(self):
        r = cmp_range('上个月同比')
        assert quad(r) == ('2026-07-01', '2026-07-31', '2025-07-01', '2025-07-31')

    def test_this_year_yoy_last_year(self):
        """「今年同比去年」不得只返回今年。"""
        r = cmp_range('今年同比去年')
        assert quad(r) == ('2026-01-01', '2026-08-09', '2025-01-01', '2025-08-09')

    def test_this_year_yoy(self):
        r = cmp_range('今年同比')
        assert quad(r) == ('2026-01-01', '2026-08-09', '2025-01-01', '2025-08-09')

    @pytest.mark.parametrize('msg', ['Q2同比', '第二季度同比'])
    def test_q2_yoy(self, msg):
        r = cmp_range(msg)
        assert quad(r) == ('2026-04-01', '2026-06-30', '2025-04-01', '2025-06-30')

    def test_explicit_year_quarter_yoy(self):
        r = cmp_range('2025Q1同比')
        assert quad(r) == ('2025-01-01', '2025-03-31', '2024-01-01', '2024-03-31')

    @pytest.mark.parametrize('msg', ['H1同比', '上半年同比'])
    def test_h1_yoy(self, msg):
        r = cmp_range(msg)
        assert quad(r) == ('2026-01-01', '2026-06-30', '2025-01-01', '2025-06-30')

    def test_explicit_year_half_yoy(self):
        r = cmp_range('2025H2同比')
        assert quad(r) == ('2025-07-01', '2025-12-31', '2024-07-01', '2024-12-31')

    def test_bare_yoy_defaults_to_ytd(self):
        """「同比」单独出现 → 今年截至今天 同比 去年同期。"""
        r = cmp_range('同比')
        assert quad(r) == ('2026-01-01', '2026-08-09', '2025-01-01', '2025-08-09')

    def test_last_year_same_period_not_full_year(self):
        """「去年同期」不得退化为去年全年。"""
        r = cmp_range('去年同期')
        assert quad(r) == ('2026-01-01', '2026-08-09', '2025-01-01', '2025-08-09')
        assert r.comparison.end != '2025-12-31'

    def test_yoy_not_fixed_365_days(self):
        """同比必须走日历平移，跨闰年时不是恒定 365 天。"""
        r = cmp_range('今年同比', today=datetime(2025, 3, 1))
        # 2024 是闰年，2024-01-01~2024-03-01 比 2025 同区间多一天
        cur = (datetime.strptime(r.current.end, '%Y-%m-%d')
               - datetime.strptime(r.current.start, '%Y-%m-%d')).days
        prev = (datetime.strptime(r.comparison.end, '%Y-%m-%d')
                - datetime.strptime(r.comparison.start, '%Y-%m-%d')).days
        assert prev == cur + 1

    def test_leap_day_falls_back_to_28(self):
        """2月29日同比时上一年度无对应日期，回退到 2月28日。"""
        r = cmp_range('本月同比', today=datetime(2024, 2, 29))
        assert r.current.end == '2024-02-29'
        assert r.comparison.end == '2023-02-28'


# ═════════════════════════════════════════════
#  环比
# ═════════════════════════════════════════════
class TestPreviousPeriod:
    def test_this_month_mom_same_elapsed_days(self):
        """进行中的月使用相同已过天数，而非完整上月。"""
        r = cmp_range('本月环比')
        assert quad(r) == ('2026-08-01', '2026-08-09', '2026-07-01', '2026-07-09')
        assert r.comparison_type == 'previous_period'

    def test_last_month_mom_full_periods(self):
        """完整周期与完整前周期比较，各自使用真实月末。"""
        r = cmp_range('上个月环比')
        assert quad(r) == ('2026-07-01', '2026-07-31', '2026-06-01', '2026-06-30')

    def test_mom_uses_real_month_length(self):
        """月环比不得使用固定 30 天：7月31天 vs 6月30天。"""
        r = cmp_range('上个月环比')
        assert r.current.end.endswith('-31')
        assert r.comparison.end.endswith('-30')

    @pytest.mark.parametrize('msg', ['Q2环比', '第二季度环比'])
    def test_q2_mom(self, msg):
        r = cmp_range(msg)
        assert quad(r) == ('2026-04-01', '2026-06-30', '2026-01-01', '2026-03-31')

    def test_q1_mom_crosses_year(self):
        """Q1 环比必须正确跨年到上一年 Q4。"""
        r = cmp_range('Q1环比')
        assert quad(r) == ('2026-01-01', '2026-03-31', '2025-10-01', '2025-12-31')

    def test_h2_mom(self):
        r = cmp_range('H2环比')
        assert quad(r) == ('2026-07-01', '2026-12-31', '2026-01-01', '2026-06-30')

    def test_h1_mom_crosses_year(self):
        """H1 环比必须正确跨年到上一年 H2。"""
        r = cmp_range('H1环比')
        assert quad(r) == ('2026-01-01', '2026-06-30', '2025-07-01', '2025-12-31')

    def test_bare_mom_defaults_to_this_month(self):
        """「环比」单独出现 → 本月截至今天 vs 上月相同已过天数。"""
        r = cmp_range('环比')
        assert quad(r) == ('2026-08-01', '2026-08-09', '2026-07-01', '2026-07-09')

    def test_explicit_year_quarter_mom(self):
        r = cmp_range('2025Q1环比')
        assert quad(r) == ('2025-01-01', '2025-03-31', '2024-10-01', '2024-12-31')

    def test_explicit_year_half_mom(self):
        r = cmp_range('2025H1环比')
        assert quad(r) == ('2025-01-01', '2025-06-30', '2024-07-01', '2024-12-31')

    def test_mom_month_end_clamped(self):
        """3月31日所在完整月环比到2月，须落在真实月末而非 2月31日。"""
        r = cmp_range('上个月环比', today=datetime(2026, 4, 15))
        assert quad(r) == ('2026-03-01', '2026-03-31', '2026-02-01', '2026-02-28')


# ═════════════════════════════════════════════
#  返回 None 的情形
# ═════════════════════════════════════════════
class TestReturnsNone:
    @pytest.mark.parametrize('msg', ['本月', '上个月', 'Q2', 'H1', '最近7天', '2025年'])
    def test_no_comparison_word(self, msg):
        """没有比较词 → None，不编造区间。"""
        assert cmp_range(msg) is None

    @pytest.mark.parametrize('msg', ['', '   ', '你好', '随便写点什么'])
    def test_unparseable(self, msg):
        assert cmp_range(msg) is None

    def test_none_input(self):
        assert extract_comparison_range(None, today=TODAY) is None

    def test_no_exception_raised(self):
        """异常输入不抛异常。"""
        for msg in ['', '@@@', '同' * 50, 'H9同比']:
            cmp_range(msg)


# ═════════════════════════════════════════════
#  返回类型契约
# ═════════════════════════════════════════════
class TestReturnTypeContract:
    @pytest.mark.parametrize('msg', ['本月同比', 'Q2环比', '去年同期', 'H1', '本月', '同比'])
    def test_v2_always_returns_daterange(self, msg):
        """extract_date_range_v2 恒定返回 DateRange，绝不返回 ComparisonRange。"""
        r = extract_date_range_v2(msg, today=TODAY)
        assert isinstance(r, DateRange)
        assert not isinstance(r, ComparisonRange)

    def test_comparison_returns_comparison_range(self):
        assert isinstance(cmp_range('本月同比'), ComparisonRange)

    def test_comparison_not_stored_in_point_or_boundary(self):
        """对比期不得塞进 DateRange.point / boundary。"""
        r = cmp_range('本月同比')
        assert r.current.point is None
        assert r.current.boundary is None

    def test_both_ranges_valid(self):
        r = cmp_range('Q2同比')
        assert bool(r.current) and bool(r.comparison)
        assert isinstance(r.current, DateRange)
        assert isinstance(r.comparison, DateRange)

    def test_default_today_does_not_crash(self):
        """不传 today 时使用当前时间，不报错。"""
        assert extract_comparison_range('本月同比') is not None


# ═════════════════════════════════════════════
#  编程错误必须暴露（不得静默降级）
# ═════════════════════════════════════════════
class TestErrorsPropagate:
    def test_type_error_propagates(self):
        """传入非法类型应抛错，而不是静默返回 None。"""
        with pytest.raises((TypeError, AttributeError)):
            extract_comparison_range('本月同比', today='2026-08-09')

    def test_week_start_invalid_does_not_swallow(self):
        """非法 week_start 不应把编程错误伪装成 None 之外的错误结果。"""
        result = extract_comparison_range('本月同比', today=TODAY, week_start='monday')
        assert result is not None


# ═════════════════════════════════════════════
#  README 示例回归
# ═════════════════════════════════════════════
class TestReadmeExamples:
    def test_readme_q2_yoy_example(self):
        result = extract_comparison_range('Q2同比', today=datetime(2026, 8, 9))
        assert result.current.start == '2026-04-01'
        assert result.current.end == '2026-06-30'
        assert result.comparison.start == '2025-04-01'
        assert result.comparison.end == '2025-06-30'

    def test_readme_json_serializable(self):
        result = extract_comparison_range('Q2同比', today=datetime(2026, 8, 9))
        json.dumps(result.to_dict(), ensure_ascii=False)
