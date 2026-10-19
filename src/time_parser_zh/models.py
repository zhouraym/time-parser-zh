"""DateRange / DateTimePoint / RelativeTime / ComparisonRange 数据类与时间常量。"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

# ─────────────────────────────────────────────────────────
#  时间常量（统一口径，避免魔法数字）
# ─────────────────────────────────────────────────────────
YEAR_DAYS = 365
HALF_YEAR_DAYS = 183


# ═════════════════════════════════════════════════════════
#  DateTimePoint 数据类（日期 + 时刻）
# ═════════════════════════════════════════════════════════

@dataclass
class DateTimePoint:
    """一个确定的日期时刻，与只表达日期区间的 :class:`DateRange` 分离。"""

    datetime: Optional[str] = None       # 'YYYY-MM-DD HH:MM:SS'
    original_text: str = ''
    label: str = ''
    is_relative: bool = False
    precision: str = 'minute'            # 'minute' / 'second' / 'period'
    confidence: float = 1.0
    recognition_status: str = 'ok'       # 'ok' / 'no_time_phrase' / 'phrase_not_supported'

    def __bool__(self):
        return self.datetime is not None

    def __repr__(self):
        if not self:
            return 'DateTimePoint(empty)'
        return f'DateTimePoint(datetime="{self.datetime}")'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  RelativeTime 数据类（锚点 + 时长）
# ═════════════════════════════════════════════════════════

@dataclass
class RelativeTime:
    """相对于一个时间锚点的偏移量及其解析结果。"""

    value: Optional[int] = None
    unit: Optional[str] = None           # 'minute' / 'hour' / 'day' / 'week' / 'month'
    direction: Optional[str] = None      # 'future' / 'past'
    resolved_at: Optional[str] = None    # 'YYYY-MM-DD HH:MM'
    original_text: str = ''
    confidence: float = 1.0
    recognition_status: str = 'ok'       # 'ok' / 'no_time_phrase' / 'phrase_not_supported'

    def __bool__(self):
        return self.resolved_at is not None

    def __repr__(self):
        if not self:
            return 'RelativeTime(empty)'
        return (
            f'RelativeTime(value={self.value}, unit="{self.unit}", '
            f'direction="{self.direction}", resolved_at="{self.resolved_at}")'
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  TemporalBoundary 数据类（单侧比较边界）
# ═════════════════════════════════════════════════════════

@dataclass
class TemporalBoundary:
    """日期或时刻的单侧边界，适合直接映射为查询比较运算符。"""

    operator: Optional[str] = None       # '<' / '<=' / '>' / '>='
    value: Optional[str] = None          # YYYY-MM-DD 或 YYYY-MM-DD HH:MM
    value_type: Optional[str] = None     # 'date' / 'datetime'
    duration: Optional[RelativeTime] = None
    original_text: str = ''
    matched_text: str = ''
    is_relative: bool = False
    confidence: float = 1.0
    recognition_status: str = 'ok'

    def __post_init__(self):
        if self.operator is not None and self.operator not in ('<', '<=', '>', '>='):
            raise ValueError("operator 必须是 '<'、'<='、'>' 或 '>='")
        if self.value_type is not None and self.value_type not in ('date', 'datetime'):
            raise ValueError("value_type 必须是 'date' 或 'datetime'")

    def __bool__(self):
        return self.operator is not None and self.value is not None

    def __repr__(self):
        if not self:
            return 'TemporalBoundary(empty)'
        return f'TemporalBoundary(operator="{self.operator}", value="{self.value}")'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  TemporalAnchor 数据类（站在某个时点评估）
# ═════════════════════════════════════════════════════════

@dataclass
class TemporalAnchor:
    """评估时钟锚点；与用于筛选记录的 TemporalBoundary 分离。"""

    mode: Optional[str] = None           # 当前为 'as_of'
    value: Optional[str] = None          # YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS
    value_type: Optional[str] = None     # 'date' / 'datetime'
    original_text: str = ''
    matched_text: str = ''
    is_relative: bool = False
    is_future: bool = False
    confidence: float = 1.0
    recognition_status: str = 'ok'

    def __post_init__(self):
        if self.mode is not None and self.mode != 'as_of':
            raise ValueError("mode 当前只支持 'as_of'")
        if self.value_type is not None and self.value_type not in ('date', 'datetime'):
            raise ValueError("value_type 必须是 'date' 或 'datetime'")

    def __bool__(self):
        return self.mode == 'as_of' and self.value is not None

    def __repr__(self):
        if not self:
            return 'TemporalAnchor(empty)'
        return f'TemporalAnchor(mode="{self.mode}", value="{self.value}")'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  DateTimeRange 数据类（可带时刻的区间 / 单边界）
# ═════════════════════════════════════════════════════════

@dataclass
class DateTimeRange:
    """带时刻的区间；允许只提供 start 或 end 来表达单侧边界。"""

    start: Optional[str] = None          # 'YYYY-MM-DD HH:MM:SS'
    end: Optional[str] = None            # 'YYYY-MM-DD HH:MM:SS'
    date_start: Optional[str] = None     # 给日期型旧系统的日历日期投影
    date_end: Optional[str] = None
    precision_lost: bool = False         # 投影到 date_start/date_end 是否丢失时刻语义
    original_text: str = ''
    is_relative: bool = False
    includes_end: bool = True
    confidence: float = 1.0
    recognition_status: str = 'ok'

    def __bool__(self):
        return self.start is not None or self.end is not None

    def __repr__(self):
        if not self:
            return 'DateTimeRange(empty)'
        return f'DateTimeRange(start={self.start!r}, end={self.end!r})'

    def to_date_tuple(self, policy: str = 'calendar_date') -> Tuple[Optional[str], Optional[str]]:
        """投影给只接受日期的旧系统。

        policy:
        - calendar_date: 直接取边界所在日期；可能扩大或缩小实际查询范围。
        - completed_days: 只保留完全落在精确区间内的自然日。
        - reject_lossy: 只要投影会丢精度就抛 ValueError。
        """
        if policy not in ('calendar_date', 'completed_days', 'reject_lossy'):
            raise ValueError("policy 必须是 'calendar_date'、'completed_days' 或 'reject_lossy'")
        if policy == 'reject_lossy' and self.precision_lost:
            raise ValueError('该 DateTimeRange 含时刻边界，无法无损投影为日期范围')
        if policy != 'completed_days':
            return self.date_start, self.date_end

        start_date = self.date_start
        end_date = self.date_end
        if self.start:
            parsed_start = datetime.strptime(self.start, '%Y-%m-%d %H:%M:%S')
            if parsed_start.time() != datetime.min.time():
                start_date = (parsed_start + timedelta(days=1)).strftime('%Y-%m-%d')
        if self.end:
            parsed_end = datetime.strptime(self.end, '%Y-%m-%d %H:%M:%S')
            if parsed_end.time() != datetime.max.replace(microsecond=0).time():
                end_date = (parsed_end - timedelta(days=1)).strftime('%Y-%m-%d')
        return start_date, end_date

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  DateRange 数据类（v2 专属）
# ═════════════════════════════════════════════════════════

@dataclass
class DateRange:
    """
    结构化日期范围。
    支持 tuple 解包（向后兼容旧 API）和属性访问（新 API）。
    """
    start: Optional[str] = None          # 'YYYY-MM-DD'
    end: Optional[str] = None            # 'YYYY-MM-DD'
    # range_type: 'range' / 'point' / 'quarter' / 'ytd' / 'unknown'
    #   另有历史取值 'yoy' / 'mom'：同比/环比现由 ComparisonRange 表达，
    #   这两个取值保留仅为向后兼容，不要在新代码中依赖。
    range_type: str = 'range'
    # granularity: 'day' / 'week' / 'month' / 'quarter' / 'half_year' / 'year'
    granularity: str = 'day'
    original_text: str = ''              # 原始匹配片段
    label: str = ''                      # 给人看的标签："最近7天" / "上个月" / "Q1 2026"
    is_relative: bool = False            # 是否相对今天（每次调用可能不同）
    includes_end: bool = True            # 端点是否包含（用于 SQL BETWEEN）
    week_start: str = 'monday'           # 'monday' / 'sunday'
    confidence: float = 1.0              # 解析置信度 0~1，调用方可用于降级
    recognition_status: str = 'ok'       # 'ok' / 'no_time_phrase' / 'phrase_not_supported' / 'ambiguous'
    # ── 截止点语义（用于"到X/截至X"的确定截止边界，不影响原有 start/end/range_type）──
    # point: 单点日期（YYYY-MM-DD）。表达指向明确截止日（如"到月底""到8月31日""截至今天"）时填充。
    #        调用方可用它作为"截至某日"的时点基准，而 start/end 仍保留完整区间。
    point: Optional[str] = None
    # boundary: 被强调的边界方向。"end"=表达强调结束边界（到/截至/截止/月底/年末）；None=未强调。
    boundary: Optional[str] = None

    def __iter__(self):
        """支持 tuple 解包：start, end = extract_date_range_v2(msg)"""
        return iter((self.start, self.end))

    def __getitem__(self, i):
        return (self.start, self.end)[i]

    def __eq__(self, other):
        if isinstance(other, tuple):
            return (self.start, self.end) == other
        if isinstance(other, DateRange):
            return (self.start, self.end) == (other.start, other.end)
        return NotImplemented

    def __bool__(self):
        return self.start is not None and self.end is not None

    def __repr__(self):
        if not self:
            return "DateRange(empty)"
        if self.range_type == 'point':
            return f"DateRange(point={self.start} [{self.label}])"
        return f"DateRange({self.start} ~ {self.end} [{self.label}, type={self.range_type}])"

    def to_tuple(self) -> Tuple[Optional[str], Optional[str]]:
        return (self.start, self.end)

    def to_dict(self) -> Dict[str, Any]:
        """
        转成普通 dict（便于 JSON 序列化 / 日志输出）。

        返回全部字段，键名与属性名一致；使用 dataclasses.asdict，
        新增字段会自动出现在结果中，无需同步维护。
        """
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  TemporalSelector 数据类（按事件顺序选择若干次）
# ═════════════════════════════════════════════════════════

@dataclass
class TemporalSelector:
    """不猜测事件日期，只描述排序、数量、偏移和可选日期范围。"""

    order: Optional[str] = None          # 'latest' / 'earliest'
    limit: Optional[int] = None
    offset: int = 0                      # 倒数第二次 = latest + limit 1 + offset 1
    date_range: Optional[DateRange] = None
    original_text: str = ''
    selector_text: str = ''
    confidence: float = 1.0
    recognition_status: str = 'ok'

    def __post_init__(self):
        if self.order is not None and self.order not in ('latest', 'earliest'):
            raise ValueError("order 必须是 'latest' 或 'earliest'")
        if self.limit is not None and self.limit <= 0:
            raise ValueError('limit 必须大于 0')
        if self.offset < 0:
            raise ValueError('offset 不能小于 0')

    def __bool__(self):
        return self.order is not None and self.limit is not None

    def __repr__(self):
        if not self:
            return 'TemporalSelector(empty)'
        return (
            f'TemporalSelector(order="{self.order}", limit={self.limit}, '
            f'offset={self.offset}, date_range={self.date_range!r})'
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  AmbiguousTemporal 数据类（识别语义，但不猜具体值）
# ═════════════════════════════════════════════════════════

@dataclass
class AmbiguousTemporal:
    """需要上层追问或应用自身策略才能解析的模糊时间表达。"""

    type: Optional[str] = None           # 'date_range' / 'relative_time' / 'datetime_point'
    status: str = 'no_time_phrase'       # 'ambiguous' / 'no_time_phrase'
    direction: Optional[str] = None      # 'recent' / 'past' / 'future' / 'around'
    unit: Optional[str] = None           # 'day' / 'month' / None
    value: Optional[int] = None          # 模糊表达始终为 None，不代替用户猜数值
    original_text: str = ''
    matched_text: str = ''
    confidence: float = 1.0

    def __bool__(self):
        return self.status == 'ambiguous' and self.type is not None

    def __repr__(self):
        if not self:
            return 'AmbiguousTemporal(empty)'
        return (
            f'AmbiguousTemporal(type="{self.type}", status="{self.status}", '
            f'direction="{self.direction}", unit={self.unit!r}, value=None)'
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ═════════════════════════════════════════════════════════
#  ComparisonRange 数据类（同比 / 环比）
# ═════════════════════════════════════════════════════════

# comparison_type 合法取值
COMPARISON_YOY = 'yoy'                          # 同比：与上一年度相同日历位置比较
COMPARISON_PREVIOUS_PERIOD = 'previous_period'  # 环比：与紧邻的同粒度前一周期比较
_VALID_COMPARISON_TYPES = (COMPARISON_YOY, COMPARISON_PREVIOUS_PERIOD)


@dataclass
class ComparisonRange:
    """
    比较区间：同时表达「本期」与「对比期」两个区间。

    刻意与 DateRange 分开，而不是把两个区间塞进一个 DateRange：
    - DateRange 只表达**一个**区间，其 point/boundary 字段有各自的语义，
      不能挪用来存放对比期；
    - extract_date_range_v2() 的返回类型因此保持恒定为 DateRange，
      调用方不需要做类型判断。

    字段：
        current         本期区间（必须是有效 DateRange）
        comparison      对比期区间（必须是有效 DateRange）
        comparison_type 'yoy'（同比）或 'previous_period'（环比）
        original_text   原始匹配片段
        label           给人看的标签，如 "2026Q2 同比 2025Q2"
        confidence      解析置信度 0~1
    """
    current: DateRange
    comparison: DateRange
    comparison_type: str
    original_text: str = ''
    label: str = ''
    confidence: float = 1.0

    def __post_init__(self):
        """构造即校验：两个区间必须有效，比较类型必须合法。"""
        if not isinstance(self.current, DateRange) or not self.current:
            raise ValueError(
                f'ComparisonRange.current 必须是有效 DateRange（start/end 均非 None），'
                f'实际得到：{self.current!r}'
            )
        if not isinstance(self.comparison, DateRange) or not self.comparison:
            raise ValueError(
                f'ComparisonRange.comparison 必须是有效 DateRange（start/end 均非 None），'
                f'实际得到：{self.comparison!r}'
            )
        if self.comparison_type not in _VALID_COMPARISON_TYPES:
            raise ValueError(
                f'comparison_type 必须是 {_VALID_COMPARISON_TYPES} 之一，'
                f'实际得到：{self.comparison_type!r}'
            )

    def __repr__(self):
        kind = '同比' if self.comparison_type == COMPARISON_YOY else '环比'
        return (f'ComparisonRange[{kind}]('
                f'current={self.current.start}~{self.current.end}, '
                f'comparison={self.comparison.start}~{self.comparison.end})')

    def to_dict(self) -> Dict[str, Any]:
        """
        转成可直接 JSON 序列化的 dict（嵌套的 DateRange 也会展开为 dict）。
        """
        return asdict(self)
