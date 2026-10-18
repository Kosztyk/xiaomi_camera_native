"""Optional startup cache. Observing video must never delay its delivery."""

from __future__ import annotations

from .media import NAL_START, PMT_PID, VIDEO_PID


class H264StartupCache:
    """Observe our video-only TS output and retain a bounded recent GOP.

    A missing marker, unknown PID or malformed packet simply means no cache.
    Callers always forward the original bytes, including partial TS packets.
    """

    def __init__(self, max_size: int = 4 * 1024 * 1024) -> None:
        self.max_size = max_size
        self.disabled = False
        self._partial = bytearray()
        self._tables: dict[int, bytes] = {}
        self._gop = bytearray()
        self._valid = False
        self._headers_ready = False
        self._checking_headers = False
        self._header_types: set[int] = set()
        self._nal_tail = b""

    def invalidate(self) -> None:
        """Discard cached video, retaining alignment of an active encoder pipe."""
        self._tables.clear()
        self._gop.clear()
        self._valid = False
        self._headers_ready = False
        self._checking_headers = False
        self._header_types.clear()
        self._nal_tail = b""

    def clear(self) -> None:
        self.invalidate()
        self._partial.clear()
        self.disabled = False

    def disable(self) -> None:
        self.clear()
        self.disabled = True

    def snapshot(self) -> bytes:
        if self.disabled or not self._valid or not self._headers_ready:
            return b""
        if len(self._gop) + len(self._partial) > self.max_size:
            return b""
        # The partial prefix was already forwarded to existing viewers. A new
        # viewer needs it too, before the next raw pipe chunk completes it.
        return bytes(self._gop + self._partial)

    def _observe_codec_headers(self, packet: bytes, start: bool, keyframe: bool) -> None:
        if start and not keyframe:
            self._checking_headers = False
            return
        if not packet[3] & 0x10:
            return
        offset = 5 + packet[4] if packet[3] & 0x20 else 4
        payload = packet[offset:]
        if start:
            if len(payload) < 9 or payload[:3] != b"\x00\x00\x01":
                self._checking_headers = False
                return
            payload = payload[9 + payload[8] :]
        probe = self._nal_tail + payload
        for marker in NAL_START.finditer(probe):
            if marker.end() < len(probe):
                kind = probe[marker.end()] & 0x1F
                if kind in {5, 7, 8}:
                    self._header_types.add(kind)
        self._nal_tail = probe[-4:]
        if self._header_types == {5, 7, 8}:
            self._headers_ready = True
            self._checking_headers = False

    def feed(self, chunk: bytes) -> None:
        if self.disabled:
            return
        self._partial.extend(chunk)
        size = len(self._partial) // 188 * 188
        complete = bytes(self._partial[:size])
        del self._partial[:size]
        for offset in range(0, size, 188):
            packet = complete[offset : offset + 188]
            if packet[0] != 0x47 or packet[1] & 0x80:
                self.disable()
                return
            adaptation = bool(packet[3] & 0x20)
            if adaptation and packet[4] > 183:
                self.disable()
                return
            pid = ((packet[1] & 0x1F) << 8) | packet[2]
            start = bool(packet[1] & 0x40)
            if pid in {0, PMT_PID} and start and packet[3] & 0x10:
                self._tables[pid] = packet
            keyframe = (
                pid == VIDEO_PID
                and start
                and adaptation
                and packet[4] > 0
                and bool(packet[5] & 0x40)
            )
            if keyframe:
                self._gop = bytearray(b"".join(self._tables.get(p, b"") for p in (0, PMT_PID)))
                self._valid = len(self._tables) == 2
                self._headers_ready = False
                self._checking_headers = True
                self._header_types.clear()
                self._nal_tail = b""
            if pid == VIDEO_PID and self._checking_headers:
                self._observe_codec_headers(packet, start, keyframe)
            if self._valid:
                if len(self._gop) + 188 > self.max_size:
                    self._gop.clear()
                    self._valid = False
                else:
                    self._gop.extend(packet)
