"""Small in-process rate limiter for the single-node reference implementation."""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config
from .auth import request_identity

_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def enforce(scope: str, request: Request) -> None:
    key = (scope, request_identity(request))
    now = time.monotonic()
    cutoff = now - config.RATE_LIMIT_WINDOW_SECONDS
    with _lock:
        bucket = _events[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= config.RATE_LIMIT_REQUESTS:
            raise HTTPException(429, "Too many requests, please try again later")
        bucket.append(now)
