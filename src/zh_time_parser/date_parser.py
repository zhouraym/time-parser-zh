"""
日期解析主入口 —— 把中文时间表达（"昨天"、"上个月"、"最近7天"、"Q1"等）
和日期范围（"2026-04-01 至 2026-04-30"）转换成具体日期。

提供两层 API：
- 旧 API（向后兼容）：extract_date_range() / parse_time_expression() 返回 (start, end) tuple
- 新 API（推荐）：extract_date_range_v2() 返回 DateRange 结构化对象

支持的表达（节选）：
- 精确日期：2026-04-15、2026/04/15、2026年4月15日
- 单日同义词：今天/今日/当天/本日/今儿/昨天/昨日/前日/前天
- 本周/上周/下周/上上周（支持 monday/sunday 起始日）
- 本月/上个月/下个月/上上个月/本月一号
- 今年/去年/前年/明年
- 季度：本季度/上季度/下季度/Q1/Q2/Q3/Q4/2026Q1/2026年第一季度
- 跨季度范围：Q1到Q2、一季度到二季度、2026Q1至2026Q3、上季度到本季度
- 跨年范围：去年到今年、2025年到2026年、25年到26年
- 跨月范围：3月到5月、1-3月
- 相对时间：最近N天/周/月/年、近N个月、近半年、近一年
- 月初/月末/年初/年末/年初至今/YTD
- 同期/同比/环比
- 范围：X至Y、~X~Y、从X到Y
- 年份：2025年、25年
- 口述日期范围（口语化）：
  - 号段：5号到15号、3号~8号、1号到今天
  - 中文日期段：3月1号到3月15号、4月5号至4月20号
  - 月+至今：上个月到今天、上个月至今、上月至今
  - 季度+至今：上季度至今、本季度到今天
  - 半年/全年+至今：上半年至今、全年至今
  - 月内段：月初到月末、本月初到本月末
  - 相对月+具体日（单点）：上个月1号、上月15号、下个月1号、本月15号
  - 具体日到今天：上个月1号到今天、4月1号到今天、2026年3月15号到今天
  - 周号段：周一到周三、本周一到周五、上周一到周五
  - 周+至今：本周到今天、上周到今天、本周至今

具体规则按维度拆分在同目录的 *_parser.py 中，本文件只负责调度顺序。
"""

import re
from datetime import datetime
from typing import Optional, Tuple

from zh_time_parser.ambiguous_temporal_parser import extract_ambiguous_temporal
from zh_time_parser.boundary_parser import _parse_as_of_point, _parse_misc
from zh_time_parser.calendar_parser import _parse_calendar_expression
from zh_time_parser.explicit_parser import (
    _parse_chinese_date_range,
    _parse_day_range,
    _parse_exact_date,
    _parse_explicit_date_range,
    _parse_specific_day_to_today,
)
from zh_time_parser.models import DateRange
from zh_time_parser.month_parser import (
    _parse_month,
    _parse_month_span,
    _parse_month_to_today,
    _parse_relative_month_day,
)
from zh_time_parser.quarter_parser import (
    _parse_quarter,
    _parse_quarter_range,
    _parse_quarter_span,
)
from zh_time_parser.range_safety import _has_multiple_range_connectors
from zh_time_parser.relative_parser import _parse_relative_time, _parse_single_day
from zh_time_parser.temporal_shift_parser import _parse_temporal_shift
from zh_time_parser.week_parser import (
    _parse_week,
    _parse_week_day_range,
    _parse_week_to_today,
)
from zh_time_parser.year_parser import (
    _parse_half_year,
    _parse_half_year_hx,
    _parse_year,
    _parse_year_range,
)

# 「输入导致」的可预期异常：某个 parser 对畸形输入失败时应静默跳过，
# 让后面的 parser 继续尝试。例如：
#   ValueError    —— datetime(2026, 2, 30)、int('') 等非法值
#   OverflowError —— "最近99999999999999999999天" 这类超大数字
#   KeyError / IndexError —— 查表或分组取值越界
# 刻意**不含** NameError / AttributeError / TypeError：那些是编程错误，
# 必须原样抛出，否则会被静默转成 recognition_status='phrase_not_supported'。
_INPUT_ERRORS = (ValueError, OverflowError, KeyError, IndexError)


# 「明确比较表达」保护词：这些是同比/环比语义，不应被当成普通 DateRange 解析。
# 与 comparison_parser 的明确触发词保持一致（含负向前瞻边界），
# 以免「同比例」「同期生」「同期刊」「同期声」等普通词被误伤成 phrase_not_supported。
# 命中时返回 phrase_not_supported 空区间，调用方应使用 extract_comparison_range() 解析。
_COMPARISON_PHRASE_PAT = re.compile(
    r'同比(?!例)|去年同期|上年同期|较去年同期|比去年同期|同期(?!生|刊|声)|'
    r'环比(?!例)|较上期|比上期'
)


# ═════════════════════════════════════════════════════════
#  主入口（v2）
# ═════════════════════════════════════════════════════════

def extract_date_range_v2(user_message: str, today: Optional[datetime] = None,
                          week_start: str = 'monday') -> DateRange:
    """
    v2 主入口：返回 DateRange 结构化对象。

    带年份的年月日组合及其范围先整体解析，之后按下列顺序调度其它规则：
    1. 范围（X至Y）
    2. 中文日期段（3月1号到3月15号）
    3. 跨季度范围 / 季度+至今（Q1到Q2 / Q1至今）
    4. 月+至今（上个月到今天 / 3月至今）
    5. 当月号段（5号到15号 / 5号到今天）
    6. 半年/全年范围（上半年至今 / 全年至今）
    7. 月内段（月初到月末）
    8. 季度内段（Q1初到Q1末）
    9. 相对时间（最近/近N/近半年/近一年）
    10. 单日同义词（今天/昨天...）
    11. 本周/上周/下周/上上周
    12. 本月/上个月/下个月/上上个月/月初/月末/X月到Y月
    13. 今年/去年/前年/明年/年初至今/年末
    14. 精确日期
    15. 杂项（截至X日）

    全部规则均基于 Python 标准库实现，不依赖任何第三方日期库；
    无法识别时返回空 DateRange（start/end 为 None），绝不整段消息猜测。

    保护：若输入包含明确的比较表达（同比/环比/去年同期/上年同期/较上期/比上期），
    则**不按普通 DateRange 解析**，返回空区间（recognition_status='phrase_not_supported'），
    提示调用方改用 extract_comparison_range()。comparison_parser 会先剥离比较词再调用本函数，
    因此「本月同比」等正常比较解析不受影响（传入的是剥离后的「本月」）。

    Args:
        user_message: 包含中文日期表达的用户消息。
        today: 相对日期的基准时刻，默认使用当前时刻。
        week_start: 自然周起始日，支持 monday 或 sunday。

    Returns:
        结构化日期范围；无效或不支持的表达返回带识别状态的空区间。

    Raises:
        TypeError: user_message 不是字符串。
        ValueError: week_start 不受支持。
    """
    if not isinstance(user_message, str):
        raise TypeError('user_message 必须是 str')
    if week_start not in ('monday', 'sunday'):
        raise ValueError("week_start 必须是 'monday' 或 'sunday'")
    if today is None:
        today = datetime.now()

    msg = user_message.strip()
    if not msg:
        return DateRange(recognition_status='no_time_phrase')

    # 模糊时间防猜保护：识别出意图，但不把“几天”等擅自换算成固定数值。
    # 调用方可用 extract_ambiguous_temporal() 获取 direction/unit 后自行追问或应用策略。
    ambiguous = extract_ambiguous_temporal(msg)
    if ambiguous:
        return DateRange(
            original_text=msg,
            label='模糊时间表达请使用 extract_ambiguous_temporal',
            range_type='unknown',
            confidence=0.0,
            recognition_status='ambiguous',
        )

    # 单个 DateRange 无法安全表达“从3月到5月到昨天”这类多连接符结构。
    # 与其静默丢掉前半段并只返回“昨天”，不如明确拒绝并让上层澄清。
    if _has_multiple_range_connectors(msg):
        return DateRange(
            original_text=msg,
            label='包含多个范围连接符，无法确定唯一日期区间',
            range_type='unknown',
            confidence=0.0,
            recognition_status='phrase_not_supported',
        )

    # 明确比较表达拦截：避免 extract_date_range_v2("去年同期") 误返回去年全年、
    # extract_date_range_v2("上月环比") 误只返回上个月。
    if _COMPARISON_PHRASE_PAT.search(msg):
        return DateRange(
            original_text=msg,
            label='比较表达请使用 extract_comparison_range',
            range_type='unknown',
            confidence=0.0,
            recognition_status='phrase_not_supported',
        )

    # 先组合解析年月日和范围端点，避免“去年8月”被弱月份规则截成“8月”。
    # 返回空 DateRange 表示已识别但日期无效，必须停止，不能再降级匹配。
    calendar_result = _parse_calendar_expression(msg, today)
    if calendar_result is not None:
        return calendar_result

    # 句首明确使用“到/截至/截止”的结构化端点时，先保留 point/boundary 语义，
    # 避免“到本月15号”被普通相对月日期提前解析成无边界的单日，或
    # “截至上上月底”被组合月份位移提前解析成普通月份范围。
    if re.match(r'^(?:到|截至|截止)', msg):
        try:
            as_of = _parse_as_of_point(msg, today)
        except _INPUT_ERRORS:
            as_of = None
        if as_of:
            as_of.recognition_status = 'ok'
            return as_of

        # 已明确写出日历端点、但值本身非法时，不能继续降级成“本月”或
        # “月底”等较宽泛表达，否则会悄悄制造另一个日期。
        malformed_endpoint = re.match(
            r'^(?:到|截至|截止)\s*(?:'
            r'\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*[日号]?|'
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|'
            r'\d{1,2}\s*月\s*\d{1,2}\s*[日号]?|'
            r'(?:这个月|本月|当月)\s*\d{1,2}\s*[日号]|'
            r'\d{1,2}\s*(?:月底|月末|最后一天)'
            r')',
            msg,
        )
        if malformed_endpoint:
            return DateRange(
                original_text=msg,
                label='截止点日期无效',
                range_type='unknown',
                confidence=0.0,
                recognition_status='phrase_not_supported',
            )

    # 检测用户原话是否包含时间词（用于设置 recognition_status）
    has_time_phrase = bool(re.search(
        r'今天|今日|昨天|昨日|前天|前日|明天|明日|'
        r'本周|上周|下周|本星期|上星期|下星期|'
        r'本月|上个月|下个月|'
        r'今年|去年|前年|明年|'
        r'本季度|上季度|下季度|Q[1-4]|'
        r'(?<![A-Za-z\d])[Hh][12](?!\d)|'
        r'最近|近|过去|这|前|'
        r'\d+\s*(?:天|周|月|年)|'
        r'(?:一|两|二|三|四|五|六|七|八|九|十|几)\s*(?:天|周|月|年)|'
        r'\d{4}[-/年]|(?:20|19)\d{2}年|'
        r'年初|年末|年底|上半年|下半年|'
        r'至今|到现在|到今天',
        msg
    ))

    # 顺序很重要：先强匹配（范围、季度），再弱匹配
    parsers = [
        lambda: _parse_explicit_date_range(msg),
        lambda: _parse_chinese_date_range(msg, today),
        lambda: _parse_specific_day_to_today(msg, today),
        # H1/H2 自然半年必须早于 _parse_year_range / _parse_year，
        # 否则 "2025H1" 会被 "2025年" 先截获成整年。
        lambda: _parse_half_year_hx(msg, today),
        lambda: _parse_quarter_range(msg, today),
        lambda: _parse_year_range(msg, today),
        lambda: _parse_month_to_today(msg, today),
        lambda: _parse_week_to_today(msg, today, week_start),
        lambda: _parse_week_day_range(msg, today, week_start),
        lambda: _parse_relative_month_day(msg, today),
        lambda: _parse_day_range(msg, today),
        # 组合月份位移必须晚于“月到今天/相对月具体日”等强规则，但早于普通月/季度，
        # 避免“上上上个月”被截成“上上个月”、“上个月的下个月”被截成“上个月”。
        lambda: _parse_temporal_shift(msg, today),
        lambda: _parse_half_year(msg, today),
        lambda: _parse_month_span(msg, today),
        lambda: _parse_quarter_span(msg, today),
        lambda: _parse_quarter(msg, today),
        lambda: _parse_relative_time(msg, today),
        lambda: _parse_single_day(msg, today),
        lambda: _parse_week(msg, today, week_start),
        # 到X/截至X 截止点（point），必须在 _parse_month 之前以精确识别"到月底"
        lambda: _parse_as_of_point(msg, today),
        lambda: _parse_month(msg, today),
        lambda: _parse_year(msg, today),
        lambda: _parse_exact_date(msg, today),
        lambda: _parse_misc(msg, today),
    ]
    for parser in parsers:
        try:
            result = parser()
            if result is not None:
                if result:
                    if result.start > result.end:
                        return DateRange(
                            original_text=msg, label='起始日期晚于结束日期',
                            range_type='unknown', confidence=0.0,
                            recognition_status='phrase_not_supported',
                        )
                    result.recognition_status = 'ok'
                return result
        except _INPUT_ERRORS:
            # 仅吞掉「输入本身导致」的可预期异常（非法日历日、数字过大等），
            # 换下一个 parser 继续尝试。
            # NameError / AttributeError / TypeError 等编程错误会原样抛出，
            # 不会被伪装成 phrase_not_supported —— 那样会让 bug 静默退化成
            # 「解析不了」，极难排查（本项目拆分模块时就踩过这个坑）。
            continue

    # 所有 parser 都失败
    if has_time_phrase:
        # 有时间词但解析失败
        return DateRange(original_text=msg, label='未识别', range_type='unknown',
                         confidence=0.0, recognition_status='phrase_not_supported')
    else:
        # 没有时间词
        return DateRange(original_text=msg, label='未识别', range_type='unknown',
                         confidence=0.0, recognition_status='no_time_phrase')


# ═════════════════════════════════════════════════════════
#  向后兼容的旧 API
# ═════════════════════════════════════════════════════════

def parse_time_expression(text: str, today: Optional[datetime] = None) -> Optional[Tuple[str, str]]:
    """旧 API：从文本中提取日期。返回 (start, end) 或 None"""
    if today is None:
        today = datetime.now()

    result = extract_date_range_v2(text, today)
    if result and result.start is not None and result.end is not None:
        return result.start, result.end
    return None


def extract_date_range(user_message: str, today: Optional[datetime] = None) -> Tuple[Optional[str], Optional[str]]:
    """旧 API：从用户消息中提取日期范围。返回 (start, end) 或 (None, None)"""
    if today is None:
        today = datetime.now()
    return extract_date_range_v2(user_message, today).to_tuple()
