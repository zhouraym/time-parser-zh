"""
异常处理边界测试。

主入口 extract_date_range_v2 会依次尝试多个 parser，并跳过失败的那个。
这里锁定「跳过哪些异常」的契约：

  - 输入导致的可预期异常（ValueError / OverflowError / KeyError / IndexError）
    → 吞掉，继续尝试下一个 parser，最终降级为 phrase_not_supported。
  - 编程错误（NameError / AttributeError / TypeError）
    → 必须原样抛出，绝不能被伪装成 phrase_not_supported。

第二条是回归防线：本项目拆分模块时曾因跨模块导入缺失产生 NameError，
被宽泛的 except Exception 吞掉后退化成「解析不了」，排查代价很高。
"""

from datetime import datetime

import pytest

import time_parser_zh.date_parser as dp
from time_parser_zh import extract_date_range_v2

FIXED_TODAY = datetime(2026, 5, 24)


def _boom(exc):
    """构造一个必定抛出指定异常的假 parser"""
    def _raise(*args, **kwargs):
        raise exc
    return _raise


class TestProgrammingErrorsPropagate:
    """编程错误必须暴露，不能被静默吞掉"""

    @pytest.mark.parametrize('exc_type', [NameError, AttributeError, TypeError])
    def test_programming_errors_are_raised(self, exc_type, monkeypatch):
        """NameError / AttributeError / TypeError 必须原样抛出"""
        monkeypatch.setattr(dp, '_parse_explicit_date_range',
                            _boom(exc_type('injected by test')))
        with pytest.raises(exc_type):
            extract_date_range_v2('最近7天', today=FIXED_TODAY)

    @pytest.mark.parametrize('exc_type', [NameError, AttributeError, TypeError])
    def test_not_disguised_as_phrase_not_supported(self, exc_type, monkeypatch):
        """核心回归点：编程错误不得退化成 recognition_status='phrase_not_supported'"""
        monkeypatch.setattr(dp, '_parse_explicit_date_range',
                            _boom(exc_type('injected by test')))
        try:
            result = extract_date_range_v2('最近7天', today=FIXED_TODAY)
        except exc_type:
            return  # 正确行为：异常冒泡
        pytest.fail(
            f'编程错误被吞掉了，退化为 recognition_status={result.recognition_status!r}。'
            f'这会让真实 bug 伪装成「解析不了」。'
        )

    def test_name_error_from_missing_cross_module_import(self, monkeypatch):
        """模拟拆分模块时漏掉跨模块导入的真实场景"""
        def _uses_undefined_name(*args, **kwargs):
            return _definitely_not_defined(args)  # noqa: F821 - 故意的
        monkeypatch.setattr(dp, '_parse_month', _uses_undefined_name)
        with pytest.raises(NameError):
            extract_date_range_v2('上个月', today=FIXED_TODAY)


class TestInputErrorsAreSwallowed:
    """输入导致的异常应被跳过，让后续 parser 继续"""

    @pytest.mark.parametrize('exc_type', [ValueError, OverflowError, KeyError, IndexError])
    def test_input_errors_do_not_crash(self, exc_type, monkeypatch):
        """某个 parser 因畸形输入失败，不应影响整体解析"""
        monkeypatch.setattr(dp, '_parse_explicit_date_range',
                            _boom(exc_type('injected by test')))
        # 后面的 parser 仍能正确识别"最近7天"
        r = extract_date_range_v2('最近7天', today=FIXED_TODAY)
        assert r.start == '2026-05-18'
        assert r.end == '2026-05-24'
        assert r.recognition_status == 'ok'

    @pytest.mark.parametrize('exc_type', [ValueError, OverflowError, KeyError, IndexError])
    def test_all_parsers_failing_degrades_gracefully(
        self, exc_type: type[Exception], monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """调度链所有规则抛输入类异常时降级为未识别。

        Args:
            exc_type: 要注入的输入错误类型。
            monkeypatch: pytest 属性替换工具。

        Returns:
            None。

        Raises:
            AssertionError: 调度链错误被泄漏或识别状态不正确。
        """
        # 日历组合属于调度前置处理，内部自行处理输入错误；本例只验证调度链。
        for name in [n for n in vars(dp) if n.startswith('_parse_') and n != '_parse_calendar_expression']:
            monkeypatch.setattr(dp, name, _boom(exc_type('injected by test')))
        r = extract_date_range_v2('最近7天', today=FIXED_TODAY)
        assert r.start is None
        assert r.recognition_status == 'phrase_not_supported'


class TestMalformedInputRealCases:
    """真实畸形输入：不抛异常，安全降级"""

    @pytest.mark.parametrize('text', [
        '最近99999999999999999999天',   # 超大数字 → OverflowError
        '2026年2月30日',                 # 不存在的日历日
        '2026-13-45',
        '99999年',
        '第99季度',
        '!@#$%^&*()',
        '   ',
    ])
    def test_no_exception_leaks(self, text):
        r = extract_date_range_v2(text, today=FIXED_TODAY)
        assert r.recognition_status in ('ok', 'phrase_not_supported', 'no_time_phrase')

    def test_huge_number_specifically(self):
        """OverflowError 路径：确实被吞掉并降级"""
        r = extract_date_range_v2('最近99999999999999999999天', today=FIXED_TODAY)
        assert r.recognition_status == 'phrase_not_supported'
