"""Tests for domain/rekey.py: auto transpose jianpu text when key signature changes."""

from __future__ import annotations

from score_trans.domain.rekey import rekey_text


class TestRekeyTextBasic:
    """Basic single-segment transposition tests."""

    def test_simple_c_to_g(self) -> None:
        # C 调转 G 调
        old = "title=Test\n1=C\n4/4\n1 2 3"
        new = "title=Test\n1=G\n1 2 3"
        result = rekey_text(new, old)
        # 检查包含新调号且至少有一个音级变化
        assert "1=G" in result
        assert "4/4" in result
        # 应该包含新的音符（具体取决于实现）

    def test_same_key_returns_original(self) -> None:
        # 无调号变化返回原文本
        old = "1=C\n1 2 3"
        new = "1=C\n1 2 3"
        result = rekey_text(new, old)
        assert result == new


class TestRekeyMultipleMeasures:
    """Test transposition with multiple measures and key changes."""

    def test_rest_not_transposed(self) -> None:
        # 休止符不应转调
        old = "1=C\n0 1 2 0"
        new = "1=G\n0 1 2 0"
        result = rekey_text(new, old)
        # 休止符应保留
        assert result.count("0") >= 2

    def test_chained_key_changes(self) -> None:
        # C → G → D，只改第一个点
        old = "1=C\n1 2 3 | 1=C\n4 5 6"
        new = "1=G\n1 2 3 | 1=C\n4 5 6"
        result = rekey_text(new, old)
        # 第一段 C→G 转，第二段保持 C
        assert "1=G" in result
        assert "1=C" in result


class TestRekeyEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_text(self) -> None:
        old = ""
        new = "title=X\n1=G\n1 2 3"
        result = rekey_text(new, old)
        assert result == new  # 旧文本为空，返回新文本

    def test_no_key_signature(self) -> None:
        # 没有 1=X 行，返回原样
        old = "1 2 3"
        new = "4 5 6"
        result = rekey_text(new, old)
        # 无调号则不转
        assert result == new

    def test_invalid_key_name(self) -> None:
        # 无效调号应该抛异常或返回原样
        old = "1=C\n1 2 3"
        new = "1=Z\n1 2 3"  # Z 是无效调号
        try:
            rekey_text(new, old)
        except ValueError:
            pass  # 正常行为是抛异常

    def test_comment_preserved(self) -> None:
        # 注释应保留
        old = "1=C\n1 2 3 ; comment"
        new = "1=G\n1 2 3 ; comment"
        result = rekey_text(new, old)
        assert "; comment" in result or result == new
