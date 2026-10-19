"""
H1/H2 自然半年表达测试。

覆盖：H1/H2、h1/h2、指定年份、空格与「年」字变体、半年范围、
与「近半年」的碰撞、与年份解析的优先级、非法表达、孤立字母 H 不误识别。
"""

from datetime import datetime

import pytest

from zh_time_parser import extract_date_range_v2

TODAY = datetime(2026, 8, 9)


def parse(msg, today=TODAY):
    return extract_date_range_v2(msg, today=today)


# ═════════════════════════════════════════════
#  1. 无年份 H1/H2（大小写）
# ═════════════════════════════════════════════
class TestBareHalfYear:
    @pytest.mark.parametrize('msg', ['H1', 'h1'])
    def test_h1_current_year(self, msg):
        r = parse(msg)
        assert (r.start, r.end) == ('2026-01-01', '2026-06-30')

    @pytest.mark.parametrize('msg', ['H2', 'h2'])
    def test_h2_current_year(self, msg):
        r = parse(msg)
        assert (r.start, r.end) == ('2026-07-01', '2026-12-31')

    def test_h1_fields(self):
        r = parse('H1')
        assert r.range_type == 'range'
        assert r.granularity == 'half_year'
        assert r.recognition_status == 'ok'
        assert r.label == '2026H1'
        assert r.original_text == 'H1'

    def test_bare_is_relative(self):
        """无年份表达随 today 变化，is_relative=True。"""
        assert parse('H1').is_relative is True
        assert parse('h2').is_relative is True

    def test_follows_today(self):
        r = parse('H1', today=datetime(2030, 3, 1))
        assert (r.start, r.end) == ('2030-01-01', '2030-06-30')


# ═════════════════════════════════════════════
#  2. 指定年份 H1/H2 + 空格/「年」字变体
# ═════════════════════════════════════════════
class TestExplicitYearHalfYear:
    @pytest.mark.parametrize('msg', ['2025H1', '2025 H1', '2025年H1', '2025h1'])
    def test_2025_h1_variants(self, msg):
        r = parse(msg)
        assert (r.start, r.end) == ('2025-01-01', '2025-06-30')
        assert r.label == '2025H1'

    @pytest.mark.parametrize('msg', ['2025H2', '2025 H2', '2025年H2', '2025h2'])
    def test_2025_h2_variants(self, msg):
        r = parse(msg)
        assert (r.start, r.end) == ('2025-07-01', '2025-12-31')
        assert r.label == '2025H2'

    def test_explicit_year_not_relative(self):
        """指定年份不随 today 变化，is_relative=False。"""
        assert parse('2025H1').is_relative is False

    def test_explicit_year_granularity(self):
        r = parse('2025H2')
        assert r.granularity == 'half_year'
        assert r.range_type == 'range'
        assert r.recognition_status == 'ok'

    def test_original_text_preserved(self):
        assert parse('2025年H1').original_text == '2025年H1'

    def test_embedded_in_sentence(self):
        r = parse('查询2025H2的数据')
        assert (r.start, r.end) == ('2025-07-01', '2025-12-31')
        assert r.original_text == '2025H2'


# ═════════════════════════════════════════════
#  3. 半年范围
# ═════════════════════════════════════════════
class TestHalfYearRange:
    @pytest.mark.parametrize('msg', ['H1到H2', 'H1至H2', 'H1~H2'])
    def test_full_year_range(self, msg):
        r = parse(msg)
        assert (r.start, r.end) == ('2026-01-01', '2026-12-31')
        assert r.granularity == 'half_year'

    def test_range_label(self):
        assert parse('H1到H2').label == '2026H1~2026H2'

    def test_explicit_year_range(self):
        r = parse('2025H1到2025H2')
        assert (r.start, r.end) == ('2025-01-01', '2025-12-31')
        assert r.is_relative is False

    def test_range_wins_over_single(self):
        """H1到H2 不能被单个 H1 截获（否则 end 会是 06-30）。"""
        assert parse('H1到H2').end == '2026-12-31'

    def test_cross_year_range_not_supported(self):
        """
        跨年份半年范围暂不支持，不得给出错误区间。
        允许退化为识别其中单个半年，但绝不能返回 2025-07-01~2026-06-30。
        """
        r = parse('2025H2到2026H1')
        assert (r.start, r.end) != ('2025-07-01', '2026-06-30')

    def test_reversed_range_not_supported(self):
        """H2到H1 顺序颠倒，不应产出反向区间。"""
        r = parse('H2到H1')
        if r.recognition_status == 'ok':
            assert r.start <= r.end


# ═════════════════════════════════════════════
#  4. 与「近半年」的碰撞
# ═════════════════════════════════════════════
class TestRecentHalfYearCollision:
    def test_recent_half_year_still_sliding(self):
        """「近半年」必须保持滑动 183 天，不得变成 H1/H2。"""
        r = parse('近半年')
        assert (r.start, r.end) != ('2026-01-01', '2026-06-30')
        assert (r.start, r.end) != ('2026-07-01', '2026-12-31')
        assert r.end == '2026-08-09'

    def test_recent_half_year_span(self):
        r = parse('近半年')
        span = (datetime.strptime(r.end, '%Y-%m-%d')
                - datetime.strptime(r.start, '%Y-%m-%d')).days
        assert span == 183

    def test_recent_half_year_not_half_year_granularity(self):
        assert parse('近半年').granularity != 'half_year'

    @pytest.mark.parametrize('msg', ['上半年', '下半年'])
    def test_chinese_half_year_unchanged(self, msg):
        """裸「上半年/下半年」仍走原解析器，行为不变。"""
        r = parse(msg)
        expected = ('2026-01-01', '2026-06-30') if msg == '上半年' else ('2026-07-01', '2026-12-31')
        assert (r.start, r.end) == expected


# ═════════════════════════════════════════════
#  5. 与年份解析的优先级
# ═════════════════════════════════════════════
class TestYearPriority:
    def test_2025h1_not_captured_as_full_year(self):
        """2025H1 不能被「2025年」先截获成整年。"""
        r = parse('2025H1')
        assert (r.start, r.end) != ('2025-01-01', '2025-12-31')
        assert r.end == '2025-06-30'

    def test_plain_year_unchanged(self):
        """不含 H 的年份表达行为不变。"""
        r = parse('2025年')
        assert (r.start, r.end) == ('2025-01-01', '2025-12-31')

    def test_quarter_unchanged(self):
        r = parse('2025Q1')
        assert (r.start, r.end) == ('2025-01-01', '2025-03-31')


# ═════════════════════════════════════════════
#  6. 非法表达与误识别防护
# ═════════════════════════════════════════════
class TestInvalidHalfYear:
    @pytest.mark.parametrize('msg', ['H0', 'H3', 'H9', 'H5'])
    def test_invalid_half_index(self, msg):
        """H0/H3/H9 不是合法半年，不得识别为 half_year。"""
        assert parse(msg).granularity != 'half_year'

    @pytest.mark.parametrize('msg', ['H', 'Hello', 'HH', '这是H级客户'])
    def test_isolated_h_not_matched(self, msg):
        """普通文本中孤立字母 H 不应误识别为半年。"""
        assert parse(msg).granularity != 'half_year'

    @pytest.mark.parametrize('msg', ['H12', 'H10'])
    def test_h_followed_by_digit(self, msg):
        """H12 不应被当成 H1。"""
        assert parse(msg).granularity != 'half_year'

    @pytest.mark.parametrize('msg', ['ABH1', 'XH2'])
    def test_letter_prefixed_h_not_matched(self, msg):
        """字母紧邻的 H1 属于标识符片段，不应识别。"""
        assert parse(msg).granularity != 'half_year'

    def test_invalid_returns_valid_daterange(self):
        """非法表达仍返回 DateRange，不抛异常。"""
        r = parse('H9')
        assert r is not None
        assert hasattr(r, 'recognition_status')
