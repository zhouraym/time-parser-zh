"""使用固定基准日期演示独立安装后的公开接口。"""

from datetime import datetime
from pprint import pprint

from zh_time_parser import (
    extract_comparison_range,
    extract_date_range_v2,
    extract_datetime_point,
    extract_relative_time,
)


def main() -> None:
    """运行日期、时刻、相对偏移与同比解析示例。

    Args:
        无。

    Returns:
        None。

    Raises:
        RuntimeError: 固定示例未能解析出同比区间。
    """
    today = datetime(2026, 10, 19, 15, 30)
    pprint(extract_date_range_v2("去年8月", today=today).to_dict())
    pprint(extract_datetime_point("明天下午3点", today=today).to_dict())
    pprint(extract_relative_time("两小时后", anchor=today).to_dict())
    comparison = extract_comparison_range("Q2同比", today=today)
    if comparison is None:
        raise RuntimeError("固定示例未能解析出同比区间")
    pprint(comparison.to_dict())


if __name__ == "__main__":
    main()
