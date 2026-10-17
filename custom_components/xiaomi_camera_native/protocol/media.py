"""Small video-only MPEG-TS muxer. Frames remain encoded; no decoder here."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from .errors import ProtocolError
from .miss import VideoPacket

PMT_PID = 0x1000
VIDEO_PID = 0x100
START = b"\x00\x00\x00\x01"
NAL_START = re.compile(b"\x00\x00\x00?\x01")


def crc32_mpeg(data: bytes) -> int:
    value = 0xFFFFFFFF
    for byte in data:
        value ^= byte << 24
        for _ in range(8):
            value = ((value << 1) ^ (0x04C11DB7 if value & 0x80000000 else 0)) & 0xFFFFFFFF
    return value


def nal_units(payload: bytes) -> list[bytes]:
    return [unit for unit in NAL_START.split(payload) if unit]


def nal_type(unit: bytes, codec: int) -> int:
    return unit[0] & 0x1F if codec == 4 else (unit[0] >> 1) & 0x3F


def encode_pts(pts: int) -> bytes:
    pts &= (1 << 33) - 1
    return bytes(
        (
            0x21 | ((pts >> 29) & 0x0E),
            (pts >> 22) & 0xFF,
            ((pts >> 14) & 0xFE) | 1,
            (pts >> 7) & 0xFF,
            ((pts << 1) & 0xFE) | 1,
        )
    )


@dataclass(frozen=True)
class MuxedVideo:
    data: bytes
    keyframe: bool


class MpegTsMuxer:
    """One camera session, with safe timestamps and repeated codec headers."""

    def __init__(self) -> None:
        self.codec: int | None = None
        self._cc: dict[int, int] = {}
        self._parameters: dict[int, bytes] = {}
        self._started = False
        self._last_input: int | None = None
        self._pts = 90000
        self._last_tables = -90000

    def _header(self, pid: int, start: bool, adaptation: bool) -> bytes:
        cc = self._cc.get(pid, 0)
        self._cc[pid] = (cc + 1) & 15
        return bytes(
            (
                0x47,
                ((pid >> 8) & 0x1F) | (0x40 if start else 0),
                pid & 255,
                (0x30 if adaptation else 0x10) | cc,
            )
        )

    def restart(self) -> None:
        """Wait for fresh codec headers after reconnect, retaining TS continuity."""
        self._started = False
        self._parameters.clear()
        self._last_input = None
        self._pts += 4500

    def _section(self, pid: int, section: bytes) -> bytes:
        section += struct.pack(">I", crc32_mpeg(section))
        payload = b"\x00" + section
        return self._header(pid, True, False) + payload + b"\xff" * (184 - len(payload))

    def tables(self) -> bytes:
        pat = bytes.fromhex("00b00d0001c100000001f000")
        stream_type = 0x1B if self.codec == 4 else 0x24
        pmt = (
            bytes.fromhex("02b0120001c10000e100f000")
            + bytes((stream_type,))
            + bytes.fromhex("e100f000")
        )
        return self._section(0, pat) + self._section(PMT_PID, pmt)

    def _packetize(self, payload: bytes, pts: int, keyframe: bool) -> bytes:
        pes = b"\x00\x00\x01\xe0\x00\x00\x80\x80\x05" + encode_pts(pts) + payload
        packets = []
        first = True
        while pes:
            capacity = 176 if first else 184  # The first TS packet carries PCR.
            chunk, pes = pes[:capacity], pes[capacity:]
            adaptation = first or len(chunk) < 184
            header = self._header(VIDEO_PID, first, adaptation)
            if adaptation:
                size = 183 - len(chunk)
                if first:
                    pcr = ((pts - 27000) & ((1 << 33) - 1)) << 15 | 0x7E00
                    extra = bytes((0x10 | (0x40 if keyframe else 0),)) + pcr.to_bytes(6, "big")
                else:
                    extra = b"\x00" if size else b""
                header += bytes((size,)) + extra + b"\xff" * (size - len(extra))
            packets.append(header + chunk)
            first = False
        return b"".join(packets)

    def feed(self, packet: VideoPacket) -> MuxedVideo | None:
        if packet.codec not in {4, 5}:
            return None
        if self.codec is not None and packet.codec != self.codec:
            raise ProtocolError("Camera changed its video codec; a new stream session is required")
        self.codec = packet.codec
        units = nal_units(packet.payload)
        if not units:
            return None
        parameter_types = {7, 8} if self.codec == 4 else {32, 33, 34}
        present = {nal_type(unit, self.codec) for unit in units}
        for unit in units:
            kind = nal_type(unit, self.codec)
            if kind in parameter_types:
                self._parameters[kind] = START + unit
        is_vcl = (
            any(1 <= kind <= 5 for kind in present)
            if self.codec == 4
            else any(kind <= 31 for kind in present)
        )
        if not is_vcl:
            return None
        keyframe = (5 in present) if self.codec == 4 else bool(present.intersection(range(16, 24)))
        if not self._started:
            if not keyframe or not parameter_types.issubset(self._parameters):
                return None
            self._started = True
        if self._last_input is not None:
            delta = packet.timestamp_ms - self._last_input
            # Some Xiaomi clocks repeat, jump backwards, or reset to uptime.
            self._pts += 90 * (delta if 1 <= delta <= 1000 else 50)
        self._last_input = packet.timestamp_ms
        prefix = b""
        if keyframe:
            prefix = b"".join(
                self._parameters[kind] for kind in sorted(parameter_types) if kind not in present
            )
        aud_type = 9 if self.codec == 4 else 35
        aud = (
            b""
            if aud_type in present
            else START + (b"\x09\xf0" if self.codec == 4 else b"\x46\x01\x50")
        )
        data = b""
        if keyframe or self._pts - self._last_tables >= 90000:
            data = self.tables()
            self._last_tables = self._pts
        data += self._packetize(aud + prefix + packet.payload, self._pts, keyframe)
        return MuxedVideo(data, keyframe)
