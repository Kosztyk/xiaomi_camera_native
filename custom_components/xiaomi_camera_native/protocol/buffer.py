"""Async media queues with a byte budget in addition to an item limit."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

Item = TypeVar("Item")


class ByteLimitedQueue(asyncio.Queue[Item]):
    """Count payload bytes until a consumer dequeues each item."""

    def __init__(
        self, maxsize: int, max_bytes: int, size_of: Callable[[Item], int]
    ) -> None:
        super().__init__(maxsize)
        self._max_bytes = max_bytes
        self._size_of = size_of
        self._queued_bytes = 0

    def put_nowait(self, item: Item) -> None:
        size = self._size_of(item)
        if self._queued_bytes + size > self._max_bytes:
            raise asyncio.QueueFull
        super().put_nowait(item)
        self._queued_bytes += size

    def get_nowait(self) -> Item:
        item = super().get_nowait()
        self._queued_bytes -= self._size_of(item)
        return item
