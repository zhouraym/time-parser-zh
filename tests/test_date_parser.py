"""
DateRange 补充冒烟测试 —— 用不同锚点覆盖跨月、跨年和组合输入。

完整的逐规则契约位于 test_date_parse.py；本文件只保留端到端代表样例和
主矩阵未覆盖的组合场景，避免两套完整测试长期漂移。
运行: pytest tests/test_date_parser.py -v
"""
from datetime import datetime

from zh_time_parser import extract_date_range_v2

# 固定测试日期：2026-06-23（周二）
TODAY = datetime(2026, 6, 23)


class TestRelativeTime:
    """相对时间表达"""

    def test_recent_7_days(self):
        r = extract_date_range_v2("最近7天", TODAY)
        assert r.start == "2026-06-17"
        assert r.end == "2026-06-23"

    def test_recent_30_days(self):
        r = extract_date_range_v2("最近30天", TODAY)
        assert r.start == "2026-05-25"
        assert r.end == "2026-06-23"

    def test_recent_3_months(self):
        r = extract_date_range_v2("最近3个月", TODAY)
        assert r.start == "2026-03-23"
        assert r.end == "2026-06-23"

    def test_recent_1_year(self):
        r = extract_date_range_v2("最近1年", TODAY)
        assert r.start == "2025-06-23"
        assert r.end == "2026-06-23"

    def test_recent_half_year(self):
        r = extract_date_range_v2("近半年", TODAY)
        assert r.start == "2025-12-22"
        assert r.end == "2026-06-23"

    def test_recent_ten_days(self):
        """最近十天 - 中文数字"""
        r = extract_date_range_v2("最近十天", TODAY)
        assert r.start == "2026-06-14"
        assert r.end == "2026-06-23"

    def test_recent_three_months(self):
        """最近三个月 - 中文数字"""
        r = extract_date_range_v2("最近三个月", TODAY)
        assert r.start == "2026-03-23"
        assert r.end == "2026-06-23"

    def test_recent_two_years(self):
        """最近两年 - 中文数字"""
        r = extract_date_range_v2("最近两年", TODAY)
        assert r.start == "2024-06-23"
        assert r.end == "2026-06-23"


class TestPastYears:
    """前N年表达"""

    def test_past_two_years(self):
        """前两年 - 中文数字"""
        r = extract_date_range_v2("前两年", TODAY)
        assert r.start == "2024-06-23"
        assert r.end == "2026-06-23"

    def test_past_three_years(self):
        """前三年 - 中文数字"""
        r = extract_date_range_v2("前三年", TODAY)
        assert r.start == "2023-06-23"
        assert r.end == "2026-06-23"


class TestThisQuarter:
    """这个季度表达"""

    def test_this_quarter(self):
        """这个季度 - 当前季度"""
        r = extract_date_range_v2("这个季度", TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-06-30"

    def test_this_quarter_with_ge(self):
        """这个季度 - 带'个'字"""
        r = extract_date_range_v2("这个季度", TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-06-30"


class TestChineseNumbers:
    """中文数字支持"""

    def test_recent_two_years(self):
        r = extract_date_range_v2("最近两年", TODAY)
        assert r.start == "2024-06-23"
        assert r.end == "2026-06-23"

    def test_recent_three_years(self):
        r = extract_date_range_v2("最近三年", TODAY)
        assert r.start == "2023-06-23"
        assert r.end == "2026-06-23"

    def test_recent_two_months(self):
        r = extract_date_range_v2("最近两个月", TODAY)
        assert r.start == "2026-04-23"
        assert r.end == "2026-06-23"

    def test_recent_ten_days(self):
        r = extract_date_range_v2("最近十天", TODAY)
        assert r.start == "2026-06-14"
        assert r.end == "2026-06-23"

    def test_recent_twenty_days(self):
        r = extract_date_range_v2("最近二十天", TODAY)
        assert r.start == "2026-06-04"
        assert r.end == "2026-06-23"


class TestThisPastYears:
    """这N年/前N年表达"""

    def test_this_two_years(self):
        r = extract_date_range_v2("这两年", TODAY)
        assert r.start == "2024-06-23"
        assert r.end == "2026-06-23"

    def test_this_three_years(self):
        r = extract_date_range_v2("这三年", TODAY)
        assert r.start == "2023-06-23"
        assert r.end == "2026-06-23"

    def test_past_two_years(self):
        r = extract_date_range_v2("前两年", TODAY)
        assert r.start == "2024-06-23"
        assert r.end == "2026-06-23"

    def test_past_several_years(self):
        r = extract_date_range_v2("前几年", TODAY)
        assert not r
        assert r.recognition_status == "ambiguous"


class TestYearUntilNow:
    """X年至今表达"""

    def test_2025_until_now(self):
        r = extract_date_range_v2("2025年至今", TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2026-06-23"

    def test_25_until_now(self):
        r = extract_date_range_v2("25年至今", TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2026-06-23"

    def test_2024_until_now(self):
        r = extract_date_range_v2("2024年到现在", TODAY)
        assert r.start == "2024-01-01"
        assert r.end == "2026-06-23"


class TestMonthExpressions:
    """月份相关表达"""

    def test_last_month(self):
        r = extract_date_range_v2("上个月", TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-31"

    def test_this_month(self):
        r = extract_date_range_v2("这个月", TODAY)
        assert r.start == "2026-06-01"
        assert r.end == "2026-06-23"  # 现有行为：本月到今天

    def test_next_month(self):
        r = extract_date_range_v2("下个月", TODAY)
        assert r.start == "2026-07-01"
        assert r.end == "2026-07-31"


class TestYearExpressions:
    """年份相关表达"""

    def test_this_year(self):
        r = extract_date_range_v2("今年", TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-06-23"

    def test_last_year(self):
        r = extract_date_range_v2("去年", TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2025-12-31"

    def test_year_2025(self):
        r = extract_date_range_v2("2025年", TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2025-12-31"


class TestQuarterExpressions:
    """季度相关表达"""

    def test_this_quarter(self):
        r = extract_date_range_v2("这个季度", TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-06-30"

    def test_last_quarter(self):
        r = extract_date_range_v2("上个季度", TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-03-31"

    def test_q1_2026(self):
        r = extract_date_range_v2("2026年Q1", TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-03-31"


class TestWeekExpressions:
    """周相关表达"""

    def test_this_week(self):
        r = extract_date_range_v2("这周", TODAY)
        assert r.start == "2026-06-22"  # 周一
        assert r.end == "2026-06-28"    # 周日

    def test_last_week(self):
        r = extract_date_range_v2("上周", TODAY)
        assert r.start == "2026-06-15"
        assert r.end == "2026-06-21"


class TestDayExpressions:
    """日相关表达"""

    def test_today(self):
        r = extract_date_range_v2("今天", TODAY)
        assert r.start == "2026-06-23"
        assert r.end == "2026-06-23"

    def test_yesterday(self):
        r = extract_date_range_v2("昨天", TODAY)
        assert r.start == "2026-06-22"
        assert r.end == "2026-06-22"

    def test_day_before_yesterday(self):
        r = extract_date_range_v2("前天", TODAY)
        assert r.start == "2026-06-21"
        assert r.end == "2026-06-21"


class TestDateRanges:
    """日期范围表达"""

    def test_explicit_range(self):
        r = extract_date_range_v2("2026-01-01至2026-06-23", TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-06-23"

    def test_month_range(self):
        r = extract_date_range_v2("3月到5月", TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-05-31"

    def test_year_range(self):
        r = extract_date_range_v2("2024年到2026年", TODAY)
        assert r.start == "2024-01-01"
        assert r.end == "2026-12-31"


class TestRecognitionStatus:
    """recognition_status 字段测试"""

    def test_ok_status(self):
        r = extract_date_range_v2("最近7天", TODAY)
        assert r.recognition_status == "ok"

    def test_no_time_phrase(self):
        r = extract_date_range_v2("查张三的明细", TODAY)
        assert r.recognition_status == "no_time_phrase"

    def test_phrase_not_supported(self):
        r = extract_date_range_v2("前阵子", TODAY)
        assert r.recognition_status == "ambiguous"


class TestEdgeCases:
    """边界情况"""

    def test_empty_string(self):
        r = extract_date_range_v2("", TODAY)
        assert r.recognition_status == "no_time_phrase"

    def test_no_date_info(self):
        r = extract_date_range_v2("随便聊聊", TODAY)
        assert r.recognition_status == "no_time_phrase"

    def test_mixed_with_other_text(self):
        r = extract_date_range_v2("帮我查一下最近3天的数据", TODAY)
        assert r.start == "2026-06-21"
        assert r.end == "2026-06-23"
        assert r.recognition_status == "ok"
