"""Private b3 PTZ transport regression tests (no Home Assistant/hardware needed)."""
from __future__ import annotations

import asyncio
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from test_ipc020_tutk_transport import load_protocol


class MotorTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mod = load_protocol()
        provision = SimpleNamespace(uid='TEST_UID', password='SECRET', auth_mode='password',
                                    public=b'',private=b'',device_public=b'',sign='')
        self.client = self.mod.TutkClient('192.0.2.5', provision, None)
        self.client._version = 18
        self.client._started = True
        self.client._read_task = SimpleNamespace(done=lambda: False)
        self.client.status.video_packets = 1
        self.client._sid16 = bytes(16)
        self.writes = []

    @staticmethod
    def ack(msg, *, delta_seq=0, flip_token=False):
        out = bytearray(24)
        out[:4] = b'\x00\x71\x0b\x00'
        seq = (struct.unpack_from('<H', msg, 32)[0] + delta_seq) & 0xffff
        struct.pack_into('<H', out, 4, seq)
        out[20:24] = msg[48:52]
        if flip_token:
            out[20] ^= 0x80
        return out

    async def test_ptz_requires_matching_sequence_and_request_id(self):
        async def transmit(channel, msg):
            self.writes.append(bytes(msg))
            await self.client._handle_ch0(self.ack(msg, delta_seq=-1))
            self.assertFalse(self.client._cmd_ack.is_set())
            await self.client._handle_ch0(self.ack(msg, flip_token=True))
            self.assertFalse(self.client._cmd_ack.is_set())
            await self.client._handle_ch0(self.ack(msg))
            self.assertTrue(self.client._cmd_ack.is_set())
        self.client._write_session = transmit
        await self.client.pan_tilt('right')
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.client.status.ptz_ack_state, 'matched')
        self.assertEqual(self.client.status.ptz_unmatched_acks, 2)
        self.assertEqual(self.client.status.ptz_last_direction, 'right')
        self.assertEqual(self.client.status.last_control, 'transport_ack_only')
        self.assertIsInstance(self.client.status.ptz_ack_ms, int)
        self.assertGreaterEqual(self.client.status.ptz_ack_ms, 0)
        self.assertIsNone(self.client._pending_ack_seq)

    async def test_motor_timeout_sends_exactly_one_datagram_and_cleans_state(self):
        published = []
        self.client.on_status = lambda status: published.append(
            (status.ptz_ack_state, status.last_control)
        )
        async def transmit(channel, msg):
            self.writes.append(bytes(msg))
            await self.client._handle_ch0(self.ack(msg, delta_seq=1))
        self.client._write_session = transmit
        with self.assertRaisesRegex(self.mod.TransportError, 'single attempt'):
            await self.client.pan_tilt('left')
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.client.status.ptz_ack_state, 'timeout')
        self.assertEqual(self.client.status.last_control, 'unacknowledged')
        self.assertIsNone(self.client.status.ptz_ack_ms)
        self.assertEqual(self.client.status.ptz_unmatched_acks, 1)
        self.assertIsNone(self.client._pending_ack_seq)
        self.assertFalse(self.client._pending_motor)
        self.assertEqual(published[-1], ('timeout', 'unacknowledged'))
        self.assertNotIn(('timeout', 'attempted'), published)

    async def test_socket_failure_publishes_terminal_motor_status(self):
        published = []
        self.client.on_status = lambda status: published.append(
            (status.ptz_ack_state, status.last_control)
        )
        self.client._write_session = AsyncMock(side_effect=OSError)
        with self.assertRaises(OSError):
            await self.client.pan_tilt('right')
        self.client._write_session.assert_awaited_once()
        self.assertFalse(self.client._pending_motor)
        self.assertEqual(published[-1], ('aborted', 'unacknowledged'))

    async def test_media_command_still_retries_and_accepts_ack(self):
        async def transmit(channel, msg):
            self.writes.append(bytes(msg))
            if len(self.writes) == 2:
                await self.client._handle_ch0(self.ack(msg))
        self.client._write_session = transmit
        await self.client._send_control(0x01FF, b'{}')
        self.assertEqual(len(self.writes), 2)
        self.assertEqual(self.client.status.ptz_ack_state, 'not_sent')

    async def test_recognized_response_count_does_not_claim_motor_success(self):
        async def transmit(channel, msg):
            self.writes.append(bytes(msg))
        self.client._write_session = transmit
        inbound = bytearray(28)
        inbound[:4] = b'\x00\x70\x0b\x00'
        struct.pack_into('<I', inbound, 24, 0xF005)
        await self.client._handle_ch0(inbound)
        self.assertEqual(self.client.status.ptz_app_responses, 1)
        self.assertEqual(self.client.status.ptz_ack_state, 'not_sent')
        self.assertEqual(self.client.status.last_control, 'not_sent')
        self.assertEqual(len(self.writes), 1)  # reply ACK only, no motor command

    async def test_v25_counter_ack_cannot_confirm_motor_write(self):
        self.client._version = 25
        async def transmit(channel, msg):
            self.writes.append(bytes(msg))
            counter = bytearray(24)
            counter[:4] = b'\x09\x00\x0b\x00'
            struct.pack_into('<H', counter, 12, 0)
            await self.client._handle_ch0(counter)
        self.client._write_session = transmit
        with self.assertRaises(self.mod.TransportError):
            await self.client.pan_tilt('right')
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.client.status.ptz_ack_state,'timeout')
        self.assertGreaterEqual(self.client.status.ptz_unmatched_acks,1)

    async def test_diagnostics_include_only_sanitized_ptz_fields(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]/'custom_components/xiaomi_camera_native'
        for part in ['camera.py','diagnostics.py']:
            body = (root/part).read_text()
            for key in ('ipc020_tutk_ptz_command_seq','ipc020_tutk_ptz_ack_state',
                        'ipc020_tutk_ptz_ack_ms','ipc020_tutk_ptz_unmatched_acks',
                        'ipc020_tutk_ptz_app_responses','ipc020_tutk_ptz_last_direction'):
                self.assertIn(key,body)
            self.assertNotIn('provision.uid',body)
            self.assertNotIn('provision.password',body)


if __name__ == '__main__':
    unittest.main()
