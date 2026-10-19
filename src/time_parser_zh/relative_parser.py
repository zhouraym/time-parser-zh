"""相对时间表达：最近N天/周/月/年、近半年、今天/昨天等单日同义词。"""

import re
from datetime import datetime, timedelta
from typing import Optional

from time_parser_zh.models import HALF_YEAR_DAYS, YEAR_DAYS, DateRange
from time_parser_zh.normalization import (
    _fmt,
    _months_ago,
    _parse_cn_number,
)


def _parse_relative_time(msg: str, today: datetime) -> Optional[DateRange]:
    """
    相对时间：
    - 最近7天 / 最近3天 / 最近一周 / 最近2周
    - 近3个月 / 近半年 / 近一年 / 近1年
    - 近 N 天/周/月/年（含中文数字：最近两年、近三年、这几年、前两年）
    """
    # 近半年 / 最近半年 / 过去半年
    if re.search(r'(?:近|最近|过去)半年', msg):
        s = today - timedelta(days=HALF_YEAR_DAYS)
        return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='day',
                         original_text='近半年', label='近半年', is_relative=True)

    # 近一年 / 最近1年 / 过去一年 / 近1年
    if re.search(r'(?:近|最近|过去)(?:一年|1年)', msg):
        s = today - timedelta(days=YEAR_DAYS)
        return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='day',
                         original_text='近一年', label='近一年', is_relative=True)

    # 近N天 / 近N日（含中文数字）
    m = re.search(r'(?:近|最近|过去)\s*(\d+|一|两|二|三|四|五|六|七|八|九|十|十几|二十|三十)\s*天', msg)
    if m:
        n = _parse_cn_number(m.group(1))
        if n:
            s = today - timedelta(days=n - 1)  # 包含今天
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='day',
                             original_text=m.group(0), label=f'近{n}天', is_relative=True)

    # 近N周 / 最近N周（含中文数字）
    m = re.search(r'(?:近|最近|过去)\s*(\d+|一|两|二|三|四|五|六|七|八|九|十|十几|二十)\s*周', msg)
    if m:
        n = _parse_cn_number(m.group(1))
        if n:
            s = today - timedelta(weeks=n)
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='day',
                             original_text=m.group(0), label=f'近{n}周', is_relative=True)

    # 近N月 / 最近N月（含中文数字）
    m = re.search(r'(?:近|最近|过去)\s*(\d+|一|两|二|三|四|五|六|七|八|九|十|十几|二十)\s*个?月', msg)
    if m:
        n = _parse_cn_number(m.group(1))
        if n:
            s = _months_ago(today, n)
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='day',
                             original_text=m.group(0), label=f'近{n}个月', is_relative=True)

    # 近N年 / 最近N年 / 过去N年 / 这N年 / 前N年（含中文数字 + "几年"）
    m = re.search(r'(?:近|最近|过去|这|前)\s*(\d+|一|两|二|三|四|五|六|七|八|九|十|十几|二十|几)\s*年', msg)
    if m:
        n = _parse_cn_number(m.group(1))
        if n:
            try:
                s = today.replace(year=today.year - n)
            except ValueError:
                # 闰年 2-29 边界处理
                s = today.replace(year=today.year - n, day=28)
            return DateRange(_fmt(s), _fmt(today), range_type='range', granularity='day',
                             original_text=m.group(0), label=f'近{n}年', is_relative=True)

    return None


def _parse_single_day(msg: str, today: datetime) -> Optional[DateRange]:
    """单日同义词：今天/昨天/前天/当天/今日/今儿/前日/昨日"""
    # 顺序很重要：从长到短，避免 "今天" 匹到 "今" 后没匹 "天"
    mapping = [
        (r'前天|前日', -2, '前天'),
        (r'大前天', -3, '大前天'),
        (r'昨天|昨日', -1, '昨天'),
        (r'今天|今日|当天|本日|今儿', 0, '今天'),
        (r'明天|明日', 1, '明天'),
        (r'后天|后日', 2, '后天'),
    ]
    for pat, delta, label in mapping:
        if re.search(pat, msg):
            d = today + timedelta(days=delta)
            return DateRange(_fmt(d), _fmt(d), range_type='point', granularity='day',
                             original_text=label, label=label, is_relative=True)
    return None
