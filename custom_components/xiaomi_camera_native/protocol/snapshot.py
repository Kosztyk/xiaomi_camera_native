"""Bounded FFmpeg snapshot capture with one owner for subprocess output."""

from __future__ import annotations

import asyncio
from contextlib import suppress

SNAPSHOT_TIMEOUT = 8.0
SNAPSHOT_CACHE_SECONDS = 10.0
SNAPSHOT_RETRY_SECONDS = 2.0
MAX_SNAPSHOT_DIMENSION = 4096
MAX_SNAPSHOT_PIXELS = 4096 * 2160


def snapshot_size_allowed(width: int | None, height: int | None) -> bool:
    """Validate caller requests, treating zero and None as unspecified."""
    return all(
        dimension is None
        or (type(dimension) is int and 0 <= dimension <= MAX_SNAPSHOT_DIMENSION)
        for dimension in (width, height)
    ) and (width or 0) * (height or 0) <= MAX_SNAPSHOT_PIXELS


def complete_jpeg(image: bytes | None) -> bool:
    """Reject empty or truncated output before passing it to HA/HomeKit."""
    return (
        isinstance(image, bytes) and image.startswith(b"\xff\xd8") and image.endswith(b"\xff\xd9")
    )


async def async_get_snapshot(
    ffmpeg: str,
    source: str,
    *,
    width: int | None = None,
    height: int | None = None,
    fast: bool = True,
    timeout: float = SNAPSHOT_TIMEOUT,
) -> bytes | None:
    """Read once, then kill/reap the same process on timeout or cancellation.

    Do not use ha-ffmpeg ImageFrame's timeout cleanup here: its kill() and
    close(0) can each start a new communicate() reader for the same pipe.
    """
    if not snapshot_size_allowed(width, height):
        return None
    inputs = ["-f", "mpegts", "-probesize", "65536", "-analyzeduration", "500000"] if fast else []
    size = ["-s", f"{width}x{height}"] if width and height else []
    process = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        *inputs,
        "-i",
        source,
        "-an",
        "-frames:v",
        "1",
        "-c:v",
        "mjpeg",
        *size,
        "-f",
        "image2pipe",
        "pipe:1",
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    # Shield this one reader so timeout/cancellation can kill the producer and
    # finish draining it without starting a competing read of stdout.
    reader = asyncio.create_task(process.communicate())
    try:
        async with asyncio.timeout(timeout):
            image, _ = await asyncio.shield(reader)
        return image if process.returncode == 0 and complete_jpeg(image) else None
    finally:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()

        async def reap() -> None:
            await asyncio.gather(reader, return_exceptions=True)
            await process.wait()

        cleanup = asyncio.create_task(reap())
        cancelled = False
        while True:
            try:
                await asyncio.shield(cleanup)
                break
            except asyncio.CancelledError:
                # A second cancellation (for example reload during a timed-out
                # request) must not abandon the child process or its reader.
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError
