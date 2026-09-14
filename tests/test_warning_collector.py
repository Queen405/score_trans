from __future__ import annotations

import asyncio
import logging

from score_trans.utils.warnings import (
    collect_warnings,
    dedupe_preserve_order,
)

_CHILD_LOGGER = logging.getLogger("score_trans.domain.write.jianpu_text")
_SIBLING_LOGGER = logging.getLogger("score_trans.services.correct.correction_service")


def test_collect_warnings_captures_child_logger_output() -> None:
    with collect_warnings() as captured:
        _CHILD_LOGGER.warning("小节 %s 的休止时值 %s 超出剩余容量", 3, 1)
        _SIBLING_LOGGER.warning("声部「Piano」包含 2 个 voice")

    assert captured == [
        "小节 3 的休止时值 1 超出剩余容量",
        "声部「Piano」包含 2 个 voice",
    ]


def test_collect_warnings_silent_outside_context() -> None:
    with collect_warnings() as captured:
        _CHILD_LOGGER.warning("inside %s", 1)

    # context 外的日志不应进入之前的收集器
    _CHILD_LOGGER.warning("outside")
    assert captured == ["inside 1"]


def test_collect_warnings_deduplicates_within_context() -> None:
    with collect_warnings() as captured:
        for _ in range(3):
            _CHILD_LOGGER.warning("重复消息")
        _CHILD_LOGGER.warning("唯一消息")

    assert captured == ["重复消息", "唯一消息"]


def test_collect_warnings_propagates_to_to_thread() -> None:
    async def runner() -> list[str]:
        with collect_warnings() as captured:
            await asyncio.to_thread(_CHILD_LOGGER.warning, "来自线程 %s", "x")
        return captured

    captured = asyncio.run(runner())
    assert captured == ["来自线程 x"]


def test_collect_warnings_nested_contexts_are_independent() -> None:
    with collect_warnings() as outer:
        _CHILD_LOGGER.warning("outer-1")
        with collect_warnings() as inner:
            _CHILD_LOGGER.warning("inner-1")
            _CHILD_LOGGER.warning("inner-2")
        _CHILD_LOGGER.warning("outer-2")

    assert inner == ["inner-1", "inner-2"]
    assert outer == ["outer-1", "outer-2"]


def test_collect_warnings_ignores_info_level() -> None:
    with collect_warnings() as captured:
        _CHILD_LOGGER.info("info 消息")
        _CHILD_LOGGER.warning("warn 消息")

    assert captured == ["warn 消息"]


def test_dedupe_preserve_order() -> None:
    assert dedupe_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert dedupe_preserve_order([]) == []
