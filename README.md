# time-parser-zh

中文自然语言时间表达解析器。将“去年8月”“明天下午3点”“两小时后”“Q2同比”等表达转换为结构化结果，适用于查询条件解析、报表和对话应用。

A pure Python parser for Chinese natural language date and time expressions.

- 纯 Python 标准库实现，运行时无第三方依赖。
- 日期范围、日期时刻、时刻范围、相对偏移、同比与环比使用各自的结构化接口。
- 支持传入基准时刻 `today`，便于复现结果与编写测试。
- Python 3.10+。项目名为 `time-parser-zh`，Python 导入包名为 `zh_time_parser`。

## 安装

在本项目根目录执行（尚未发布到 PyPI）：

```bash
python -m pip install .
```

开发安装：

```bash
python -m pip install -e ".[dev]"
```

## 快速开始

```python
from datetime import datetime
from zh_time_parser import extract_date_range_v2, extract_datetime_point

today = datetime(2026, 10, 19, 15, 30)

result = extract_date_range_v2("去年8月", today=today)
print(result.to_tuple())
# ('2025-08-01', '2025-08-31')

point = extract_datetime_point("明天下午3点", today=today)
print(point.datetime)
# 2026-10-20 15:00:00
```

同比返回当前区间与对比区间：

```python
from datetime import datetime
from zh_time_parser import extract_comparison_range

result = extract_comparison_range("Q2同比", today=datetime(2026, 10, 19))
if result is not None:
    print(result.current.to_tuple())
    # ('2026-04-01', '2026-06-30')
    print(result.comparison.to_tuple())
    # ('2025-04-01', '2025-06-30')
```

## 公开接口

| 接口 | 返回类型 | 用途 |
| --- | --- | --- |
| `extract_date_range_v2` | `DateRange` | 日期范围，如“上个月”“去年8月” |
| `extract_datetime_point` | `DateTimePoint` | 日期与时刻，如“明天下午3点” |
| `extract_datetime_range` | `DateTimeRange` | 含时刻区间与单侧范围 |
| `extract_relative_time` | `RelativeTime` | 相对偏移，如“两小时后” |
| `extract_comparison_range` | `ComparisonRange` 或 `None` | 同比、环比的两个日期区间 |
| `extract_temporal_boundary` | `TemporalBoundary` | 带比较运算符的单侧边界 |
| `extract_temporal_anchor` | `TemporalAnchor` | 结构化时间锚点 |
| `extract_temporal_selector` | `TemporalSelector` | 事件排序、数量与范围选择 |
| `extract_ambiguous_temporal` | `AmbiguousTemporal` | 模糊表达的方向和单位 |
| `extract_date_range` / `parse_time_expression` | 二元 tuple / tuple 或 `None` | 兼容旧版日期接口 |

结构化结果提供 `to_dict()`。日期结果可通过 `to_tuple()` 获取起止日期。自然周默认从周一开始，支持相应接口的 `week_start="sunday"` 配置。

相对表达默认使用本机 `datetime.now()`。需要可重复结果时显式传入 `today`；`extract_relative_time` 对应的参数名为 `anchor`。库不会自动执行时区转换、节假日或农历推算。

## 识别结果与限制

对日期范围应先检查 `bool(result)` 与 `recognition_status`，再使用起止值：

- `ok`：已识别。
- `no_time_phrase`：未发现时间表达。
- `phrase_not_supported`：表达不支持或日期无效。
- `ambiguous`：模糊表达，需要调用方进一步处理。

比较解析不能识别时返回 `None`。日期范围接口不负责表达同比与环比，请使用 `extract_comparison_range`。

当前保留了原库的已知缺陷，例如部分重复季度词、带相对年份的时刻表达、非法钟点校验和部分跨年范围；个别输入可能返回不完整结果或错误状态。代表性问题以 `strict xfail` 记录正确预期，本次整理没有修改解析规则。不要将本库视为完整的任意中文时间理解系统。

## 开发和验证

```bash
python -m pytest
python examples/basic_usage.py
python -m build
python -m twine check dist/*
```

GitHub Actions 配置了 Linux / Windows 与 Python 3.10–3.13 的测试、构建、分发元数据检查和 wheel 安装验证。流水线不会发布包。

```text
src/zh_time_parser/     解析器和数据模型
tests/                 上游测试与本项目回归测试
examples/              可运行的固定日期示例
.github/workflows/     持续集成配置
pyproject.toml         安装、依赖、版本和测试配置
```

## 致谢

感谢 [BZHDZNJJ/zh-time-parser](https://github.com/BZHDZNJJ/zh-time-parser) 的开源贡献。

