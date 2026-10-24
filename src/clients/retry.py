"""Retry with exponential backoff for transport errors and timeouts."""

import time
from collections.abc import Callable
from typing import TypeVar

from src.clients.base import TransportError

T = TypeVar("T")


def call_with_retry(
    fn: Callable[[], T],
    max_attempts: int,
    retry_on: tuple[type[BaseException], ...],
    base_delay_s: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    for attempt in range(max_attempts):
        try:
            return fn()
        except retry_on as e:
            if attempt == max_attempts - 1:
                raise TransportError(e, max_attempts) from e
            sleep(base_delay_s * 2**attempt)
    raise AssertionError("unreachable")
