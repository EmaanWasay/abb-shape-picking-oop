"""Thread-safe storage of the newest result, shared between threads."""
from __future__ import annotations

import threading

from .models import FrameResult


class ResultStore:
    """Holds the newest FrameResult.

    Written by the coordinate thread, read by the GUI and the controller.
    A FrameResult is replaced as a whole and never changed afterwards, so
    readers always see a complete, consistent result.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._latest = FrameResult()

    def update(self, result: FrameResult) -> None:
        with self._lock:
            self._latest = result

    def latest(self) -> FrameResult:
        with self._lock:
            return self._latest
