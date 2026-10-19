"""
DateRange 主契约与完整规则回归 —— 验证结构化 API 和旧 API 的兼容行为。

运行方式：
    python -m pytest tests/test_date_parse.py -v

策略：
- 本文件是按解析维度组织的完整契约矩阵；不要在补充冒烟文件重复同一组参数
- 精确值断言：用于硬性日期（"2026-04-01 至 2026-04-30"、"2025年"）
- 固定 today 注入：用于相对日期（"上个月"、"最近7天"），保证测试可重复
- 涉及"今天"等动态日期，仅断言结构（start/end 都不为 None）
"""

from datetime import datetime

from time_parser_zh import (
    DateRange,  # 数据类
    extract_date_range,  # 旧 API（向后兼容）
    extract_date_range_v2,  # 新 API（推荐）
    parse_time_expression,  # 旧 API
)

# 全局固定的"今天"，用于相对日期测试
FIXED_TODAY = datetime(2026, 5, 24)


# ═════════════════════════════════════════════════════════
#  1. 范围（最高优先级）
# ═════════════════════════════════════════════════════════

class TestExplicitDateRange:
    """日期范围解析"""

    def test_explicit_date_range(self):
        start, end = extract_date_range("2026-04-01 至 2026-04-30")
        assert start == "2026-04-01"
        assert end == "2026-04-30"

    def test_date_range_with_from_to(self):
        start, end = extract_date_range("从2026/03/01到2026/03/15")
        assert start == "2026-03-01"
        assert end == "2026-03-15"

    def test_date_range_with_tilde(self):
        """用 ~ 分隔的范围"""
        start, end = extract_date_range("2026-04-01 ~ 2026-04-30")
        assert start == "2026-04-01"
        assert end == "2026-04-30"

    def test_date_range_compact(self):
        """紧凑格式：20260401 至 20260415"""
        start, end = extract_date_range("20260401至20260415")
        assert start == "2026-04-01"
        assert end == "2026-04-15"

    def test_v2_returns_daterange(self):
        """v2 返回 DateRange 对象"""
        r = extract_date_range_v2("2026-04-01 至 2026-04-30")
        assert isinstance(r, DateRange)
        assert r.range_type == 'range'
        assert r.start == "2026-04-01"
        assert r.end == "2026-04-30"
        # tuple 解包也能用
        s, e = r
        assert (s, e) == ("2026-04-01", "2026-04-30")


# ═════════════════════════════════════════════════════════
#  2. 季度（新增）
# ═════════════════════════════════════════════════════════

class TestQuarter:
    """季度解析"""

    def test_year_with_quarter(self):
        """2026Q1 → 2026-01-01 ~ 2026-03-31"""
        r = extract_date_range_v2("2026Q1", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-03-31"
        assert r.range_type == 'quarter'
        assert r.granularity == 'quarter'

    def test_current_quarter(self):
        """本季度（5月 → Q2）"""
        r = extract_date_range_v2("本季度", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-06-30"

    def test_last_quarter(self):
        """上季度（5月 → Q1）"""
        r = extract_date_range_v2("上季度", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-03-31"

    def test_next_quarter(self):
        """下季度（5月 → Q3）"""
        r = extract_date_range_v2("下季度", today=FIXED_TODAY)
        assert r.start == "2026-07-01"
        assert r.end == "2026-09-30"

    def test_chinese_quarter(self):
        """第一季度"""
        r = extract_date_range_v2("第一季度数据量", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-03-31"

    def test_quarter_ytd(self):
        """Q1至今"""
        r = extract_date_range_v2("Q1至今", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"


# ═════════════════════════════════════════════════════════
#  3. 相对时间
# ═════════════════════════════════════════════════════════

class TestRelativeTime:
    """相对时间解析（用固定 today）"""

    def test_last_month(self):
        r = extract_date_range_v2("上个月", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-04-30"
        assert r.range_type == 'range'

    def test_this_month_with_ge(self):
        """这个月（含"个"字，回归 bug：原正则只认"本月/这月"）"""
        for q in ["这个月", "这个月新增的记录", "张三最近这个月提交的"]:
            r = extract_date_range_v2(q, today=FIXED_TODAY)
            assert r.start == "2026-05-01", q
            assert r.end == "2026-05-24", q

    def test_last_month_short(self):
        """上月（不带"个"）"""
        r = extract_date_range_v2("上月数据", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-04-30"

    def test_last_last_month(self):
        """上上个月（5月 → 3月）"""
        r = extract_date_range_v2("上上个月", today=FIXED_TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-03-31"

    def test_next_month(self):
        """下个月（5月 → 6月）"""
        r = extract_date_range_v2("下个月", today=FIXED_TODAY)
        assert r.start == "2026-06-01"
        assert r.end == "2026-06-30"

    def test_next_month_year_boundary(self):
        """下个月跨年（12月 → 次年 1月）"""
        r = extract_date_range_v2("下个月", today=datetime(2026, 12, 15))
        assert r.start == "2027-01-01"
        assert r.end == "2027-01-31"

    def test_current_month(self):
        """本月（5月24日）"""
        r = extract_date_range_v2("本月", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-24"

    def test_recent_7_days(self):
        r = extract_date_range_v2("最近7天", today=FIXED_TODAY)
        assert r.start == "2026-05-18"  # 包含今天，所以是 24-7+1=18
        assert r.end == "2026-05-24"

    def test_recent_30_days(self):
        r = extract_date_range_v2("最近30天", today=FIXED_TODAY)
        assert r.start == "2026-04-25"
        assert r.end == "2026-05-24"

    def test_near_3_months(self):
        """近3个月"""
        r = extract_date_range_v2("近3个月", today=FIXED_TODAY)
        assert r.start == "2026-02-24"  # 3月前
        assert r.end == "2026-05-24"

    def test_near_half_year(self):
        """近半年"""
        r = extract_date_range_v2("近半年", today=FIXED_TODAY)
        assert r.end == "2026-05-24"
        # 182 天前
        assert r.start is not None

    def test_near_one_year(self):
        """近一年"""
        r = extract_date_range_v2("近一年", today=FIXED_TODAY)
        assert r.start == "2025-05-24"
        assert r.end == "2026-05-24"

    def test_recent_2_weeks(self):
        """最近2周"""
        r = extract_date_range_v2("最近2周", today=FIXED_TODAY)
        assert r.start == "2026-05-10"
        assert r.end == "2026-05-24"


# ═════════════════════════════════════════════════════════
#  4. 单日同义词
# ═════════════════════════════════════════════════════════

class TestSingleDay:
    """单日同义词"""

    def test_today(self):
        r = extract_date_range_v2("今天", today=FIXED_TODAY)
        assert r.start == "2026-05-24"
        assert r.end == "2026-05-24"
        assert r.range_type == 'point'

    def test_today_synonym_tongtian(self):
        """当天"""
        r = extract_date_range_v2("当天数据", today=FIXED_TODAY)
        assert r.start == "2026-05-24"

    def test_today_synonym_jiri(self):
        """今日"""
        r = extract_date_range_v2("今日记录", today=FIXED_TODAY)
        assert r.start == "2026-05-24"

    def test_yesterday(self):
        r = extract_date_range_v2("昨天", today=FIXED_TODAY)
        assert r.start == "2026-05-23"
        assert r.end == "2026-05-23"

    def test_tomorrow(self):
        r = extract_date_range_v2("明天", today=FIXED_TODAY)
        assert r.start == "2026-05-25"

    def test_day_before_yesterday(self):
        r = extract_date_range_v2("前天", today=FIXED_TODAY)
        assert r.start == "2026-05-22"


# ═════════════════════════════════════════════════════════
#  5. 周
# ═════════════════════════════════════════════════════════

class TestWeek:
    """周解析"""

    def test_this_week_monday_start(self):
        """本周（周一开始，2026-05-24 是周日，本周是 5/18-5/24）"""
        r = extract_date_range_v2("本周", today=FIXED_TODAY, week_start='monday')
        assert r.start == "2026-05-18"
        assert r.end == "2026-05-24"
        assert r.week_start == 'monday'

    def test_this_week_sunday_start(self):
        """本周（周日开始，5/24 是周日，本周是 5/24-5/30）"""
        r = extract_date_range_v2("本周", today=FIXED_TODAY, week_start='sunday')
        assert r.start == "2026-05-24"
        assert r.end == "2026-05-30"

    def test_last_week(self):
        r = extract_date_range_v2("上周", today=FIXED_TODAY, week_start='monday')
        assert r.start == "2026-05-11"
        assert r.end == "2026-05-17"

    def test_next_week(self):
        r = extract_date_range_v2("下周", today=FIXED_TODAY, week_start='monday')
        assert r.start == "2026-05-25"
        assert r.end == "2026-05-31"


# ═════════════════════════════════════════════════════════
#  6. 月份（跨月、单月）
# ═════════════════════════════════════════════════════════

class TestMonth:
    """月份解析"""

    def test_cross_month_range(self):
        """3月到5月"""
        r = extract_date_range_v2("3月到5月数据", today=FIXED_TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-05-31"

    def test_cross_month_dash(self):
        """1-3月"""
        r = extract_date_range_v2("1-3月数据", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-03-31"

    def test_single_month(self):
        """3月（当前年）"""
        r = extract_date_range_v2("3月份数据", today=FIXED_TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-03-31"

    def test_month_start(self):
        """本月月初"""
        r = extract_date_range_v2("本月初", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-24"

    def test_month_end(self):
        """本月月末"""
        r = extract_date_range_v2("本月底", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-31"


# ═════════════════════════════════════════════════════════
#  7. 年份
# ═════════════════════════════════════════════════════════

class TestYear:
    """年份解析"""

    def test_full_year_4digit(self):
        start, end = extract_date_range("2025年")
        assert start == "2025-01-01"
        assert end == "2025-12-31"

    def test_full_year_2digit(self):
        start, end = extract_date_range("25年")
        assert start == "2025-01-01"
        assert end == "2025-12-31"

    def test_this_year(self):
        r = extract_date_range_v2("今年", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"  # 至今

    def test_last_year(self):
        r = extract_date_range_v2("去年", today=FIXED_TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2025-12-31"

    def test_year_before_last(self):
        r = extract_date_range_v2("前年", today=FIXED_TODAY)
        assert r.start == "2024-01-01"
        assert r.end == "2024-12-31"

    def test_next_year(self):
        r = extract_date_range_v2("明年", today=FIXED_TODAY)
        assert r.start == "2027-01-01"
        assert r.end == "2027-12-31"

    def test_ytd(self):
        """年初至今"""
        r = extract_date_range_v2("年初至今", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"
        assert r.range_type == 'ytd'

    def test_ytd_alias(self):
        """YTD 缩写"""
        r = extract_date_range_v2("YTD 数据", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"

    def test_year_end(self):
        """年末"""
        r = extract_date_range_v2("年末数据量", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-12-31"

    def test_invalid_year_5digit(self):
        """99999年 不在合理范围，应不识别"""
        r = extract_date_range_v2("99999年数据量", today=FIXED_TODAY)
        # 应该落到 unknown 或者更弱的匹配
        assert r.range_type == 'unknown' or r.start is None


# ═════════════════════════════════════════════════════════
#  8. 精确日期
# ═════════════════════════════════════════════════════════

class TestExactDate:
    """精确日期解析"""

    def test_dash_format(self):
        r = extract_date_range_v2("2026-04-15", today=FIXED_TODAY)
        assert r.start == "2026-04-15"
        assert r.end == "2026-04-15"
        assert r.range_type == 'point'

    def test_slash_format(self):
        r = extract_date_range_v2("2026/04/15", today=FIXED_TODAY)
        assert r.start == "2026-04-15"

    def test_chinese_format(self):
        """2026年4月15日"""
        r = extract_date_range_v2("2026年4月15日数据量", today=FIXED_TODAY)
        assert r.start == "2026-04-15"

    def test_compact_format(self):
        """20260415"""
        r = extract_date_range_v2("20260415 数据", today=FIXED_TODAY)
        assert r.start == "2026-04-15"

    def test_md_chinese(self):
        """4月15日（当前年）"""
        r = extract_date_range_v2("4月15日登记", today=FIXED_TODAY)
        assert r.start == "2026-04-15"


# ═════════════════════════════════════════════════════════
#  9. 边界与健壮性
# ═════════════════════════════════════════════════════════

class TestRobustness:
    """边界和健壮性"""

    def test_no_date_expression(self):
        """无日期表达 → 返回空 DateRange"""
        r = extract_date_range_v2("张三一共多少")
        assert r.start is None
        assert r.end is None
        # 旧 API 也保持兼容
        s, e = extract_date_range("张三一共多少")
        assert s is None
        assert e is None

    def test_empty_string(self):
        r = extract_date_range_v2("")
        assert r.start is None

    def test_whitespace(self):
        r = extract_date_range_v2("   ")
        assert r.start is None

    def test_garbage_text(self):
        r = extract_date_range_v2("!@#$%^&*()")
        assert r.start is None

    def test_does_not_misparse_plain_name_and_number(self):
        """不把普通名词/数字误解析成日期"""
        r = extract_date_range_v2("张三 有 12345 个", today=FIXED_TODAY)
        # 应该返回空（数字 12345 不是合法日期）
        assert r.start is None or r.range_type == 'unknown'

    def test_old_api_still_works(self):
        """旧 API 仍可用"""
        s, e = extract_date_range("2026-04-01 至 2026-04-30")
        assert s == "2026-04-01"
        assert e == "2026-04-30"

    def test_old_api_parse_time_expression(self):
        """旧 API parse_time_expression 仍可用"""
        result = parse_time_expression("上个月", today=FIXED_TODAY)
        assert result == ("2026-04-01", "2026-04-30")

    def test_daterange_tuple_unpacking(self):
        """DateRange 支持 tuple 解包"""
        s, e = extract_date_range_v2("上个月", today=FIXED_TODAY)
        assert s == "2026-04-01"
        assert e == "2026-04-30"

    def test_daterange_equality(self):
        """DateRange 与 tuple 比较相等"""
        r = extract_date_range_v2("上个月", today=FIXED_TODAY)
        assert r == ("2026-04-01", "2026-04-30")

    def test_daterange_repr(self):
        """DateRange repr 不报错"""
        r = extract_date_range_v2("上个月", today=FIXED_TODAY)
        assert "上个月" in repr(r)


# ═════════════════════════════════════════════════════════
#  10. 优先级测试
# ═════════════════════════════════════════════════════════

class TestPriority:
    """解析器优先级（强匹配优先于弱匹配）"""

    def test_explicit_range_beats_single_date(self):
        """范围优先于单日期"""
        r = extract_date_range_v2("2026-04-01 至 2026-04-30", today=FIXED_TODAY)
        # 不应该被"2026-04-01"截胡成单日
        assert r.start == "2026-04-01"
        assert r.end == "2026-04-30"

    def test_quarter_beats_month(self):
        """Q1 优先于 3月"""
        r = extract_date_range_v2("2026Q1", today=FIXED_TODAY)
        assert r.granularity == 'quarter'

    def test_year_beats_month_in_text(self):
        """2025年 中的"5月"不应被截胡"""
        r = extract_date_range_v2("2025年数据", today=FIXED_TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2025-12-31"


# ═════════════════════════════════════════════════════════
#  11. 口述日期范围（新）
# ═════════════════════════════════════════════════════════

class TestDayRange:
    """当月号段（口语化）"""

    def test_day_range_basic(self):
        """5号到15号 → 当月 5日 ~ 15日"""
        r = extract_date_range_v2("5号到15号数据", today=FIXED_TODAY)
        assert r.start == "2026-05-05"
        assert r.end == "2026-05-15"
        assert r.granularity == 'day'

    def test_day_range_tilde(self):
        """3号~8号"""
        r = extract_date_range_v2("3号~8号", today=FIXED_TODAY)
        assert r.start == "2026-05-03"
        assert r.end == "2026-05-08"

    def test_day_range_dash(self):
        """5-15 → 当月 5日 ~ 15日"""
        r = extract_date_range_v2("5-15 数据", today=FIXED_TODAY)
        assert r.start == "2026-05-05"
        assert r.end == "2026-05-15"

    def test_day_range_slash(self):
        """3/8 → 当月 3日 ~ 8日"""
        r = extract_date_range_v2("3/8 数据", today=FIXED_TODAY)
        assert r.start == "2026-05-03"
        assert r.end == "2026-05-08"

    def test_day_to_today(self):
        """1号到今天 → 当月 1日 ~ 5月24日"""
        r = extract_date_range_v2("1号到今天", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-24"

    def test_day_to_today_alt(self):
        """5号至今"""
        r = extract_date_range_v2("5号至今", today=FIXED_TODAY)
        assert r.start == "2026-05-05"
        assert r.end == "2026-05-24"


class TestChineseDateRange:
    """中文日期段"""

    def test_month_day_range(self):
        """3月1号到3月15号"""
        r = extract_date_range_v2("3月1号到3月15号", today=FIXED_TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-03-15"

    def test_month_day_range_with_zhi(self):
        """4月5日至4月20日"""
        r = extract_date_range_v2("4月5日至4月20日", today=FIXED_TODAY)
        assert r.start == "2026-04-05"
        assert r.end == "2026-04-20"

    def test_month_day_range_from_to(self):
        """从5月1号到5月10号"""
        r = extract_date_range_v2("从5月1号到5月10号", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-10"

    def test_year_month_day_range(self):
        """2026年3月1号至2026年3月31号"""
        r = extract_date_range_v2("2026年3月1号至2026年3月31号", today=FIXED_TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-03-31"


class TestMonthToToday:
    """月份+至今"""

    def test_last_month_to_today(self):
        """上个月到今天（5/24 → 4/1 ~ 5/24）"""
        r = extract_date_range_v2("上个月到今天", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-05-24"
        assert r.is_relative is True

    def test_last_month_ytd(self):
        """上个月至今（简写）"""
        r = extract_date_range_v2("上个月至今", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-05-24"

    def test_last_month_short_to_today(self):
        """上月到今天（不带"个"）"""
        r = extract_date_range_v2("上月到今天", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-05-24"

    def test_last_last_month_to_today(self):
        """上上个月到今天（5/24 → 3/1 ~ 5/24）"""
        r = extract_date_range_v2("上上个月到今天", today=FIXED_TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-05-24"

    def test_specific_month_to_today(self):
        """3月至今"""
        r = extract_date_range_v2("3月至今", today=FIXED_TODAY)
        assert r.start == "2026-03-01"
        assert r.end == "2026-05-24"


class TestQuarterRange:
    """跨季度范围 / 季度+至今"""

    def test_q1_to_q2(self):
        """Q1到Q2 → 1/1 ~ 6/30"""
        r = extract_date_range_v2("Q1到Q2", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-06-30"
        assert r.granularity == 'quarter'

    def test_q1_to_q3_with_tilde(self):
        """Q1~Q3"""
        r = extract_date_range_v2("Q1~Q3", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-09-30"

    def test_year_q_range(self):
        """2025Q1到2025Q3"""
        r = extract_date_range_v2("2025Q1到2025Q3", today=FIXED_TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2025-09-30"

    def test_chinese_quarter_range(self):
        """一季度到三季度"""
        r = extract_date_range_v2("一季度到三季度", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-09-30"

    def test_quarter_to_quarter_with_zhongwen(self):
        """第一季度至第二季度"""
        r = extract_date_range_v2("第一季度至第二季度", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-06-30"

    def test_last_quarter_to_this_quarter(self):
        """上季度到本季度"""
        r = extract_date_range_v2("上季度到本季度", today=FIXED_TODAY)
        # 5/24 → 上季度 Q1 1/1 ~ 3/31，本季度 Q2 4/1 ~ 6/30
        assert r.start == "2026-01-01"
        assert r.end == "2026-06-30"

    def test_last_quarter_ytd(self):
        """上季度至今（5/24 → Q1 1/1 ~ 5/24）"""
        r = extract_date_range_v2("上季度至今", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"

    def test_q1_ytd_existing(self):
        """Q1至今（已存在）"""
        r = extract_date_range_v2("Q1至今", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"

    def test_this_quarter_to_today(self):
        """本季度到今天"""
        r = extract_date_range_v2("本季度到今天", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-05-24"


class TestHalfYear:
    """半年/全年范围"""

    def test_first_half_ytd(self):
        """上半年至今（5/24 → 1/1 ~ 5/24）"""
        r = extract_date_range_v2("上半年至今", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"

    def test_second_half_ytd(self) -> None:
        """五月的下半年至今应拒绝倒序区间。

        Args:
            无。

        Returns:
            None。

        Raises:
            AssertionError: 尚未开始的半年被解析成倒序日期区间。
        """
        r = extract_date_range_v2("下半年至今", today=FIXED_TODAY)
        assert not r
        assert r.to_tuple() == (None, None)
        assert r.recognition_status == "phrase_not_supported"

    def test_first_half_full(self):
        """上半年（整段）"""
        r = extract_date_range_v2("上半年的数据", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-06-30"

    def test_full_year_ytd(self):
        """全年至今"""
        r = extract_date_range_v2("全年至今", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-05-24"


class TestMonthSpan:
    """月内段"""

    def test_month_start_to_end(self):
        """月初到月末"""
        r = extract_date_range_v2("月初到月末", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-31"

    def test_this_month_start_to_end(self):
        """本月初到本月末"""
        r = extract_date_range_v2("本月初到本月末", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-31"


class TestQuarterSpan:
    """季度内段"""

    def test_q1_full(self):
        """Q1初到Q1末"""
        r = extract_date_range_v2("Q1初到Q1末", today=FIXED_TODAY)
        assert r.start == "2026-01-01"
        assert r.end == "2026-03-31"

    def test_this_quarter_full(self):
        """本季度初到本季度末"""
        r = extract_date_range_v2("本季度初到本季度末", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-06-30"


# ═════════════════════════════════════════════════════════
#  12. 相对月 + 具体日（单点）
# ═════════════════════════════════════════════════════════

class TestRelativeMonthDay:
    """相对月 + 具体日"""

    def test_last_month_first_day(self):
        """上个月1号 → 2026-04-01（单点）"""
        r = extract_date_range_v2("上个月1号", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-04-01"
        assert r.range_type == 'point'

    def test_last_month_short(self):
        """上月1号"""
        r = extract_date_range_v2("上月1号", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-04-01"

    def test_last_month_15(self):
        """上个月15号"""
        r = extract_date_range_v2("上个月15号", today=FIXED_TODAY)
        assert r.start == "2026-04-15"
        assert r.end == "2026-04-15"

    def test_last_last_month(self):
        """上上个月10号 → 3-10"""
        r = extract_date_range_v2("上上个月10号", today=FIXED_TODAY)
        assert r.start == "2026-03-10"

    def test_next_month_first_day(self):
        """下个月1号 → 2026-06-01"""
        r = extract_date_range_v2("下个月1号", today=FIXED_TODAY)
        assert r.start == "2026-06-01"
        assert r.end == "2026-06-01"

    def test_this_month_15(self):
        """本月15号"""
        r = extract_date_range_v2("本月15号", today=FIXED_TODAY)
        assert r.start == "2026-05-15"
        assert r.end == "2026-05-15"

    def test_with_ri(self):
        """上个月1日（用日不用号）"""
        r = extract_date_range_v2("上个月1日", today=FIXED_TODAY)
        assert r.start == "2026-04-01"


# ═════════════════════════════════════════════════════════
#  13. 具体日 到 今天
# ═════════════════════════════════════════════════════════

class TestSpecificDayToToday:
    """具体日 到 今天"""

    def test_last_month_to_today(self):
        """上个月1号到今天 → 4-1 ~ 5-24"""
        r = extract_date_range_v2("上个月1号到今天", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-05-24"

    def test_last_month_ytd(self):
        """上月1号至今"""
        r = extract_date_range_v2("上月1号至今", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-05-24"

    def test_last_month_15_to_today(self):
        """上个月15号到今天"""
        r = extract_date_range_v2("上个月15号到今天", today=FIXED_TODAY)
        assert r.start == "2026-04-15"
        assert r.end == "2026-05-24"

    def test_md_to_today(self):
        """4月1号到今天"""
        r = extract_date_range_v2("4月1号到今天", today=FIXED_TODAY)
        assert r.start == "2026-04-01"
        assert r.end == "2026-05-24"

    def test_current_month_md_to_today(self):
        """5月1号到今天"""
        r = extract_date_range_v2("5月1号到今天", today=FIXED_TODAY)
        assert r.start == "2026-05-01"
        assert r.end == "2026-05-24"

    def test_ymd_to_today(self):
        """2026年3月15号到今天"""
        r = extract_date_range_v2("2026年3月15号到今天", today=FIXED_TODAY)
        assert r.start == "2026-03-15"
        assert r.end == "2026-05-24"

    def test_md_ytd(self):
        """3月10号至今"""
        r = extract_date_range_v2("3月10号至今", today=FIXED_TODAY)
        assert r.start == "2026-03-10"
        assert r.end == "2026-05-24"


# ═════════════════════════════════════════════════════════
#  14. 周号段
# ═════════════════════════════════════════════════════════

class TestWeekDayRange:
    """周内号段"""

    def test_weekday_simple(self):
        """周一到周三 → 本周一到本周三"""
        r = extract_date_range_v2("周一到周三", today=FIXED_TODAY)
        # 5/24 是周日，本周（周一起算）= 5/18 ~ 5/24
        assert r.start == "2026-05-18"
        assert r.end == "2026-05-20"

    def test_this_week_mon_to_fri(self):
        """本周一到周五"""
        r = extract_date_range_v2("本周一到周五", today=FIXED_TODAY)
        assert r.start == "2026-05-18"
        assert r.end == "2026-05-22"

    def test_this_week_full(self):
        """本周一到本周五"""
        r = extract_date_range_v2("本周一到本周五", today=FIXED_TODAY)
        assert r.start == "2026-05-18"
        assert r.end == "2026-05-22"

    def test_last_week_mon_to_fri(self):
        """上周一到周五"""
        r = extract_date_range_v2("上周一到周五", today=FIXED_TODAY)
        assert r.start == "2026-05-11"
        assert r.end == "2026-05-15"

    def test_last_week_full(self):
        """上周一到上周三"""
        r = extract_date_range_v2("上周一到上周三", today=FIXED_TODAY)
        assert r.start == "2026-05-11"
        assert r.end == "2026-05-13"

    def test_xingqi(self):
        """星期一到星期三"""
        r = extract_date_range_v2("星期一到星期三", today=FIXED_TODAY)
        assert r.start == "2026-05-18"
        assert r.end == "2026-05-20"

    def test_next_week_mon_to_wed(self):
        """下周一到周三"""
        r = extract_date_range_v2("下周一到周三", today=FIXED_TODAY)
        assert r.start == "2026-05-25"
        assert r.end == "2026-05-27"


# ═════════════════════════════════════════════════════════
#  15. 周 + 至今
# ═════════════════════════════════════════════════════════

class TestWeekToToday:
    """周 + 至今"""

    def test_this_week_to_today(self):
        """本周到今天 → 5/18 ~ 5/24（5/24 是周日）"""
        r = extract_date_range_v2("本周到今天", today=FIXED_TODAY)
        assert r.start == "2026-05-18"
        assert r.end == "2026-05-24"

    def test_this_week_ytd(self):
        """本周至今"""
        r = extract_date_range_v2("本周至今", today=FIXED_TODAY)
        assert r.start == "2026-05-18"
        assert r.end == "2026-05-24"

    def test_last_week_to_today(self):
        """上周到今天 → 上周一(5/11) ~ 5/24"""
        r = extract_date_range_v2("上周到今天", today=FIXED_TODAY)
        assert r.start == "2026-05-11"
        assert r.end == "2026-05-24"

    def test_last_last_week_to_today(self):
        """上上周到今天"""
        r = extract_date_range_v2("上上周到今天", today=FIXED_TODAY)
        assert r.start == "2026-05-04"
        assert r.end == "2026-05-24"


# ═════════════════════════════════════════════════════════
#  16. 跨年范围
# ═════════════════════════════════════════════════════════

class TestYearRange:
    """跨年范围"""

    def test_last_year_to_this_year(self):
        """去年到今年 → 2025-01-01 ~ 2026-05-24（今年取至今）"""
        r = extract_date_range_v2("去年到今年", today=FIXED_TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2026-05-24"

    def test_year_before_last_to_this_year(self):
        """前年到今年"""
        r = extract_date_range_v2("前年到今年", today=FIXED_TODAY)
        assert r.start == "2024-01-01"
        assert r.end == "2026-05-24"

    def test_explicit_years(self):
        """2025年到2026年"""
        r = extract_date_range_v2("2025年到2026年", today=FIXED_TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2026-12-31"

    def test_two_digit_years(self):
        """25年到26年"""
        r = extract_date_range_v2("25年到26年", today=FIXED_TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2026-12-31"

    def test_explicit_to_today(self):
        """2025年到今年"""
        r = extract_date_range_v2("2025年到今年", today=FIXED_TODAY)
        assert r.start == "2025-01-01"
        assert r.end == "2026-05-24"
