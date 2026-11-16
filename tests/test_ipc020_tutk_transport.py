"""Offline TUTK transport tests (b2 baseline, retained in b3). No Xiaomi/HA access needed."""
from __future__ import annotations

import ast
import asyncio
import importlib
import json
import socket
import sys
import types
import unittest
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / 'custom_components' / 'xiaomi_camera_native'


def load_protocol():
    """Import pure protocol code, bypassing Home Assistant package initializer."""
    names = ('custom_components','custom_components.xiaomi_camera_native',
             'custom_components.xiaomi_camera_native.protocol')
    for name in names:
        if name not in sys.modules:
            module=types.ModuleType(name)
            module.__path__=[str(ROOT/name.replace('.','/'))]
            sys.modules[name]=module
    # The repository's CI packaging job deliberately installs no Home
    # Assistant/aiohttp/cryptography dependencies. Stub only imports external
    # to the standalone TUTK framing module; runtime imports real modules.
    prefix = 'custom_components.xiaomi_camera_native.protocol.'
    if prefix+'cloud' not in sys.modules:
        cloud = types.ModuleType(prefix+'cloud')
        cloud.LegacyProvisioning = type('LegacyProvisioning', (), {})
        sys.modules[prefix+'cloud'] = cloud
    if prefix+'crypto' not in sys.modules:
        crypto = types.ModuleType(prefix+'crypto')
        crypto.decode_media = lambda key, data: data
        crypto.shared_key = lambda public, private: bytes(32)
        sys.modules[prefix+'crypto'] = crypto
    if prefix+'errors' not in sys.modules:
        errors = types.ModuleType(prefix+'errors')
        errors.ProtocolError = type('ProtocolError', (Exception,), {})
        errors.TransportError = type('TransportError', (Exception,), {})
        sys.modules[prefix+'errors'] = errors
    if prefix+'miss' not in sys.modules:
        miss = types.ModuleType(prefix+'miss')
        miss.PAN_TILT_OPERATIONS = {'left': 1, 'right': 2, 'up': 3, 'down': 4}
        @dataclass(frozen=True)
        class VideoPacket:
            codec: int
            sequence: int
            flags: int
            timestamp_ms: int
            payload: bytes
        miss.VideoPacket = VideoPacket
        sys.modules[prefix+'miss'] = miss
    return importlib.import_module(prefix+'tutk')


class ProtocolPackets(unittest.TestCase):
    def setUp(self):
        self.mod = load_protocol()

    def test_packet_go2rtc_v1915_reference_vector(self):
        source=bytes((i*13+29)%256 for i in range(24))
        expected=bytes.fromhex('860734caeceddfc77fa649af57a14d3d684d6666925e47ae')
        self.assertEqual(self.mod.encode_packet(source), expected)
        self.assertEqual(self.mod.decode_packet(expected), source)

    def test_obfuscation_roundtrip_all_lengths(self):
        for n in list(range(0,100)) + [118, 512, 598, 1200]:
            source=bytes(i*31 % 256 for i in range(n))
            self.assertEqual(self.mod.decode_packet(self.mod.encode_packet(source)), source, n)

    def test_uid_message_does_not_embed_a_password(self):
        data=self.mod.connect_by_uid('UID_LEGACY_TEST', bytes(range(8)), 1)
        self.assertEqual(len(data), 68)
        self.assertEqual(data[:4], bytes.fromhex('04021902'))
        self.assertEqual(data[8:11], bytes.fromhex('010621'))
        self.assertIn(b'UID_LEGACY_TEST',data)
        self.assertEqual(data[64], 1)
        self.assertNotIn(b'SECRET_PASSWORD',data)
        with self.assertRaises(Exception):
            self.mod.connect_by_uid('X'*37, bytes(range(8)), 1)

    def test_cloud_does_not_store_credentials_in_session_options(self):
        s=(COMP/'protocol/session.py').read_text()
        self.assertIn('experimental_legacy_tutk: bool = False',s)
        self.assertIn('legacy_provision_ipc020',s)
        self.assertNotIn('provision.uid = ',s)
        self.assertNotIn('options = replace(self.options, uid=',s)
        self.assertIn('self.device.model == "chuangmi.camera.ipc020"',s)
        self.assertIn('self.options.experimental_legacy_tutk is True',s)
        self.assertNotIn('go2rtc',s)

    def test_options_exposed_only_on_ipc020(self):
        f=(COMP/'config_flow.py').read_text()
        self.assertIn('if device["model"] == "chuangmi.camera.ipc020":',f)
        self.assertIn('"experimental_legacy_tutk", default=current["experimental_legacy_tutk"]',f)
        model_script=(COMP/'protocol/miss.py').read_text()
        self.assertIn('EXPERIMENTAL_PAN_TILT_MODELS = frozenset({"chuangmi.camera.ipc020"})',model_script)

    def test_diagnostics_only_safe_stage_values(self):
        for filename in ('camera.py','diagnostics.py'):
            text=(COMP/filename).read_text()
            for field in ('ipc020_tutk_stage','ipc020_tutk_auth_mode',
                          'ipc020_tutk_sdk','ipc020_tutk_video_packets',
                          'ipc020_tutk_last_control','ipc020_tutk_media_results'):
                self.assertIn(field,text)
            self.assertNotIn('provision.uid',text)
            self.assertNotIn('provision.password',text)
            self.assertNotIn('provision.private',text)


class CloudCredentials(unittest.IsolatedAsyncioTestCase):
    def _extract(self):
        tree=ast.parse((COMP/'protocol/cloud.py').read_text())
        cloud_cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='XiaomiCloud')
        method=next(n for n in cloud_cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='legacy_provision_ipc020')
        @dataclass(repr=False)
        class LegacyProvisioning:
            uid:str;auth_mode:str;password:str='';public:bytes=b'';private:bytes=b'';device_public:bytes=b'';sign:str=''
        class ProtocolError(Exception): pass
        class CloudError(Exception): pass
        ns={"LegacyProvisioning":LegacyProvisioning,"ProtocolError":ProtocolError,
            "generate_keypair":lambda:(b'\x01'*32,b'\x02'*32)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])), 'legacy', 'exec'),ns)
        return ns['legacy_provision_ipc020'],ProtocolError

    async def test_signed_key_fields(self):
        provision,err=self._extract()
        class Client:
            async def request(self,path,params,*,retry):
                self.path=path;self.params=params;self.retry=retry
                return {'p2p_id':'TEST_UID','signForAppData':'SECRET_SIG',
                        'p2p_dev_public_key':'03'*32}
        client=Client()
        result=await provision(client,SimpleNamespace(did='5',model='chuangmi.camera.ipc020'))
        self.assertEqual(result.auth_mode,'signed')
        self.assertEqual(result.uid,'TEST_UID')
        self.assertEqual(result.device_public,b'\x03'*32)
        self.assertEqual(client.path,'/device/devicepass')
        self.assertEqual(client.params,{'did':'5','toSignAppData':'01'*32})
        self.assertIs(client.retry,True)
        self.assertNotIn('SECRET',repr(result))

    async def test_password_fallback_and_non_matching_model(self):
        provision,Error=self._extract()
        class Client:
            async def request(self,*args,**kwargs):
                return {'p2p_id':'TEST_UID','password':'SECRET_PASSWORD'}
        result=await provision(Client(),SimpleNamespace(model='chuangmi.camera.ipc020',did='5'))
        self.assertEqual(result.auth_mode,'password')
        self.assertEqual(result.password,'SECRET_PASSWORD')
        with self.assertRaises(Error):
            await provision(Client(),SimpleNamespace(model='chuangmi.camera.ip029a',did='5'))

    async def test_invalid_credentials_do_not_embed_secrets_in_errors(self):
        provision,Error=self._extract()
        for response in ({'p2p_id':'UID','signForAppData':'SIG','p2p_dev_public_key':'INVALID_KEY'},
                         {'p2p_id':'UID','password':''},{'p2p_id':'U'*40,'password':'PASS'}):
            class Client:
                async def request(self,*a,**kw):return response
            with self.assertRaises(Error) as caught:
                await provision(Client(),SimpleNamespace(model='chuangmi.camera.ipc020',did='5'))
            self.assertNotIn('UID',str(caught.exception))
            self.assertNotIn('INVALID_KEY',str(caught.exception))


class TutkSession(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tutk=load_protocol()
        self.provision=SimpleNamespace(uid='TEST_UID',password='SECRET_PASSWORD',auth_mode='password',sign='',public=b'',private=b'',device_public=b'')

    async def test_media_start_sends_a1_sequence(self):
        client=self.tutk.TutkClient('192.0.2.10',self.provision,None)
        client._send_control=AsyncMock()
        await client.start_media('hd')
        self.assertTrue(client._started)
        self.assertEqual(client.status.stage,'waiting_for_video')
        self.assertEqual(client.status.media_results,'audio:ack,video:ack,quality:ack')
        self.assertEqual([x.args[0] for x in client._send_control.await_args_list], [0x300,0x1FF,0x320])
        self.assertEqual(json.loads(client._send_control.await_args_list[2].args[1]),{'videoquality':3})

    async def test_ptz_requires_first_video_frame(self):
        client=self.tutk.TutkClient('192.0.2.10',self.provision,None)
        client._send_control=AsyncMock()
        with self.assertRaises(self.tutk.ProtocolError):
            await client.pan_tilt('left')
        client._read_task = SimpleNamespace(done=lambda: False)
        client._started=True
        with self.assertRaises(self.tutk.ProtocolError):
            await client.pan_tilt('left')
        client.status.video_packets=1
        await client.pan_tilt('left')
        client._send_control.assert_awaited_once_with(0xF005,b'{"operation":1}',motor=True)
        self.assertEqual(client.status.last_control,'transport_ack_only')
        client._read_task = SimpleNamespace(done=lambda: True)
        with self.assertRaises(self.tutk.ProtocolError):
            await client.pan_tilt('left')
        self.assertEqual(client._send_control.await_count, 1)

    async def test_udp_port_changes_only_during_matching_handshake(self):
        loop = asyncio.get_running_loop()
        client = self.tutk.TutkClient('127.0.0.1', self.provision, None)
        with (
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as viewer,
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as discovery,
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as camera,
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as stray,
        ):
            for sock in (viewer, discovery, camera, stray):
                sock.setblocking(False)
                sock.bind(('127.0.0.1', 0))
            client._sock = viewer
            client._peer = discovery.getsockname()
            request = b'\x04\x02' + bytes(14)
            unrelated_packet = request + b'wrong port'
            reply = request + b'reply'

            async def handshake_peer():
                _, addr = await loop.sock_recvfrom(discovery, 2048)
                await loop.sock_sendto(stray, self.tutk.encode_packet(unrelated_packet), addr)
                _, addr = await loop.sock_recvfrom(discovery, 2048)
                await loop.sock_sendto(camera, self.tutk.encode_packet(reply), addr)

            with patch.object(self.tutk, '_SESSION_TIMEOUT', 0.9):
                async with asyncio.timeout(2):
                    async with asyncio.TaskGroup() as tasks:
                        tasks.create_task(handshake_peer())
                        self.assertEqual(await client._exchange(lambda data: data == reply, request), reply)
            self.assertEqual(client._peer, camera.getsockname())

            await loop.sock_sendto(stray, self.tutk.encode_packet(unrelated_packet), viewer.getsockname())
            await loop.sock_sendto(camera, self.tutk.encode_packet(reply), viewer.getsockname())
            self.assertEqual(await client._recv(1), (reply, camera.getsockname()))
            await client._send(request)
            raw, _ = await asyncio.wait_for(loop.sock_recvfrom(camera, 2048), 1)
            self.assertEqual(self.tutk.decode_packet(raw), request)

    async def test_read_video_accepts_annexb_and_skips_audio(self):
        client=self.tutk.TutkClient('192.0.2.10',self.provision,None)
        client._media.put_nowait((b'\x8a'+b'\x00'*31, b'abc'))
        client._media.put_nowait((b'\x4e'+b'\x00'*31, b'\x00\x00\x00\x01\x67hello'))
        got=await client.read_video(.1)
        self.assertEqual(got.codec,4)
        self.assertEqual(client.status.video_packets,1)
        self.assertEqual(client.status.stage,'receiving_video')

    async def test_video_timeout_has_safe_stage(self):
        client=self.tutk.TutkClient('192.0.2.10',self.provision,None)
        with self.assertRaises(self.tutk.TransportError):
            await client.read_video(.01)
        self.assertEqual(client.status.stage,'no_video_frames')


if __name__=='__main__':
    unittest.main()
