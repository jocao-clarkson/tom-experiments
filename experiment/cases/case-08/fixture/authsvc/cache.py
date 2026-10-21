import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Hashable


class TTLMemo:
    """Small in-process LRU memo; each entry expires ttl seconds after it was loaded."""

    def __init__(self, ttl: float, maxsize: int = 1024, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl
        self._maxsize = maxsize
        self._clock = clock
        self._data: OrderedDict[Hashable, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_load(self, key: Hashable, loader: Callable[[], Any]) -> Any:
        now = self._clock()
        with self._lock:
            entry = self._data.get(key)
            if entry is not None and entry[1] > now:
                self._data.move_to_end(key)
                return entry[0]
        value = loader()
        with self._lock:
            self._data[key] = (value, now + self._ttl)
            self._data.move_to_end(key)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)
        return value

    def evict(self, key: Hashable) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
