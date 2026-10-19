"""
DateRange 数据类自身的行为测试。

覆盖 README 中承诺的对外契约：to_dict()、__bool__、tuple 兼容、字段默认值。
"""

from datetime import datetime

import pytest

from zh_time_parser import DateRange, extract_date_range_v2

FIXED_TODAY = datetime(2026, 5, 24)


class TestToDict:
    """to_dict() —— README 承诺存在，必须真实可用"""

    def test_to_dict_returns_plain_dict(self):
        d = DateRange('2026-05-01', '2026-05-24', label='本月').to_dict()
        assert isinstance(d, dict)
        assert d['start'] == '2026-05-01'
        assert d['end'] == '2026-05-24'
        assert d['label'] == '本月'

    def test_to_dict_contains_all_public_fields(self):
        """所有文档化字段都应出现在 to_dict() 中"""
        d = DateRange().to_dict()
        expected = {
            'start', 'end', 'range_type', 'granularity', 'original_text',
            'label', 'is_relative', 'includes_end', 'week_start',
            'confidence', 'recognition_status', 'point', 'boundary',
        }
        assert expected <= set(d)

    def test_to_dict_is_json_serializable(self):
        import json
        r = extract_date_range_v2('上个月', today=FIXED_TODAY)
        # 不抛异常即可，且能还原
        assert json.loads(json.dumps(r.to_dict(), ensure_ascii=False))['start'] == '2026-04-01'

    def test_to_dict_is_a_copy(self):
        """修改返回的 dict 不应影响原对象"""
        r = DateRange('2026-05-01', '2026-05-24')
        d = r.to_dict()
        d['start'] = 'tampered'
        assert r.start == '2026-05-01'


class TestBoolSemantics:
    """__bool__ —— 实现要求 start 和 end 同时存在"""

    def test_true_when_both_present(self):
        assert bool(DateRange('2026-05-01', '2026-05-24')) is True

    def test_false_when_empty(self):
        assert bool(DateRange()) is False

    def test_false_when_only_start(self):
        """只有 start 没有 end → False（README 曾错写为「有 start 即为真」）"""
        assert bool(DateRange(start='2026-05-01')) is False

    def test_false_when_only_end(self):
        assert bool(DateRange(end='2026-05-24')) is False


class TestTupleCompatibility:
    """旧 API 兼容：解包 / 索引 / 与 tuple 比较"""

    def test_unpacking(self):
        start, end = DateRange('2026-05-01', '2026-05-24')
        assert (start, end) == ('2026-05-01', '2026-05-24')

    def test_indexing(self):
        r = DateRange('2026-05-01', '2026-05-24')
        assert r[0] == '2026-05-01'
        assert r[1] == '2026-05-24'

    def test_equals_tuple(self):
        assert DateRange('2026-05-01', '2026-05-24') == ('2026-05-01', '2026-05-24')

    def test_to_tuple(self):
        assert DateRange('2026-05-01', '2026-05-24').to_tuple() == ('2026-05-01', '2026-05-24')


class TestFieldDefaults:
    """字段默认值 —— README 字段表的依据"""

    def test_defaults(self):
        r = DateRange()
        assert r.range_type == 'range'
        assert r.granularity == 'day'
        assert r.is_relative is False
        assert r.includes_end is True
        assert r.week_start == 'monday'
        assert r.confidence == 1.0
        assert r.recognition_status == 'ok'
        assert r.point is None
        assert r.boundary is None

    def test_granularity_differs_from_range_type(self):
        """granularity 与 range_type 是两个维度，不可混为一谈"""
        r = extract_date_range_v2('到2027年末', today=FIXED_TODAY)
        assert r.range_type == 'range'
        assert r.granularity == 'year'

    def test_point_and_boundary_filled_for_cutoff(self):
        """截止点表达会填充 point / boundary"""
        r = extract_date_range_v2('到2027年末', today=FIXED_TODAY)
        assert r.point == '2027-12-31'
        assert r.boundary == 'end'

    def test_point_is_none_for_plain_range(self):
        """普通区间不填 point"""
        r = extract_date_range_v2('上个月', today=FIXED_TODAY)
        assert r.point is None
        assert r.boundary is None

    def test_week_start_recorded(self):
        r = extract_date_range_v2('本周', today=FIXED_TODAY, week_start='sunday')
        assert r.week_start == 'sunday'

    @pytest.mark.parametrize('text,expected', [
        ('最近7天', True),
        ('2026-04-01 至 2026-04-30', False),
    ])
    def test_is_relative(self, text, expected):
        assert extract_date_range_v2(text, today=FIXED_TODAY).is_relative is expected


class TestReadmeExamples:
    """锁定 README 里写出的示例输出，防止文档与实现再次不一致"""

    def test_last_month_example(self):
        r = extract_date_range_v2('上个月', today=datetime(2026, 5, 24))
        assert r.start == '2026-04-01'
        assert r.end == '2026-04-30'
        assert r.label == '上个月'
        # README 曾错写成 range_type == 'month'，实际 month 是 granularity
        assert r.range_type == 'range'
        assert r.granularity == 'month'

    def test_recent_7_days_example(self):
        r = extract_date_range_v2('最近7天', today=datetime(2026, 8, 9))
        assert (r.start, r.end) == ('2026-08-03', '2026-08-09')

    def test_unrecognized_example(self):
        r = extract_date_range_v2('张三 有 12345 个')
        assert bool(r) is False
        assert r.recognition_status == 'no_time_phrase'

    def test_cutoff_point_example(self):
        r = extract_date_range_v2('到2027年末', today=FIXED_TODAY)
        assert (r.start, r.end) == ('2027-01-01', '2027-12-31')
        assert r.point == '2027-12-31'
        assert r.boundary == 'end'
