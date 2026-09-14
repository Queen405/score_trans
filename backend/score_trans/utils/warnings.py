from __future__ import annotations

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_LOGGER = logging.getLogger("score_trans")
_ACTIVE: ContextVar[list[str] | None] = ContextVar(
    "score_trans_warning_collector", default=None
)
_install_lock = threading.Lock()
_handler_installed = False


class _WarningCollectorHandler(logging.Handler):
    """捕获 ``score_trans`` logger 树下的 WARNING+ 记录到当前上下文收集器。

    仅当上下文内存在活跃收集器时才记录，避免对全局日志造成额外开销。
    """

    def emit(self, record: logging.LogRecord) -> None:
        collector = _ACTIVE.get()
        if collector is None:
            return
        try:
            message = record.getMessage()
        except Exception:
            message = record.msg if isinstance(record.msg, str) else str(record.msg)
        if message and message not in collector:
            collector.append(message)


def _ensure_handler_installed() -> None:
    global _handler_installed
    if _handler_installed:
        return
    with _install_lock:
        if _handler_installed:
            return
        _LOGGER.addHandler(_WarningCollectorHandler(level=logging.WARNING))
        _handler_installed = True


@contextmanager
def collect_warnings() -> Iterator[list[str]]:
    """捕获上下文作用域内 ``score_trans`` 的 WARNING+ 日志消息。

    幂等安装一次 handler；``asyncio.to_thread`` 会复制当前 contextvars，
    故在后台任务线程内同样可捕获。嵌套时内层收集器独立于外层。
    """
    _ensure_handler_installed()
    collected: list[str] = []
    token = _ACTIVE.set(collected)
    try:
        yield collected
    finally:
        _ACTIVE.reset(token)


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
