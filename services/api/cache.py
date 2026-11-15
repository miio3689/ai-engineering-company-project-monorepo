"""Thread-safe in-process TTL cache.

Each worker process owns a separate cache, so multiple workers do not share
entries. Writes made outside the API are reflected only after the TTL expires.
"""

from collections.abc import Callable
import logging
from threading import Lock
import time
from typing import TypeVar

logger = logging.getLogger("api.cache")
T = TypeVar("T")


class InProcessTTLCache:
    def __init__(self, clock: Callable[[], float] | None = None):
        self._clock = clock or time.monotonic
        self._lock = Lock()
        self._entries: dict[str, tuple[float, object]] = {}
        self._generations: dict[str, int] = {}

    def get_or_set(
        self,
        key: str,
        ttl_seconds: float,
        loader: Callable[[], T],
    ) -> T:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than zero")

        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None and entry[0] > now:
                logger.debug("cache hit: %s", key)
                return entry[1]  # type: ignore[return-value]

            if entry is not None:
                del self._entries[key]
            generation = self._generations.setdefault(key, 0)
            logger.debug("cache miss: %s", key)

        value = loader()

        with self._lock:
            if self._generations.get(key) == generation:
                self._entries[key] = (self._clock() + ttl_seconds, value)
        return value

    def invalidate(self, key: str, *, is_prefix: bool = False) -> None:
        with self._lock:
            keys = (
                {
                    cached_key
                    for cached_key in self._generations
                    if cached_key.startswith(key)
                }
                if is_prefix
                else {key}
            )
            for cached_key in keys:
                self._generations[cached_key] = (
                    self._generations.get(cached_key, 0) + 1
                )
                self._entries.pop(cached_key, None)

    def clear(self) -> None:
        with self._lock:
            for key in self._generations:
                self._generations[key] += 1
            self._entries.clear()
