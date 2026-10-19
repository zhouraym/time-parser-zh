"""格式化、校验与中文数字等基础工具。"""

import calendar
import re
from datetime import datetime
from typing import Optional, Tuple


def _fmt(d: datetime) -> str:
    """datetime → 'YYYY-MM-DD'"""
    return d.strftime('%Y-%m-%d')


def _is_valid_year(y: int) -> bool:
    """合理的年份范围"""
    return 1900 <= y <= 2100


def _normalize_date_str(s: str) -> Optional[str]:
    """把 '2026/4/5' / '20260405' 标准化成 '2026-04-05'"""
    s = s.replace('/', '-')
    # 20260401 → 2026-04-01
    if re.match(r'^\d{8}$', s):
        s = f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    # 补零
    try:
        d = datetime.strptime(s, '%Y-%m-%d')
        return d.strftime('%Y-%m-%d')
    except ValueError:
        return None


_CN_DIGITS = {
    '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}


def _parse_cn_number(s: str) -> Optional[int]:
    """把阿拉伯数字或中文数字（一/两/三/十/十几/二十）转成 int。
    无法解析返回 None。
    """
    if not s:
        return None
    # 阿拉伯数字
    if s.isdigit():
        return int(s)
    # “几”是未指定数量，不能替用户猜成任何具体数字。
    if s == '几':
        return None
    # 中文"十几" → 10 + 个位
    if s.startswith('十') and len(s) == 2 and s[1] in _CN_DIGITS:
        return 10 + _CN_DIGITS[s[1]]
    # 中文"十"
    if s == '十':
        return 10
    # 中文"二十/三十"等
    if len(s) == 2 and s[0] == '十' and s[1] in _CN_DIGITS:
        return 10 + _CN_DIGITS[s[1]]
    if len(s) == 2 and s[1] == '十' and s[0] in _CN_DIGITS:
        return _CN_DIGITS[s[0]] * 10
    if len(s) == 3 and s[1] == '十' and s[0] in _CN_DIGITS and s[2] in _CN_DIGITS:
        return _CN_DIGITS[s[0]] * 10 + _CN_DIGITS[s[2]]
    # 单个中文数字
    if len(s) == 1 and s in _CN_DIGITS:
        return _CN_DIGITS[s]
    return None


def _months_ago(today: datetime, n: int) -> datetime:
    """n 个月前的今天（处理跨年）"""
    month = today.month - n
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(today.day, _days_in_month(year, month))
    return datetime(year, month, day)


def _full_month_range(year: int, month: int) -> Tuple[datetime, datetime]:
    """某年某月的完整范围（1 号 ~ 最后一天）"""
    last_day = _days_in_month(year, month)
    return datetime(year, month, 1), datetime(year, month, last_day)


def _n_months_before_range(today: datetime, n: int) -> Tuple[datetime, datetime]:
    """n 个月前的完整月范围（1 号 ~ 最后一天）"""
    target_month = today.month - n
    target_year = today.year
    while target_month <= 0:
        target_month += 12
        target_year -= 1
    return _full_month_range(target_year, target_month)


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]
