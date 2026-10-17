"""On-demand shared camera sessions and an in-process loopback TS endpoint."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any

from aiohttp import web

from .cloud import CameraDevice, XiaomiCloud
from .errors import AuthenticationError, ProtocolError, TransportError, XiaomiError
from .media import MpegTsMuxer
from .miss import PAN_TILT_MODELS, PAN_TILT_OPERATIONS, MissClient

_LOGGER = logging.getLogger(__name__)
QUEUE_SIZE = 256
MAX_CACHE = 4 * 1024 * 1024
PAN_TILT_SETTLE_TIME = 0.4
PAN_TILT_TIMEOUT = 40


@dataclass(frozen=True)
class StreamOptions:
    host: str = ""
    transport: str = "auto"
    quality: str = "hd"
    video_mode: str = "h264"
    height: int = 720
    idle_timeout: int = 30


class CameraSession:
    """One MISS connection and, optionally, one shared encoder per camera."""

    def __init__(
        self,
        cloud: XiaomiCloud,
        device: CameraDevice,
        options: StreamOptions,
        ffmpeg: str = "ffmpeg",
        on_state: Callable[[], None] | None = None,
        on_auth_error: Callable[[], None] | None = None,
    ) -> None:
        self.cloud = cloud
        self.device = device
        self.options = options
        self.ffmpeg = ffmpeg
        self.on_state = on_state or (lambda: None)
        self.on_auth_error = on_auth_error or (lambda: None)
        self.status = "idle"
        self.last_error: str | None = None
        self.protocol: str | None = None
        self.codec: str | None = None
        self.frames = 0
        self.reconnects = 0
        self.last_ptz_error: str | None = None
        self._subscribers: set[asyncio.Queue[bytes | None]] = set()
        self._task: asyncio.Task[None] | None = None
        self._idle: asyncio.TimerHandle | None = None
        self._encoder: asyncio.subprocess.Process | None = None
        self._encoder_tasks: list[asyncio.Task[Any]] = []
        self._encoder_failed = False
        self._client: MissClient | None = None
        self._cache = bytearray()
        self._cache_valid = False
        self._closed = False
        self._lifecycle_lock = asyncio.Lock()
        self._connection_lock = asyncio.Lock()
        self._control_tasks: set[asyncio.Task[Any]] = set()
        self._ptz_busy = False

    @property
    def supports_pan_tilt(self) -> bool:
        return self.device.model in PAN_TILT_MODELS

    async def _connect_client(self, *, start_video: bool) -> MissClient:
        provisioning = await self.cloud.provision(self.device)
        client = await MissClient.connect(
            self.options.host or self.device.host,
            provisioning,
            model=self.device.model,
            transport=self.options.transport,
            quality=self.options.quality,
            start_video=start_video,
        )
        self.protocol = client.connection.protocol
        return client

    async def pan_tilt(self, direction: str) -> None:
        """Move one step without opening a competing video connection.

        Creation, motor writes and closure share a lock with the video task.
        An idle camera gets a short control-only connection: no video command,
        encoder or HTTP subscriber. Overlapping button presses are rejected
        rather than queued into a long sequence of unintended movements.
        """
        if not isinstance(direction, str) or direction not in PAN_TILT_OPERATIONS:
            raise ProtocolError("Pan/tilt direction must be left, right, up or down")
        if not self.supports_pan_tilt:
            raise ProtocolError("Pan/tilt is not supported for this camera model")
        if self._closed:
            raise TransportError("Camera integration is unloading")
        if self._ptz_busy:
            raise TransportError("A pan/tilt command is still running; try again in a moment")
        self._ptz_busy = True
        task = asyncio.current_task()
        assert task is not None
        self._control_tasks.add(task)
        try:
            async with asyncio.timeout(PAN_TILT_TIMEOUT), self._connection_lock:
                if self._closed:
                    raise TransportError("Camera integration is unloading")
                client = self._client
                temporary = client is None
                if temporary:
                    client = await self._connect_client(start_video=False)
                assert client is not None
                try:
                    await client.pan_tilt(direction)
                    # Allow a discrete step to finish before another press or
                    # closing a temporary connection. Never repeat the command.
                    await asyncio.sleep(PAN_TILT_SETTLE_TIME)
                finally:
                    if temporary:
                        await client.close()
            self.last_ptz_error = None
        except AuthenticationError:
            self.last_ptz_error = "Xiaomi authentication expired; reauthenticate the integration"
            self.on_auth_error()
            raise
        except (XiaomiError, OSError, TimeoutError) as err:
            self.last_ptz_error = (
                str(err)
                if isinstance(err, XiaomiError)
                else "Pan/tilt connection failed or timed out"
            )
            raise TransportError(self.last_ptz_error) from None
        finally:
            self._control_tasks.discard(task)
            self._ptz_busy = False
            # Also persists any cloud credentials rotated during provisioning.
            self.on_state()

    async def _close_client(self) -> None:
        async with self._connection_lock:
            client, self._client = self._client, None
            if client is not None:
                await client.close()

    def _state(self, status: str) -> None:
        self.status = status
        self.on_state()

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[bytes | None]]:
        async with self._lifecycle_lock:
            if self._closed:
                raise TransportError("Camera integration is unloading")
            if self._idle is not None:
                self._idle.cancel()
                self._idle = None
            if self._task is not None and self._task.cancelling():
                await asyncio.gather(self._task, return_exceptions=True)
            queue: asyncio.Queue[bytes | None] = asyncio.Queue(QUEUE_SIZE)
            if self._cache_valid and self._cache:
                queue.put_nowait(bytes(self._cache))
            self._subscribers.add(queue)
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._run())
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
            if not self._subscribers and not self._closed:
                self._idle = asyncio.get_running_loop().call_later(
                    self.options.idle_timeout, self._stop_when_idle
                )

    def _stop_when_idle(self) -> None:
        self._idle = None
        if not self._subscribers and self._task is not None:
            self._task.cancel()

    def _publish(self, data: bytes) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                # Disconnect slow viewers instead of stalling camera reception.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)
                self._subscribers.discard(queue)

    def _finish(self) -> None:
        for queue in self._subscribers:
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(None)
        self._subscribers.clear()
        self._cache.clear()
        self._cache_valid = False

    async def _start_encoder(self) -> None:
        height = max(180, min(2160, self.options.height))
        command = [
            self.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "+genpts",
            "-probesize",
            "1048576",
            "-analyzeduration",
            "1000000",
            "-i",
            "pipe:0",
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            f"scale=-2:trunc(min({height}\\,ih)/2)*2",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-tune",
            "zerolatency",
            "-pix_fmt",
            "yuv420p",
            "-g",
            "40",
            "-bf",
            "0",
            "-f",
            "mpegts",
            "-mpegts_flags",
            "+resend_headers",
            "-muxdelay",
            "0",
            "-muxpreload",
            "0",
            "pipe:1",
        ]
        self._encoder = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._encoder_failed = False
        self._encoder_tasks = [
            asyncio.create_task(self._encoder_output()),
            asyncio.create_task(self._discard_encoder_errors()),
        ]

    async def _discard_encoder_errors(self) -> None:
        assert self._encoder is not None and self._encoder.stderr is not None
        # Drain stderr without logging command lines or endpoint credentials.
        while await self._encoder.stderr.read(4096):
            pass

    async def _encoder_output(self) -> None:
        assert self._encoder is not None and self._encoder.stdout is not None
        while data := await self._encoder.stdout.read(188 * 32):
            self._publish(data)
        self._encoder_failed = True

    async def _stop_encoder(self) -> None:
        process, self._encoder = self._encoder, None
        for task in self._encoder_tasks:
            task.cancel()
        await asyncio.gather(*self._encoder_tasks, return_exceptions=True)
        self._encoder_tasks.clear()
        if process is not None and process.returncode is None:
            if process.stdin is not None:
                process.stdin.close()
            with suppress(ProcessLookupError):
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                with suppress(ProcessLookupError):
                    process.kill()
                await process.wait()

    async def _capture(self, muxer: MpegTsMuxer) -> None:
        self._state("connecting")
        async with self._connection_lock:
            self._client = await self._connect_client(start_video=True)
        while True:
            packet = await self._client.read_video()
            self.codec = "H.264" if packet.codec == 4 else "H.265"
            video = muxer.feed(packet)
            if video is None:
                continue
            self.frames += 1
            if self.status != "streaming":
                self.last_error = None
                self._state("streaming")
            elif self.frames % 100 == 0:
                self.on_state()
            if self.options.video_mode == "h264":
                if self._encoder is None:
                    await self._start_encoder()
                assert self._encoder is not None and self._encoder.stdin is not None
                if self._encoder_failed or self._encoder.returncode is not None:
                    raise TransportError(
                        "H.264 conversion failed; check FFmpeg or select Original video"
                    )
                self._encoder.stdin.write(video.data)
                await asyncio.wait_for(self._encoder.stdin.drain(), 5)
            else:
                if video.keyframe:
                    self._cache.clear()
                    self._cache_valid = True
                if self._cache_valid:
                    self._cache.extend(video.data)
                    if len(self._cache) > MAX_CACHE:
                        self._cache.clear()
                        self._cache_valid = False
                self._publish(video.data)

    async def _run(self) -> None:
        muxer = MpegTsMuxer()
        failures = 0
        try:
            while not self._closed:
                frame_count = self.frames
                try:
                    await self._capture(muxer)
                except asyncio.CancelledError:
                    raise
                except AuthenticationError:
                    self.last_error = (
                        "Xiaomi authentication expired; reauthenticate the integration"
                    )
                    self.on_auth_error()
                    self._state("error")
                    break
                except (XiaomiError, OSError, TimeoutError) as err:
                    self.last_error = (
                        str(err)
                        if isinstance(err, XiaomiError)
                        else "Local camera or encoder connection failed"
                    )
                    self._state("reconnecting")
                    # A sustained session earns a fresh retry budget.
                    failures = 1 if self.frames - frame_count >= 100 else failures + 1
                    if failures >= 4:
                        self._state("error")
                        _LOGGER.warning("Xiaomi camera %s: %s", self.device.did, self.last_error)
                        break
                    self.reconnects += 1
                finally:
                    await self._close_client()
                muxer.restart()
                self._cache.clear()
                self._cache_valid = False
                if self._encoder_failed:
                    break
                await asyncio.sleep(min(2**failures, 8))
        except asyncio.CancelledError:
            pass
        finally:
            await self._close_client()
            await self._stop_encoder()
            self._finish()
            if self.status != "error":
                self._state("idle")

    async def close(self) -> None:
        self._closed = True
        controls = list(self._control_tasks)
        for task in controls:
            task.cancel()
        await asyncio.gather(*controls, return_exceptions=True)
        if self._idle is not None:
            self._idle.cancel()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._finish()


class LoopbackServer:
    """A random-port HTTP source inside this process, never bound to the LAN."""

    def __init__(self, sessions: dict[str, CameraSession]) -> None:
        self.sessions = sessions
        self._token = secrets.token_urlsafe(32)
        self._runner: web.AppRunner | None = None
        self.port = 0

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/{token}/{did}.ts", self._stream)
        self._runner = web.AppRunner(app, access_log=None, shutdown_timeout=2)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await site.start()
        assert site._server is not None
        self.port = site._server.sockets[0].getsockname()[1]

    def source(self, did: str) -> str:
        return f"http://127.0.0.1:{self.port}/{self._token}/{did}.ts"

    async def _stream(self, request: web.Request) -> web.StreamResponse:
        if not secrets.compare_digest(request.match_info["token"], self._token):
            raise web.HTTPNotFound()
        session = self.sessions.get(request.match_info["did"])
        if session is None:
            raise web.HTTPNotFound()
        async with session.subscribe() as queue:
            try:
                first = await asyncio.wait_for(queue.get(), 45)
            except TimeoutError:
                raise web.HTTPServiceUnavailable(
                    text="Camera did not produce video in time"
                ) from None
            if first is None:
                raise web.HTTPServiceUnavailable(
                    text=session.last_error or "Camera stream is unavailable"
                )
            response = web.StreamResponse(
                headers={"Content-Type": "video/mp2t", "Cache-Control": "no-store"}
            )
            try:
                await response.prepare(request)
                await response.write(first)
                while True:
                    data = await asyncio.wait_for(queue.get(), 30)
                    if data is None:
                        break
                    await asyncio.wait_for(response.write(data), 10)
            except (ConnectionError, TimeoutError, asyncio.CancelledError):
                pass
            return response

    async def close(self) -> None:
        await asyncio.gather(*(session.close() for session in self.sessions.values()))
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
