"""多范围连接符不得静默降级为部分结果。"""

from datetime import datetime

import pytest

from zh_time_parser import extract_date_range_v2, extract_datetime_range

TODAY = datetime(2026, 8, 11, 12, 0)


@pytest.mark.parametrize(
    'text',
    [
        '从3月到5月到昨天',
        '3月到5月到昨天',
        '从3月到5月，截至昨天',
    ],
)
def test_date_range_rejects_multiple_connectors(text):
    result = extract_date_range_v2(text, today=TODAY)
    assert not result
    assert result.recognition_status == 'phrase_not_supported'
    assert '多个范围连接符' in result.label


def test_datetime_range_rejects_multiple_connectors():
    result = extract_datetime_range('从3月到5月到昨天', today=TODAY)
    assert not result
    assert result.start is None and result.end is None
    assert result.recognition_status == 'phrase_not_supported'


def test_business_word_daoqi_is_not_counted_as_connector():
    result = extract_date_range_v2('8月1日至昨天的到期金额', today=TODAY)
    assert result.recognition_status != 'phrase_not_supported' or '多个范围连接符' not in result.label


def test_normal_single_range_still_works():
    result = extract_date_range_v2('3月到5月', today=TODAY)
    assert (result.start, result.end) == ('2026-03-01', '2026-05-31')
