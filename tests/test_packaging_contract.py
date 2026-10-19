"""发布包的版本与 PEP 561 类型标记契约。"""

import pkgutil

import time_parser_zh


def test_runtime_version_is_1_0() -> None:
    assert time_parser_zh.__version__ == '1.0.0'


def test_py_typed_is_in_package_data() -> None:
    marker = pkgutil.get_data('time_parser_zh', 'py.typed')
    assert marker is not None
