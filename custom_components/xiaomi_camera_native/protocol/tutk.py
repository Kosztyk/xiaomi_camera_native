"""Opt-in pure-Python legacy TUTK LAN transport for ipc020.

Protocol framing adapted from AlexxIT/go2rtc v1.9.15 pkg/tutk (MIT).
No proprietary SDK, binary or external go2rtc process is needed.
Only direct LAN address mode is implemented; relay/cloud discovery is not.
The packet format is based on observed TUTK versions 16 and 25, and remains
User-reported working on chuangmi.camera.ipc020 / firmware 4.0.9_0102;
other hardware and firmware revisions remain unverified.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import socket
import struct
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass

from .buffer import ByteLimitedQueue
from .cloud import LegacyProvisioning
from .crypto import decode_media, shared_key
from .errors import ProtocolError, TransportError
from .miss import PAN_TILT_OPERATIONS, VideoPacket

_LOGGER = logging.getLogger(__name__)
_P2P_PORT = 32761
_MAX_VIDEO_FRAME = 2 * 1024 * 1024
_MAX_QUEUE = 96
_MAX_MEDIA_QUEUE_BYTES = 8 * 1024 * 1024
_REORDER_WINDOW = 5
_SESSION_TIMEOUT = 6.0
_CONNECT_RETRIES = 3
_CHARLIE = b"Charlie is the designer of P2P!!"
# Fixed permutations from go2rtc's open-source TUTK implementation.
_SWAP16 = (11, 9, 8, 15, 13, 10, 12, 14, 2, 1, 5, 0, 6, 4, 7, 3)


def _rol32(v: int, n: int) -> int:
    n &= 31
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF if n else v


def _transcode(src: bytes, *, reverse: bool) -> bytes:
    """TUTK's packet obfuscation (not media encryption)."""
    out = bytearray(len(src))
    full = len(src) // 16 * 16
    for start in range(0, full, 16):
        data = src[start : start + 16]
        tmp = bytearray(16)
        if reverse:
            for i in (0, 4, 8, 12):
                x = struct.unpack_from('<I', data, i)[0]
                struct.pack_into('<I', tmp, i, _rol32(x, i + 3))
            swapped = bytes(tmp[i] for i in _SWAP16)
            tmp = bytearray(swapped[i] ^ _CHARLIE[i] for i in range(16))
            for i in (0, 4, 8, 12):
                struct.pack_into('<I', out, start + i, _rol32(struct.unpack_from('<I', tmp, i)[0], i + 1))
        else:
            for i in (0, 4, 8, 12):
                x = struct.unpack_from('<I', data, i)[0]
                struct.pack_into('<I', tmp, i, _rol32(x, -i - 1))
            tmp = bytearray(tmp[i] ^ _CHARLIE[i] for i in range(16))
            swapped = bytes(tmp[i] for i in _SWAP16)
            for i in (0, 4, 8, 12):
                struct.pack_into('<I', out, start + i, _rol32(struct.unpack_from('<I', swapped, i)[0], -i - 3))
    remainder = len(src) - full
    if remainder:
        if reverse:
            tmp = src[full:][::-1] if remainder == 2 else _swap_short(src[full:])
            out[full:] = bytes(x ^ _CHARLIE[i] for i, x in enumerate(tmp))
        else:
            tmp = bytes(x ^ _CHARLIE[i] for i, x in enumerate(src[full:]))
            out[full:] = _swap_short(tmp)
    return bytes(out)


def _swap_short(data: bytes) -> bytes:
    n = len(data)
    if n == 2:
        return data[::-1]
    if n == 4:
        return bytes(data[i] for i in (2, 3, 0, 1))
    if n == 8:
        return bytes(data[i] for i in (7, 4, 3, 2, 1, 6, 5, 0))
    return data


def encode_packet(src: bytes) -> bytes:
    return _transcode(src, reverse=False)


def decode_packet(src: bytes) -> bytes:
    return _transcode(src, reverse=True)


def connect_by_uid(uid: str, sid: bytes, stage: int) -> bytes:
    if not 1 <= len(uid) <= 36 or not uid.isascii() or len(sid) != 8:
        raise ProtocolError("Invalid legacy P2P identity")
    if stage not in (1, 2):
        raise ValueError("Only direct LAN P2P is supported")
    msg = bytearray(68)
    msg[:4] = b'\x04\x02\x19\x02'
    struct.pack_into('<H', msg, 4, 52)
    msg[8:11] = b'\x01\x06\x21'
    msg[16 : 16 + len(uid)] = uid.encode('ascii')
    msg[52:56] = b'\x06\x00\x03\x03'
    msg[56:64] = sid
    msg[64] = stage
    return bytes(msg)


@dataclass
class TutkStatus:
    stage: str = 'not_started'
    sdk: str = 'unknown'
    auth_mode: str = 'unknown'
    video_packets: int = 0
    dropped_packets: int = 0
    malformed_packets: int = 0
    last_control: str = 'not_sent'
    media_results: str = 'not_run'
    # Sanitized PTZ transport evidence, never a physical movement confirmation.
    ptz_command_seq: int | None = None
    ptz_ack_state: str = 'not_sent'  # not_sent, waiting, matched, timeout, aborted
    ptz_ack_ms: int | None = None
    ptz_unmatched_acks: int = 0
    ptz_app_responses: int = 0  # Uncorrelated IOCtrl messages, NOT motor success.
    ptz_last_direction: str = 'not_sent'


class TutkClient:
    """Single camera socket + bounded queues; no parallel recv from the same socket."""

    class _Connection:
        protocol = 'tutk+udp'

    def __init__(self, host: str, provision: LegacyProvisioning, on_status: Callable[[TutkStatus], None] | None) -> None:
        self.host = host
        self.provision = provision
        self.status = TutkStatus(auth_mode=provision.auth_mode)
        self.on_status = on_status or (lambda _value: None)
        self.connection = self._Connection()
        self._sock: socket.socket | None = None
        self._peer = (host, _P2P_PORT)
        self._sid = os.urandom(8)
        self._version = 0
        self._sid16 = b''
        self._read_task: asyncio.Task[None] | None = None
        self._control_lock = asyncio.Lock()
        self._cmd_ack = asyncio.Event()
        self._pending_ack_seq: int | None = None
        self._pending_ack_token: bytes | None = None
        self._pending_motor = False
        self._media: ByteLimitedQueue[tuple[bytes, bytes] | None] = ByteLimitedQueue(
            _MAX_QUEUE, _MAX_MEDIA_QUEUE_BYTES,
            lambda item: len(item[0]) + len(item[1]) if item else 0,
        )
        self._responses: asyncio.Queue[bytes] = asyncio.Queue(12)
        self._closed = False
        self._seq_ch0 = 0
        self._seq_ch1 = 0
        self._seq_cmd = 0
        self._seq_cmd2 = 0
        self._seq_cnt = 0
        self._recv_pkt0 = 0
        self._recv_pkt1 = 0
        self._recv_cmd2 = 0
        self._reorder_seq = 0
        self._reorder: dict[int, bytes] = {}
        self._frame_seq = -1
        self._chunk_seq = 0
        self._frame_size = 0
        self._frame = bytearray()
        self._key = None
        if provision.auth_mode == 'signed':
            self._key = shared_key(provision.device_public, provision.private)
        self._started = False

    def _stage(self, name: str) -> None:
        self.status.stage = name
        self.on_status(self.status)

    @classmethod
    async def connect(
        cls, host: str, provision: LegacyProvisioning, *,
        quality: str = 'hd', start_video: bool = True,
        on_status: Callable[[TutkStatus], None] | None = None,
    ) -> 'TutkClient':
        try:
            ip = ipaddress.IPv4Address(host)
            if ip.is_unspecified or ip.is_multicast or int(ip) == 0xFFFFFFFF:
                raise ValueError()
        except ValueError:
            raise ProtocolError('A valid local IPv4 address is required for TUTK') from None
        self = cls(str(ip), provision, on_status)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setblocking(False)
            sock.bind(('0.0.0.0', 0))
            self._sock = sock
            self._stage('lan_discovery')
            packet = connect_by_uid(provision.uid, self._sid, 1)
            result = await self._exchange(
                lambda d: len(d) >= 60 and d[8:12] == b'\x02\x06\x12\x00', packet
            )
            self._version = result[2]
            self.status.sdk = f'TUTK/{self._version}'
            self._stage('lan_handshake')
            await self._send(connect_by_uid(provision.uid, self._sid, 2))
            self._sid16 = bytearray(16)
            self._sid16[:2] = self._sid[:2]
            self._sid16[4] = 0x0C
            self._sid16[8:] = self._sid
            self._stage('p2p_authentication')
            username = (
                json.dumps({'public_key': provision.public.hex(), 'sign': provision.sign, 'account': 'admin'}, separators=(',', ':'))
                if provision.auth_mode == 'signed' else 'admin'
            )
            password = provision.password if provision.auth_mode == 'password' else ''
            s1 = self._client_start(0, username, password)
            s2 = self._client_start(1, username, password)
            await self._exchange(lambda d: len(d) >= 84 and d[28] == 0 and d[29] in (0x14,0x21), s1, s2)
            self._stage('authenticated')
            self._read_task = asyncio.create_task(self._receiver())
            if start_video:
                await self.start_media(quality)
            return self
        except BaseException:
            await self.close()
            raise

    async def _send(self, msg: bytes) -> None:
        if self._sock is None:
            raise TransportError('TUTK socket is closed')
        await asyncio.get_running_loop().sock_sendto(self._sock, encode_packet(msg), self._peer)

    async def _recv(
        self, timeout: float, *, negotiating: bool = False
    ) -> tuple[bytes, tuple[str, int]]:
        if self._sock is None:
            raise TransportError('TUTK socket is closed')
        end = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = end - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError
            raw, peer = await asyncio.wait_for(asyncio.get_running_loop().sock_recvfrom(self._sock, 2048), remaining)
            if peer[0] != self.host or len(raw) < 16 or (not negotiating and peer != self._peer):
                continue
            packet = decode_packet(raw)
            if packet[:2] == b'\x04\x02':
                return packet, peer

    async def _exchange(self, predicate: Callable[[bytes], bool], *packets: bytes) -> bytes:
        for _ in range(_CONNECT_RETRIES):
            for packet in packets:
                await self._send(packet)
            try:
                deadline = asyncio.get_running_loop().time() + _SESSION_TIMEOUT / _CONNECT_RETRIES
                while asyncio.get_running_loop().time() < deadline:
                    incoming, peer = await self._recv(
                        max(.01, deadline - asyncio.get_running_loop().time()),
                        negotiating=True,
                    )
                    if predicate(incoming):
                        # Only a matching handshake reply can select a new port.
                        self._peer = peer
                        return incoming
            except TimeoutError:
                continue
        raise TransportError(f'TUTK {self.status.stage} timed out')

    def _message(self, size: int) -> bytearray:
        if size > 1500 or size < 28:
            raise ProtocolError('TUTK message length exceeded')
        msg = bytearray(size)
        msg[:4] = b'\x04\x02\x19\x0a'
        struct.pack_into('<H', msg, 4, size - 16)
        msg[8:11] = b'\x07\x04\x21'
        msg[12:28] = self._sid16
        return msg

    def _client_start(self, index: int, username: str, password: str) -> bytes:
        if len(username.encode()) > 256 or len(password.encode()) > 256:
            raise ProtocolError('TUTK login field too long')
        msg = self._message(598)
        cmd = memoryview(msg)[28:]
        cmd[:4] = b'\x00\x00\x0b\x00'
        struct.pack_into('<H', cmd, 16, 546)
        if index == 0:
            cmd[18] = 1
        else:
            cmd[1] = 0x20
        struct.pack_into('<I', cmd, 20, int(time.time()*1000) & 0xFFFFFFFF)
        data = cmd[24:]
        u = username.encode()
        p = password.encode()
        data[:len(u)] = u
        data[257:257+len(p)] = p
        cfg = data[514:]
        cfg[4] = 4
        cfg[8:12] = b'\xfb\x07\x1f\x00'
        cfg[22] = 3
        return bytes(msg)

    async def _write_session(self, channel: int, msg: bytearray) -> None:
        if channel == 0:
            struct.pack_into('<H', msg, 6, self._seq_ch0)
            self._seq_ch0 = (self._seq_ch0 + 1) & 65535
        else:
            struct.pack_into('<H', msg, 6, self._seq_ch1)
            self._seq_ch1 = (self._seq_ch1 + 1) & 65535
            msg[14] = 1
        await self._send(bytes(msg))

    def _control_ack(self, cmd: bytes, *, counter: bool = False) -> None:
        """Handle IOCtrl ACKs without treating an older ACK as a PTZ success.

        V18/V16 IOCtrl 0x71 copies both request sequence (offset 4) and
        request ID (offset 20). go2rtc's older Session16 implementation is
        the reference. Other versions' counter ACKs cannot be conclusively
        attributed to one PTZ command, so they never confirm a motor write.

        Media-start behavior for existing camera firmware remains unchanged.
        """
        if not self._pending_motor:
            # Keep existing media initialization behavior, particularly for
            # untested TUTK >=25; no change to established video negotiation.
            self._cmd_ack.set()
            return
        if len(cmd) < 24 or counter:
            self.status.ptz_unmatched_acks += 1
            self.on_status(self.status)
            return
        seq = struct.unpack_from('<H', cmd, 4)[0]
        valid = seq == self._pending_ack_seq
        if self._version < 25:
            # Legacy firmware echoes this per-command request ID; checking it
            # prevents a coincidental 16-bit sequence match from a stale ACK.
            valid = valid and cmd[20:24] == self._pending_ack_token
        if valid:
            self._cmd_ack.set()
        else:
            self.status.ptz_unmatched_acks += 1
            self.on_status(self.status)

    async def _send_control(self, ctrl: int, payload: bytes, *, motor: bool = False) -> None:
        if len(payload) > 900:
            raise ProtocolError('TUTK IO control too large')
        async with self._control_lock:
            self._cmd_ack.clear()
            if self._version >= 25:
                msg = self._message(28 + 28 + 4 + len(payload))
                cmd = memoryview(msg)[28:]
                cmd[:4] = b'\x00\x70\x0b\x00'
                seq = self._seq_cmd
                struct.pack_into('<H', cmd, 4, seq)
                self._seq_cmd = (self._seq_cmd + 1) & 65535
                cmd[9] = 0x70
                cmd[12] = 1
                struct.pack_into('<H', cmd, 16, len(msg) - 52)
                struct.pack_into('<H', cmd, 10, self._seq_cmd2)
                struct.pack_into('<H', cmd, 20, self._seq_cmd2)
                self._seq_cmd2 = (self._seq_cmd2 + 1) & 65535
                struct.pack_into('<I', cmd, 28, ctrl)
                cmd[32:32+len(payload)] = payload
                token = None
            else:
                msg = self._message(28 + 24 + 4 + len(payload))
                cmd = memoryview(msg)[28:]
                cmd[:4] = b'\x00\x70\x0b\x00'
                self._seq_cmd = (self._seq_cmd + 1) & 65535
                seq = self._seq_cmd
                struct.pack_into('<H', cmd, 4, seq)
                struct.pack_into('<H', cmd, 16, len(payload) + 4)
                struct.pack_into('<I', cmd, 20, int(time.time()*1000) & 0xFFFFFFFF)
                token = bytes(cmd[20:24])
                struct.pack_into('<I', cmd, 24, ctrl)
                cmd[28:28+len(payload)] = payload
            self._pending_ack_seq = seq
            self._pending_ack_token = token
            self._pending_motor = motor
            if motor:
                self.status.ptz_command_seq = seq
                self.status.ptz_ack_state = 'waiting'
                self.status.ptz_ack_ms = None
            # Motor commands are non-idempotent. One packet only, even when
            # the ACK is lost. Media setup retains its original retry policy.
            attempts = 1 if motor else 3
            try:
                if motor:
                    self.on_status(self.status)
                for _ in range(attempts):
                    sent_at = time.monotonic()
                    await self._write_session(0, msg)
                    try:
                        await asyncio.wait_for(self._cmd_ack.wait(), 1.25)
                    except TimeoutError:
                        continue
                    if motor:
                        self.status.ptz_ack_state = 'matched'
                        self.status.ptz_ack_ms = max(0, int((time.monotonic() - sent_at) * 1000))
                    return
                if motor:
                    self.status.ptz_ack_state = 'timeout'
                    raise TransportError('TUTK motor command not acknowledged (single attempt)')
                raise TransportError('TUTK control message not acknowledged')
            finally:
                self._pending_ack_seq = None
                self._pending_ack_token = None
                self._pending_motor = False
                self._cmd_ack.clear()

    async def start_media(self, quality: str = 'hd') -> None:
        """Try IMILAB A1 legacy media sequence, unverified for ipc020."""
        if quality not in {'hd','sd','auto','0','1','2','3','4','5'}:
            raise ProtocolError('Invalid legacy video quality')
        self._stage('media_start')
        value = {'hd': 3,'sd': 1,'auto': 0}.get(quality, int(quality) if quality.isdigit() else 3)
        # Existing IMILAB A1 command sequence; not yet verified for ipc020.
        # Issue all three commands even if a firmware does not acknowledge one,
        # so one unsupported audio command cannot mask a usable video command.
        results: list[str] = []
        for label, ctrl, data in (
            ('audio', 0x0300, b'{}'),
            ('video', 0x01FF, b'{}'),
            ('quality', 0x0320, json.dumps({'videoquality': value}, separators=(',', ':')).encode()),
        ):
            self._stage('media_' + label)
            try:
                await self._send_control(ctrl, data)
                results.append(label + ':ack')
            except TransportError:
                results.append(label + ':no_ack')
            self.status.media_results = ','.join(results)
            self.on_status(self.status)
        self._started = True
        self._stage('waiting_for_video')

    def _put_frame(self, frame_info: bytes, payload: bytes) -> None:
        if len(frame_info) < 1 or len(payload) < 1 or len(payload) > _MAX_VIDEO_FRAME:
            self.status.malformed_packets += 1
            return
        try:
            self._media.put_nowait((frame_info, payload))
        except asyncio.QueueFull:
            self.status.dropped_packets += 1

    def _msg(self, cmd: bytes) -> bytearray:
        msg = self._message(28 + len(cmd))
        msg[28:] = cmd
        return msg

    async def _handle_ch1(self, cmd: bytes) -> None:
        if len(cmd) < 24:
            return
        if cmd[:2] == b'\x00\x00' and self._version < 25 and len(cmd) >= 56:
            out = bytearray(24 + 32)
            out[:4] = b'\x00\x14\x0b\x00'
            out[16] = 32
            out[20:24] = cmd[20:24]
            out[24:56] = cmd[-32:]
            await self._write_session(1, self._msg(out))
            out = bytearray(36)
            out[:4] = b'\x00\x12\x0b\x00'
            out[16] = 12
            out[24] = 2
            out[28] = 1
            out[33] = 1
            await self._write_session(1, self._msg(out))
        elif cmd[:2] == b'\x00\x20' and self._version >= 25:
            out = bytearray(28 + 36)
            out[:4] = b'\x00\x21\x0b\x00'
            out[16] = 36
            out[20:24] = cmd[20:24]
            out[33] = 1; out[35] = 1; out[36] = 1; out[40] = 4
            out[44:48] = b'\xfb\x07\x1f\x00'
            out[58] = 3; out[60] = 1
            await self._write_session(1, self._msg(out))
        elif cmd[:2] in (b'\x00\x07', b'\x00\x08'):
            out = bytearray(28)
            out[:4] = b'\x01\x0a\x0b\x00' if cmd[1] == 7 else b'\x01\x09\x0b\x00'
            if cmd[1] == 7:
                out[20] = 1
            else:
                out[20:28] = cmd[20:28]
            await self._write_session(1, self._msg(out))

    async def _ack_counters(self) -> None:
        out = bytearray(24)
        out[:4] = b'\x09\x00\x0b\x00'
        struct.pack_into('<H', out, 4, self._seq_cmd)
        self._seq_cmd = (self._seq_cmd + 1) & 65535
        struct.pack_into('<H', out, 8, self._recv_pkt0)
        self._recv_pkt0 = self._recv_pkt1
        struct.pack_into('<H', out, 10, self._recv_pkt1)
        struct.pack_into('<H', out, 12, self._recv_cmd2)
        struct.pack_into('<H', out, 18, self._seq_cnt)
        self._seq_cnt = (self._seq_cnt + 1) & 65535
        struct.pack_into('<H', out, 20, int(time.time()*1000) & 65535)
        await self._write_session(0, self._msg(out))

    async def _handle_v25_chunk(self, cmd: bytes) -> None:
        if len(cmd) < 40:
            return
        flags = cmd[1]
        cmd2 = cmd[16:] if flags & 8 else cmd[8:]
        if len(cmd2) < 20:
            return
        seq = struct.unpack_from('<H', cmd2, 2)[0]
        distance = (seq - self._reorder_seq) & 0xFFFF
        if distance >= 0x8000 or seq in self._reorder:
            return
        if distance:
            self._reorder[seq] = cmd
            if len(self._reorder) <= _REORDER_WINDOW:
                return
            # The gap outlasted the reorder window. Resume at the oldest
            # buffered packet, discarding the incomplete frame before it.
            self.status.dropped_packets += 1
            self._frame.clear()
            self._reorder_seq = min(
                self._reorder, key=lambda number: (number - self._reorder_seq) & 0xFFFF
            )
            cmd = self._reorder.pop(self._reorder_seq)
        await self._handle_v25_ordered(cmd)
        self._reorder_seq = (self._reorder_seq + 1) & 65535
        while self._reorder_seq in self._reorder:
            pending = self._reorder.pop(self._reorder_seq)
            await self._handle_v25_ordered(pending)
            self._reorder_seq = (self._reorder_seq + 1) & 65535

    async def _handle_v25_ordered(self, cmd: bytes) -> None:
        flags = cmd[1]
        cmd2 = cmd[16:] if flags & 8 else cmd[8:]
        if len(cmd2) < 20:
            return
        seq = struct.unpack_from('<H', cmd2, 2)[0]
        chunks = struct.unpack_from('<H', cmd2, 4)[0]
        chunk_idx = struct.unpack_from('<H', cmd2, 6)[0]
        if chunk_idx == 0 or chunks == 1:
            self._frame.clear()
            self._chunk_seq = seq
        elif not self._frame or seq != self._chunk_seq:
            self.status.dropped_packets += 1
            self._frame.clear()
            return
        if len(self._frame) + len(cmd2) - 20 > _MAX_VIDEO_FRAME + 32:
            self._frame.clear(); self.status.dropped_packets += 1
            return
        self._frame.extend(cmd2[20:])
        if not (flags & 1):
            self._chunk_seq = (self._chunk_seq + 1) & 65535
            return
        self._recv_pkt1 = seq
        await self._ack_counters()
        if len(self._frame) >= 33:
            self._put_frame(bytes(self._frame[-32:]), bytes(self._frame[:-32]))
        self._frame.clear()

    async def _handle_ch0(self, cmd: bytes) -> None:
        if len(cmd) < 24:
            self.status.malformed_packets += 1
            return
        if self._version >= 25:
            if cmd[0] in (3,5,7):
                await self._handle_v25_chunk(cmd)
            elif cmd[0] == 0:
                self._recv_cmd2 = struct.unpack_from('<H', cmd, 2)[0]
                await self._ack_counters()
                if cmd[1] == 0x71:
                    self._control_ack(cmd)
            elif cmd[0] == 9:
                ack = struct.unpack_from('<H', cmd, 12)[0]
                if self._seq_cmd > ack:
                    self._control_ack(cmd, counter=True)
            elif cmd[:2] == b'\x0a\x08':
                out = bytearray(20)
                out[:4] = b'\x0b\x00\x0b\x00'
                out[8:10] = cmd[8:10]
                await self._write_session(0, self._msg(out))
            return
        if cmd[:2] == b'\x00\x71':
            self._control_ack(cmd)
        elif cmd[:2] == b'\x00\x70':
            # Count only explicitly recognized TUTK vendor control IDs. These
            # inbound messages contain no trustworthy motor-position result.
            if len(cmd) >= 28 and struct.unpack_from('<I', cmd, 24)[0] == 0xF005:
                self.status.ptz_app_responses += 1
                self.on_status(self.status)
            out = bytearray(24)
            out[:4] = b'\x00\x71\x0b\x00'
            out[2:6] = cmd[2:6]
            out[20:24] = cmd[20:24]
            await self._write_session(0, self._msg(out))
        elif cmd[:2] == b'\x00\x12':
            out = bytearray(44)
            out[:4] = b'\x00\x13\x0b\x00'
            out[16] = 20
            out[24:36] = cmd[24:36]
            await self._write_session(0, self._msg(out))
        elif cmd[0] == 1 and cmd[1] in (3,4):
            size = struct.unpack_from('<I', cmd, 8)[0]
            if cmd[1] == 4:
                hsize = struct.unpack_from('<H', cmd, 14)[0]
                if hsize == 0 or hsize > 128 or len(cmd) < 24 + hsize:
                    self.status.malformed_packets += 1
                    return
                self._put_frame(cmd[24:24+hsize], cmd[24+hsize:])
            elif size < _MAX_VIDEO_FRAME:
                seq = struct.unpack_from('<H', cmd, 4)[0]
                chunk = struct.unpack_from('<H', cmd, 12)[0]
                hsize = struct.unpack_from('<H', cmd, 14)[0]
                if chunk == 0:
                    self._frame_seq = seq
                    self._chunk_seq = 0
                    self._frame.clear()
                    self._frame_size = size + hsize
                elif seq != self._frame_seq or chunk != self._chunk_seq:
                    self.status.dropped_packets += 1
                    self._frame.clear()
                    self._frame_size = 0
                    return
                if self._frame_size == 0 or len(self._frame) + len(cmd) - 24 > _MAX_VIDEO_FRAME + 128:
                    self._frame.clear(); self._frame_size = 0
                    return
                self._frame.extend(cmd[24:])
                if len(self._frame) >= self._frame_size:
                    self._put_frame(bytes(self._frame[size:self._frame_size]), bytes(self._frame[:size]))
                    self._frame.clear(); self._frame_size = 0
                else:
                    self._chunk_seq = (self._chunk_seq + 1) & 65535

    async def _receiver(self) -> None:
        try:
            while not self._closed:
                packet, _peer = await self._recv(30)
                if packet[8] == 0x28 and len(packet) == 24:
                    pong = bytearray(packet)
                    pong[8] = 0x27; pong[10] = 0x21
                    await self._send(pong)
                elif packet[8] == 0x08 and len(packet) >= 28:
                    try:
                        channel = packet[14]
                        if channel == 0:
                            await self._handle_ch0(packet[28:])
                        elif channel == 1:
                            await self._handle_ch1(packet[28:])
                        elif channel == 5 and len(packet) == 48:
                            pong = bytearray(packet)
                            pong[8] = 7; pong[10] = 0x21; pong[32] = 0x41
                            await self._send(pong)
                    except (IndexError, struct.error, ValueError):
                        self.status.malformed_packets += 1
        except asyncio.CancelledError:
            pass
        except (OSError, TimeoutError, TransportError, ProtocolError):
            if not self._closed:
                self._stage('connection_lost')
        finally:
            with suppress(asyncio.QueueFull):
                self._media.put_nowait(None)

    async def read_video(self, timeout: float = 15) -> VideoPacket:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                self._stage('video_payload_unrecognized' if self.status.malformed_packets else 'no_video_frames')
                raise TransportError('TUTK authenticated but no valid video frames received')
            try:
                item = await asyncio.wait_for(self._media.get(), timeout=remaining)
            except TimeoutError:
                self._stage('video_payload_unrecognized' if self.status.malformed_packets else 'no_video_frames')
                raise TransportError('TUTK authenticated but no valid video frames received') from None
            if item is None:
                raise TransportError('TUTK session closed before receiving video')
            frame_info, payload = item
            codec = {0x4E: 4, 0x50: 5}.get(frame_info[0])
            if codec is None:
                continue  # Audio and unsupported codecs do not interrupt video.
            if self._key:
                try:
                    payload = decode_media(self._key, payload)
                except ProtocolError:
                    self._stage('video_decryption_failed')
                    raise
            if b'\x00\x00\x01' not in payload[:64]:
                self.status.malformed_packets += 1
                if self.status.malformed_packets == 1:
                    self._stage('invalid_video_payload')
                continue
            self.status.video_packets += 1
            if self.status.video_packets == 1:
                self._stage('receiving_video')
            elif self.status.video_packets % 100 == 0:
                self.on_status(self.status)
            return VideoPacket(codec, self.status.video_packets, 0, int(time.monotonic()*1000), payload)

    @property
    def video_ready(self) -> bool:
        return (
            self._started
            and not self._closed
            and self._read_task is not None
            and not self._read_task.done()
            and self.status.video_packets > 0
        )

    async def pan_tilt(self, direction: str) -> None:
        # This client is restricted to ipc020, which physically
        # has a horizontal motor only. No 0xF005 tilt operations are valid here.
        if direction not in ('left', 'right'):
            raise ProtocolError('ipc020 supports horizontal pan only')
        if not self.video_ready:
            raise ProtocolError('TUTK pan requires a live video connection')
        # Owner-reported working for ipc020 horizontal motion (6/6 in b3).
        # No vertical motor is present; transport ACK does not prove movement.
        self.status.last_control = 'attempted'
        self.status.ptz_last_direction = direction
        try:
            payload = json.dumps(
                {'operation': PAN_TILT_OPERATIONS[direction]}, separators=(',', ':')
            ).encode()
            await self._send_control(0xF005, payload, motor=True)
        except (OSError, TransportError, TimeoutError, asyncio.CancelledError):
            self.status.last_control = 'unacknowledged'
            if self.status.ptz_ack_state == 'waiting':
                self.status.ptz_ack_state = 'aborted'
            raise
        else:
            self.status.last_control = 'transport_ack_only'
        finally:
            self.on_status(self.status)

    async def close(self) -> None:
        self._closed = True
        if self._read_task is not None:
            self._read_task.cancel()
            await asyncio.gather(self._read_task, return_exceptions=True)
            self._read_task = None
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        with suppress(asyncio.QueueFull):
            self._media.put_nowait(None)
