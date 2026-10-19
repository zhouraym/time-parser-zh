"""ComparisonRange 数据类测试。"""

import json
from datetime import datetime

import pytest

from zh_time_parser import ComparisonRange, DateRange, extract_comparison_range


def dr(start='2026-08-01', end='2026-08-09', **kw):
    return DateRange(start, end, **kw)


class TestConstruction:
    def test_basic_construction(self):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')
        assert c.current.start == '2026-08-01'
        assert c.comparison.start == '2025-08-01'
        assert c.comparison_type == 'yoy'

    def test_default_fields(self):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')
        assert c.original_text == ''
        assert c.label == ''
        assert c.confidence == 1.0

    @pytest.mark.parametrize('ctype', ['yoy', 'previous_period'])
    def test_valid_comparison_types(self, ctype):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type=ctype)
        assert c.comparison_type == ctype


class TestValidation:
    def test_invalid_comparison_type_rejected(self):
        with pytest.raises(ValueError):
            ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='mom')

    def test_empty_current_rejected(self):
        """current 必须是有效 DateRange（start/end 均非 None）。"""
        with pytest.raises(ValueError):
            ComparisonRange(current=DateRange(None, None),
                            comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')

    def test_empty_comparison_rejected(self):
        with pytest.raises(ValueError):
            ComparisonRange(current=dr(), comparison=DateRange(None, None),
                            comparison_type='yoy')

    def test_non_daterange_rejected(self):
        with pytest.raises(ValueError):
            ComparisonRange(current='2026-08-01',
                            comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')


class TestToDict:
    def test_to_dict_keys(self):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy', label='L', original_text='本月同比')
        d = c.to_dict()
        assert set(d) == {'current', 'comparison', 'comparison_type',
                          'original_text', 'label', 'confidence'}

    def test_nested_ranges_are_dicts(self):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')
        d = c.to_dict()
        assert isinstance(d['current'], dict)
        assert isinstance(d['comparison'], dict)
        assert d['current']['start'] == '2026-08-01'

    def test_json_serializable(self):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')
        text = json.dumps(c.to_dict(), ensure_ascii=False)
        assert json.loads(text)['comparison_type'] == 'yoy'

    def test_parsed_result_json_serializable(self):
        c = extract_comparison_range('Q2环比', today=datetime(2026, 8, 9))
        json.dumps(c.to_dict(), ensure_ascii=False)


class TestRepr:
    def test_repr_contains_both_ranges(self):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')
        text = repr(c)
        assert '2026-08-01' in text and '2025-08-01' in text

    def test_repr_marks_yoy(self):
        c = ComparisonRange(current=dr(), comparison=dr('2025-08-01', '2025-08-09'),
                            comparison_type='yoy')
        assert '同比' in repr(c)

    def test_repr_marks_previous_period(self):
        c = ComparisonRange(current=dr(), comparison=dr('2026-07-01', '2026-07-09'),
                            comparison_type='previous_period')
        assert '环比' in repr(c)


class TestExports:
    def test_exported_from_package_root(self):
        import zh_time_parser
        assert 'ComparisonRange' in zh_time_parser.__all__
        assert 'extract_comparison_range' in zh_time_parser.__all__

    def test_no_v3_alias(self):
        """不得提供 extract_date_range_v3 这个命名。"""
        import zh_time_parser
        assert not hasattr(zh_time_parser, 'extract_date_range_v3')
