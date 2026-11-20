"""Node tracing: one log line when a node starts and one when it ends, with timing and candidate counts (8.3)."""
import contextvars
import functools
import logging
import time
from typing import Any, Callable

logger = logging.getLogger("graph")

# set by the chat service for each request, so every node log line can carry request_id and thread_id
request_context: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar("request_context", default={})


def ids() -> str:
    """Return the current request and thread ids for log lines ('-' when not inside a chat request)."""
    ctx = request_context.get()
    return f"request_id={ctx.get('request_id', '-')} thread_id={ctx.get('thread_id', '-')}"


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
            logger.info("node=%s event=start mode=%s %s", name, state.get("search_mode"), ids())
            result = fn(state, **deps)
            logger.info("node=%s event=end seconds=%.3f %s %s", name, time.perf_counter() - started, summary(result), ids())
            return result

        return wrapper

    return decorator
