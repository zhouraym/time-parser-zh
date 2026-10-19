"""边界与截止点表达：到X/截至X（point + boundary）、截至某日。"""

import re
from datetime import datetime
from typing import Optional

from zh_time_parser.models import DateRange
from zh_time_parser.normalization import (
    _days_in_month,
    _fmt,
    _normalize_date_str,
)


def _parse_as_of_point(msg: str, today: datetime) -> Optional[DateRange]:
    """
    解析"到/截至/截止 + 具体日"为截止点（point），供调用方做"截至某日"的时点计算。

    设计约束（不破坏任何原有解析）：
      - 仅当消息含"到/截至/截止"前缀（或明确"月底/月末/年末"结束边界）时才可能命中；
      - 不触碰无前缀表达（"本月/上个月/5号到15号/月初到月末"等仍由原 parser 处理）；
      - start/end 仍保留完整范围（如"到月底"→ start=月初, end=月底），仅额外填充
        point=截止日、boundary="end"，使时点计算与区间统计互不影响；
      - 与 _parse_misc 对"到2026年8月31日"的结果一致（都是 point），只是更早命中，行为不变。
    """
    # 匹配顺序（严格由具体到宽泛，避免相对"月底/年末"抢走指定年月）：
    #   1) 指定年份年末：到2027年末 / 截至2026年底
    #   2) 指定月份月底：到12月底 / 截至8月末
    #   3) 明确日期：到2026年8月31日 / 到8月31日 / 到本月15号
    #   4) 相对表达：本月底 / 月底 / 本年末（无"到"前缀、当前月年）

    # 1) 到 X年底 / 到 X年末（指定年份的年末，如"到2027年末"，必须排在笼统"年底/年末"之前）
    m = re.search(r'(?:到|截至|截止)\s*(\d{4})\s*(年底|年末)', msg)
    if m:
        y = int(m.group(1))
        d = datetime(y, 12, 31)
        return DateRange(
            _fmt(datetime(y, 1, 1)), _fmt(d),
            point=_fmt(d), boundary='end', range_type='range', granularity='year',
            original_text=m.group(0), label=f"截至{y}年底", is_relative=True,
        )

    # 2) 到 X月底 / 到 X月末（指定月份，如 到12月底 / 截至8月末，必须排在"月底/月末"之前）
    m = re.search(r'(?:到|截至|截止)\s*(\d{1,2})\s*(月底|月末|最后一天)', msg)
    if m:
        mo = int(m.group(1))
        if 1 <= mo <= 12:
            last = _days_in_month(today.year, mo)
            d = datetime(today.year, mo, last)
            return DateRange(
                _fmt(datetime(today.year, mo, 1)), _fmt(d),
                point=_fmt(d), boundary='end', range_type='range', granularity='month',
                original_text=m.group(0), label=f"截至{mo}月底", is_relative=True,
            )

    # 3) 到 2026年8月31日 / 到2026-08-31（完整日期，与 _parse_misc 结果一致）
    m = re.search(r'(?:到|截至|截止)\s*(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})\s*[日号]?', msg)
    if m:
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return DateRange(_fmt(d), _fmt(d), point=_fmt(d), boundary='end',
                             range_type='point', granularity='day',
                             original_text=m.group(0), label=_fmt(d), is_relative=True)
        except ValueError:
            pass

    # 3.5) 到 X月X日 / 到 8 月 31 日（无年份，用当前年，支持数字间空格）
    m = re.search(r'(?:到|截至|截止)\s*(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?', msg)
    if m:
        mo, day = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= day <= 31:
            try:
                d = datetime(today.year, mo, day)
                return DateRange(_fmt(d), _fmt(d), point=_fmt(d), boundary='end',
                                 range_type='point', granularity='day',
                                 original_text=m.group(0), label=_fmt(d), is_relative=True)
            except ValueError:
                pass

    # 3.7) 到 这个月15号 / 到本月15号 / 到15号（仅截止端、无起始号，明确带"到/截至/截止"前缀）
    #      注意：前面无起始号（"5号到15号"已由 _parse_day_range 先命中，不到这里）。
    m = re.search(r'(?:到|截至|截止)\s*(?:这个月|本月|当月)?\s*(\d{1,2})\s*[日号]', msg)
    if m:
        day = int(m.group(1))
        if 1 <= day <= 31:
            try:
                d = datetime(today.year, today.month, day)
                return DateRange(_fmt(d), _fmt(d), point=_fmt(d), boundary='end',
                                 range_type='point', granularity='day',
                                 original_text=m.group(0), label=_fmt(d), is_relative=True)
            except ValueError:
                pass

    # 3.9) 相对月份结束点：上月底 / 上上月底 / 下月底（带"到/截至/截止"前缀）
    #      必须放在宽泛"月底/月末"规则之前，否则会被后半段正则只截到"月底"当成当前月。
    #      同时支持"上上月/上月/下月 + 底/末"与"上上月底"连写两种写法。
    m = re.search(r'(?:到|截至|截止)\s*(去年|今年|明年|上上[个]?月|上[个]?月|下[个]?月)\s*(?:底|末|年底|年末)', msg)
    if m:
        offset_word = m.group(1).replace('个', '')
        if offset_word == "去年":
            y = today.year - 1
            d = datetime(y, 12, 31)
            return DateRange(_fmt(datetime(y, 1, 1)), _fmt(d),
                             point=_fmt(d), boundary='end', range_type='range', granularity='year',
                             original_text=m.group(0), label=f"截至{y}年底", is_relative=True)
        if offset_word == "今年":
            y = today.year
            d = datetime(y, 12, 31)
            return DateRange(_fmt(datetime(y, 1, 1)), _fmt(d),
                             point=_fmt(d), boundary='end', range_type='range', granularity='year',
                             original_text=m.group(0), label=f"截至{y}年底", is_relative=True)
        if offset_word == "明年":
            y = today.year + 1
            d = datetime(y, 12, 31)
            return DateRange(_fmt(datetime(y, 1, 1)), _fmt(d),
                             point=_fmt(d), boundary='end', range_type='range', granularity='year',
                             original_text=m.group(0), label=f"截至{y}年底", is_relative=True)
        # 月份级相对偏移
        if offset_word == "下月":
            mo = today.month + 1
            y = today.year
        elif offset_word == "上月":
            mo = today.month - 1
            y = today.year
        else:  # 上上月
            mo = today.month - 2
            y = today.year
        # 跨年借位
        while mo <= 0:
            mo += 12
            y -= 1
        while mo > 12:
            mo -= 12
            y += 1
        last = _days_in_month(y, mo)
        d = datetime(y, mo, last)
        return DateRange(_fmt(datetime(y, mo, 1)), _fmt(d),
                         point=_fmt(d), boundary='end', range_type='range', granularity='month',
                         original_text=m.group(0), label=f"截至{d.year}年{d.month}月底", is_relative=True)

    # 4) 相对表达（无"到"前缀、当前月年的结束边界）：本月底 / 月底 / 本月末 / 本年末
    #    必须放在指定年月规则之后，否则"到12月底"会被这里抢成当前月。
    m = re.search(r'(?:到|截至|截止)\s*(?:本)?\s*(年底|年末|月底|月末)', msg)
    if not m:
        # 防止“13月底”这类非法指定月跳过上面的范围校验后，又被后缀
        # “月底”误当成当前月月底。
        m = re.search(r'(?:本)\s*(年底|年末)|(?<!\d)(?:本)?\s*(月底|月末)', msg)
    if m:
        token = m.group(1) or m.group(2)
        if token in ('月底', '月末'):
            last = _days_in_month(today.year, today.month)
            d = datetime(today.year, today.month, last)
            return DateRange(
                _fmt(datetime(today.year, today.month, 1)), _fmt(d),
                point=_fmt(d), boundary='end', range_type='range', granularity='month',
                original_text=m.group(0), label=f"截至{d.month}月底", is_relative=True,
            )
        else:  # 本年底/本年末（带"本"的年级结束边界）
            d = datetime(today.year, 12, 31)
            return DateRange(
                _fmt(datetime(today.year, 1, 1)), _fmt(d),
                point=_fmt(d), boundary='end', range_type='range', granularity='year',
                original_text=m.group(0), label=f"截至{today.year}年底", is_relative=True,
            )

    return None


def _parse_misc(msg: str, today: datetime) -> Optional[DateRange]:
    """
    杂项：截至某日 / 截止某日
    """
    m = re.search(r'(?:截至|截止|到)\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', msg)
    if m:
        s = _normalize_date_str(m.group(1).replace('年', '-').replace('月', '-').rstrip('-日号'))
        if s:
            return DateRange(s, s, range_type='point', granularity='day',
                             original_text=m.group(0), label=f"截至{s}", is_relative=True)

    return None
