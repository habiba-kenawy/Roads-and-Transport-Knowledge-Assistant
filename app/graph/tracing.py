"""Node tracing: one log line when a node starts and one when it ends, with timing and candidate counts (8.3)."""
import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("graph")


def summary(result: Any) -> str:
    """Describe a node's output by sizes only (never document text)."""
    if not isinstance(result, dict):
        return ""
    return " ".join(f"{k}={len(v)}" for k, v in result.items() if isinstance(v, list))


def traced(name: str) -> Callable:
    """Decorator: log node start/end with the search mode and elapsed seconds."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(state: dict, **deps: Any) -> Any:
            started = time.perf_counter()
            logger.info("node=%s event=start mode=%s", name, state.get("search_mode"))
            result = fn(state, **deps)
            logger.info("node=%s event=end seconds=%.3f %s", name, time.perf_counter() - started, summary(result))
            return result

        return wrapper

    return decorator
