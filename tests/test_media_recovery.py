"""Regression tests for snapshot limits, stream recovery, and encoder cleanup."""

import asyncio
from contextlib import suppress
import importlib
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from test_ipc020_horizontal_only import isolated_code
from test_ipc020_tutk_transport import load_protocol


def protocol_module(name):
    load_protocol()
    return importlib.import_module("custom_components.xiaomi_camera_native.protocol." + name)


class SnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversized_invalid_and_partial_size_requests(self):
        snapshot = protocol_module("snapshot")
        spawn = AsyncMock()
        with patch.object(asyncio, "create_subprocess_exec", spawn):
            for width, height in (
                (16000, 16000), (4096, 4096), (4097, None),
                (None, 4097), (400, -1), (True, 480),
            ):
                with self.subTest(width=width, height=height):
                    self.assertIsNone(
                        await snapshot.async_get_snapshot("ffmpeg", "fixture", width=width, height=height)
                    )
        spawn.assert_not_awaited()

    async def test_4k_and_default_snapshots_keep_their_existing_behavior(self):
        snapshot = protocol_module("snapshot")
        jpeg = b"\xff\xd8data\xff\xd9"
        process = SimpleNamespace(
            returncode=0, communicate=AsyncMock(return_value=(jpeg, b"")), wait=AsyncMock(return_value=0)
        )
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)) as spawn:
            self.assertEqual(
                await snapshot.async_get_snapshot("ffmpeg", "fixture", width=4096, height=2160), jpeg
            )
            args = spawn.await_args.args
            self.assertEqual(args[args.index("-s") + 1], "4096x2160")
            self.assertEqual(await snapshot.async_get_snapshot("ffmpeg", "fixture", width=0), jpeg)
            self.assertNotIn("-s", spawn.await_args.args)


class MuxerTests(unittest.TestCase):
    def test_reconnect_accepts_a_different_codec_with_new_parameter_sets(self):
        media = protocol_module("media")
        muxer = media.MpegTsMuxer()
        for codec, nal_headers in (
            (4, (b"\x67sps", b"\x68pps", b"\x65idr")),
            (5, (b"\x40vps", b"\x42sps", b"\x44pps", b"\x26idr")),
        ):
            payload = b"".join(media.START + part for part in nal_headers)
            result = muxer.feed(media.VideoPacket(codec, 1, 0, 1000, payload))
            self.assertTrue(result.keyframe)
            self.assertEqual(muxer.codec, codec)
            muxer.restart()

    def test_mpeg_ts_packets_reassemble_the_original_pes(self):
        media = protocol_module("media")
        muxer = media.MpegTsMuxer()
        payload = bytes(range(256)) * 1024
        pts = 123456
        stream = muxer._packetize(payload, pts, True)
        self.assertEqual(len(stream) % 188, 0)
        fragments = []
        for index in range(0, len(stream), 188):
            packet = stream[index : index + 188]
            self.assertEqual(packet[0], 0x47)
            offset = 5 + packet[4] if packet[3] & 0x20 else 4
            fragments.append(packet[offset:])
        self.assertEqual(
            b"".join(fragments),
            b"\x00\x00\x01\xe0\x00\x00\x80\x80\x05" + media.encode_pts(pts) + payload,
        )


class MediaQueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_cs2_byte_budget_is_released_when_consumer_reads(self):
        cs2 = protocol_module("cs2")
        with patch.object(cs2, "MAX_CHANNEL_BYTES", 8):
            channel = cs2.DataChannel()
        frame = struct.pack(">I", 6) + b"sample"
        channel.feed(frame)
        with self.assertRaisesRegex(cs2.TransportError, "keep up"):
            channel.feed(frame)
        self.assertEqual(await channel.queue.get(), b"sample")
        channel.feed(frame)
        channel.close()
        self.assertIsNone(await channel.queue.get())
        channel.feed(frame)
        self.assertEqual(await channel.queue.get(), b"sample")

    async def test_tutk_byte_budget_counts_dropped_frames_and_resumes(self):
        tutk = load_protocol()
        with patch.object(tutk, "_MAX_MEDIA_QUEUE_BYTES", 8):
            client = tutk.TutkClient("127.0.0.1", SimpleNamespace(auth_mode="password"), None)
        client._put_frame(b"h", b"sample")
        client._put_frame(b"h", b"second")
        self.assertEqual(client.status.dropped_packets, 1)
        self.assertEqual(await client._media.get(), (b"h", b"sample"))
        client._put_frame(b"h", b"third")
        self.assertEqual(await client._media.get(), (b"h", b"third"))


class TutkReorderTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def packet(seq, chunk=0, chunks=1, last=True):
        command = bytearray(28)
        command[0] = 3
        command[1] = int(last)
        struct.pack_into("<HHH", command, 10, seq, chunks, chunk)
        return bytes(command) + bytes(12) + b"\x4e" + bytes(31)

    def make_client(self):
        tutk = load_protocol()
        client = tutk.TutkClient("127.0.0.1", SimpleNamespace(auth_mode="password"), None)
        client._version = 25
        client._ack_counters = AsyncMock()
        return client

    async def test_gap_recovers_across_wrap_and_drops_orphaned_fragment(self):
        client = self.make_client()
        client._reorder_seq = 65534
        await client._handle_v25_chunk(self.packet(65534, chunks=3, last=False))
        await client._handle_v25_chunk(self.packet(0, chunk=2, chunks=3))
        for seq in range(1, 8):
            await client._handle_v25_chunk(self.packet(seq))
        await client._handle_v25_chunk(self.packet(65535, chunk=1, chunks=3, last=False))
        self.assertEqual(client._media.qsize(), 7)
        self.assertEqual(client._ack_counters.await_count, 7)
        self.assertEqual(client._reorder_seq, 8)
        self.assertEqual(client._reorder, {})
        self.assertGreaterEqual(client.status.dropped_packets, 1)

    async def test_short_reordering_and_duplicate_packets(self):
        client = self.make_client()
        await client._handle_v25_chunk(self.packet(1))
        await client._handle_v25_chunk(self.packet(1))
        self.assertEqual(client._media.qsize(), 0)
        await client._handle_v25_chunk(self.packet(0))
        await client._handle_v25_chunk(self.packet(1))
        self.assertEqual(client._media.qsize(), 2)
        self.assertEqual(client.status.dropped_packets, 0)


class EncoderCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_stopper_reaps_once_and_propagates_cancellation(self):
        session_type = isolated_code(
            "protocol/session.py", "CameraSession",
            ("_stop_encoder", "_reap_encoder"),
            {"asyncio": asyncio, "suppress": suppress},
        )
        session = session_type()
        waiting = asyncio.Event()
        can_exit = asyncio.Event()
        process = SimpleNamespace(returncode=None, stdin=SimpleNamespace(close=Mock()), terminate=Mock())

        async def wait_for_exit():
            waiting.set()
            await can_exit.wait()
            process.returncode = -15

        process.wait = AsyncMock(side_effect=wait_for_exit)
        reader = asyncio.create_task(asyncio.Event().wait())
        session._encoder = process
        session._encoder_tasks = [reader]
        session._encoder_stop_task = None
        first = asyncio.create_task(session._stop_encoder())
        try:
            await asyncio.wait_for(waiting.wait(), 1)
            self.assertIs(session._encoder, process)
            self.assertFalse(reader.done())
            second = asyncio.create_task(session._stop_encoder())
            first.cancel()
            await asyncio.sleep(0)
            first.cancel()
            self.assertFalse(first.done())
        finally:
            can_exit.set()
        with self.assertRaises(asyncio.CancelledError):
            await first
        await second
        process.terminate.assert_called_once()
        process.wait.assert_awaited_once()
        self.assertIsNone(session._encoder)
        self.assertIsNone(session._encoder_stop_task)
        self.assertTrue(reader.done())
