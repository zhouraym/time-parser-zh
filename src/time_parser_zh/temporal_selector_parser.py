"""“最近一次 / 最早一次 / 最近3次”这类事件顺序选择器。"""

import re
from datetime import datetime
from typing import Optional, Tuple

from time_parser_zh.date_parser import extract_date_range_v2
from time_parser_zh.models import TemporalSelector
from time_parser_zh.normalization import _parse_cn_number

_NUMBER = r'(?:\d+|[一二两三四五六七八九十]+)'

# 强规则在前，避免“倒数第二次”被普通“第二次”截获。
_PATTERNS = (
    (re.compile(rf'倒数第\s*(?P<n>{_NUMBER})\s*次'), 'latest', 'rank_from_end'),
    (re.compile(rf'第\s*(?P<n>{_NUMBER})\s*次'), 'earliest', 'rank_from_start'),
    (re.compile(rf'(?:最近|近|最后|前)\s*(?P<n>{_NUMBER})\s*次'), 'latest', 'limit'),
    (re.compile(r'(?:最近|最后)(?:的)?一次|上一次'), 'latest', 'one'),
    (re.compile(r'最早(?:的)?一次|第一次'), 'earliest', 'one'),
)


def _number(raw: str) -> Optional[int]:
    return int(raw) if raw.isdigit() else _parse_cn_number(raw)


def _parse_selector(msg: str) -> Optional[Tuple[re.Match, str, int, int]]:
    for pattern, order, mode in _PATTERNS:
        match = pattern.search(msg)
        if not match:
            continue
        if mode == 'one':
            return match, order, 1, 0
        value = _number(match.group('n'))
        if value is None or value <= 0:
            return None
        if mode in ('rank_from_end', 'rank_from_start'):
            return match, order, 1, value - 1
        return match, order, value, 0
    return None


def _normalize_date_context(text: str) -> str:
    """去掉日期范围外层常见介词，不改变业务正文或日期短语本身。"""
    normalized = text.strip(' ，,。；;')
    normalized = re.sub(r'^\s*(?:在|于)\s*', '', normalized)
    normalized = re.sub(r'\s*(?:的)?(?:范围)?(?:之内|以内|内|里|期间)\s*$', '', normalized)
    return normalized.strip()


def extract_temporal_selector(user_message: str, today: Optional[datetime] = None,
                              week_start: str = 'monday') -> TemporalSelector:
    """解析事件顺序选择器，并把同句中的日期限制解析为可选 DateRange。"""
    if today is None:
        today = datetime.now()
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')
    if week_start not in ('monday', 'sunday'):
        raise ValueError("week_start 必须是 'monday' 或 'sunday'")

    msg = user_message.strip()
    if not msg:
        return TemporalSelector(recognition_status='no_time_phrase')

    parsed = _parse_selector(msg)
    if not parsed:
        return TemporalSelector(
            original_text=msg,
            confidence=0.0,
            recognition_status='no_time_phrase',
        )

    match, order, limit, offset = parsed
    # 只剥离已命中的选择器；其余文本继续交给稳定的 DateRange 入口。
    remaining = _normalize_date_context(f'{msg[:match.start()]} {msg[match.end():]}')
    date_range = None
    if remaining:
        candidate = extract_date_range_v2(remaining, today=today, week_start=week_start)
        if candidate:
            date_range = candidate

    return TemporalSelector(
        order=order,
        limit=limit,
        offset=offset,
        date_range=date_range,
        original_text=msg,
        selector_text=match.group(0),
    )
