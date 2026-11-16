"""Offline regression tests for ipc020 address, account, and pan recovery."""

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
import json
import logging
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from test_ipc020_horizontal_only import IPC020, isolated_code
from test_ipc020_tutk_transport import load_protocol


class LegacyProvisioning(SimpleNamespace):
    pass


@dataclass(frozen=True)
class Options:
    host: str = "192.0.2.11"
    auto_update_ip: bool = True
    experimental_legacy_tutk: bool = True
    experimental_pan_tilt: bool = True
    quality: str = "hd"


class CameraRecoveryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tutk = load_protocol()
        self.Session = isolated_code(
            "protocol/session.py", "CameraSession",
            ("__init__", "_uses_legacy_tutk", "supported_pan_tilt_directions",
             "supports_pan_tilt", "pan_tilt_ready", "_address_candidates",
             "_tutk_status", "_provision_camera", "_connect_client", "pan_tilt"),
            {
                "asyncio": asyncio,
                "H264StartupCache": lambda: None,
                "ENCODER_QUEUE_SIZE": 1,
                "LegacyProvisioning": LegacyProvisioning,
                "TutkClient": self.tutk.TutkClient,
                "ProtocolError": self.tutk.ProtocolError,
                "TransportError": self.tutk.TransportError,
                "PAN_TILT_OPERATIONS": self.tutk.PAN_TILT_OPERATIONS,
                "PAN_TILT_TIMEOUT": 5,
                "XiaomiError": Exception,
                "AuthenticationError": AuthenticationError,
                "replace": replace,
                "_LOGGER": logging.getLogger(__name__),
            },
        )
        self.device = SimpleNamespace(did="fixture", model=IPC020, host="192.0.2.11")
        self.credentials = LegacyProvisioning(uid="FIXTURE", auth_mode="password")
        self.cloud = SimpleNamespace(
            legacy_provision_ipc020=AsyncMock(return_value=self.credentials),
            provision=AsyncMock(),
        )
        self.resolver = SimpleNamespace(
            local_addresses=Mock(return_value=["192.0.2.12"]),
            cloud_address=AsyncMock(return_value="192.0.2.13"),
        )
        self.save_address = Mock()
        self.session = self.Session(
            self.cloud, self.device, Options(), address_resolver=self.resolver,
            on_address_changed=self.save_address,
        )
        self.client = self.tutk.TutkClient("192.0.2.13", self.credentials, None)

    async def test_recovers_from_stale_address_and_persists_verified_candidate(self):
        async def dial(host, *_args, **_kwargs):
            if host == "192.0.2.13":
                return self.client
            raise self.tutk.TransportError("unreachable")

        with patch.object(self.tutk.TutkClient, "connect", new=AsyncMock(side_effect=dial)) as connect:
            self.assertIs(await self.session._connect_client(start_video=True), self.client)
            self.assertEqual(
                [attempt.args[0] for attempt in connect.await_args_list],
                ["192.0.2.11", "192.0.2.12", "192.0.2.13"],
            )
        self.save_address.assert_called_once_with(self.device, "192.0.2.13")
        self.assertEqual(self.session.host, "192.0.2.13")
        self.assertEqual(self.session.options.host, "192.0.2.13")
        self.assertEqual(self.session.address_source, "xiaomi_cloud")
        self.assertEqual(self.session.address_updates, 1)
        self.assertEqual(self.cloud.legacy_provision_ipc020.await_count, 3)
        self.cloud.provision.assert_not_awaited()

    async def test_static_camera_address_is_respected(self):
        self.session.options = replace(self.session.options, auto_update_ip=False)
        with patch.object(
            self.tutk.TutkClient, "connect",
            new=AsyncMock(side_effect=self.tutk.TransportError("unreachable")),
        ) as connect:
            with self.assertRaises(self.tutk.TransportError):
                await self.session._connect_client(start_video=True)
            connect.assert_awaited_once()
            self.assertEqual(connect.await_args.args[0], "192.0.2.11")
        self.resolver.local_addresses.assert_not_called()
        self.resolver.cloud_address.assert_not_awaited()
        self.save_address.assert_not_called()

    async def test_previously_streamed_camera_cannot_pan_after_idle(self):
        self.session.frames = 1
        with self.assertRaisesRegex(self.tutk.ProtocolError, "Open the live view"):
            await self.session.pan_tilt("left")
        self.assertFalse(self.session.pan_tilt_ready)
        self.cloud.legacy_provision_ipc020.assert_not_awaited()

    async def test_pan_rechecks_video_readiness_after_acquiring_lock(self):
        self.client._started = True
        self.client.status.video_packets = 1
        self.client._read_task = SimpleNamespace(done=lambda: False)
        self.session._client = self.client
        self.session.status = "streaming"
        self.assertTrue(self.session.pan_tilt_ready)
        async with self.session._connection_lock:
            press = asyncio.create_task(self.session.pan_tilt("left"))
            await asyncio.sleep(0)
            self.assertTrue(self.session._ptz_busy)
            # The connection closed after the button press began waiting.
            self.session._client = None
        with self.assertRaisesRegex(self.tutk.TransportError, "Open the live view"):
            await press
        self.assertFalse(self.session._ptz_busy)
        self.cloud.legacy_provision_ipc020.assert_not_awaited()


class AuthenticationError(Exception):
    pass


class CloudError(Exception):
    pass


@dataclass
class Credentials:
    user_id: str = ""
    pass_token: str = ""
    service_token: str = ""
    security: bytes = b""
    c_user_id: str = ""


class TokenRefreshTests(unittest.IsolatedAsyncioTestCase):
    def make_cloud(self, post, login):
        cloud_type = isolated_code(
            "protocol/cloud.py", "XiaomiCloud",
            ("__init__", "base_url", "request", "legacy_provision_ipc020"),
            {
                "asyncio": asyncio, "base64": base64, "json": json,
                "Credentials": Credentials, "REGIONS": {"cn"}, "TIMEOUT": None,
                "AuthenticationError": AuthenticationError, "CloudError": CloudError,
                "aiohttp": SimpleNamespace(ClientError=OSError),
                "encrypt_cloud_request": lambda *_: ({}, None),
                "rc4_drop1024": lambda _key, payload: payload,
                "generate_keypair": lambda: (bytes(32), bytes(32)),
                "LegacyProvisioning": LegacyProvisioning,
            },
        )
        cloud_type.request.__globals__["XiaomiCloud"] = cloud_type
        cloud_type.login_with_token = login
        cloud = cloud_type(SimpleNamespace(post=post), "cn")
        cloud.credentials = Credentials("fixture", "pass", "expired")
        return cloud

    async def test_parallel_provisioning_refreshes_expired_token_once(self):
        sent = []
        both_requests_sent = asyncio.Event()
        refreshes = []

        @asynccontextmanager
        async def post(url, *, cookies, **_kwargs):
            self.assertTrue(url.endswith("/device/devicepass"))
            token = cookies["serviceToken"]
            sent.append(token)
            if token == "expired":
                if sent.count("expired") == 2:
                    both_requests_sent.set()
                await both_requests_sent.wait()
                yield SimpleNamespace(status=401)
            else:
                body = b'{"code":0,"result":{"p2p_id":"fixture","password":"fixture"}}'
                yield SimpleNamespace(status=200, read=AsyncMock(return_value=body))

        async def refresh(client, user_id, pass_token):
            refreshes.append((user_id, pass_token))
            client.credentials = Credentials(user_id, pass_token, "renewed")

        cloud = self.make_cloud(post, refresh)
        device = SimpleNamespace(model=IPC020, did="fixture")
        async with asyncio.timeout(2):
            credentials = await asyncio.gather(
                cloud.legacy_provision_ipc020(device),
                cloud.legacy_provision_ipc020(device),
            )
        self.assertEqual(refreshes, [("fixture", "pass")])
        self.assertEqual(sent, ["expired", "expired", "renewed", "renewed"])
        self.assertEqual([item.auth_mode for item in credentials], ["password", "password"])

    async def test_refresh_failure_preserves_the_current_account_record(self):
        @asynccontextmanager
        async def post(*_args, **_kwargs):
            yield SimpleNamespace(status=401)

        async def failed_refresh(client, user_id, pass_token):
            client.credentials = Credentials(user_id, pass_token)
            raise CloudError("temporary login failure")

        cloud = self.make_cloud(post, failed_refresh)
        active = cloud.credentials
        with self.assertRaises(CloudError):
            await cloud.legacy_provision_ipc020(SimpleNamespace(model=IPC020, did="fixture"))
        self.assertIs(cloud.credentials, active)

    async def test_authenticated_post_rejects_redirect(self):
        @asynccontextmanager
        async def post(_url, *, allow_redirects=True, **_kwargs):
            self.assertFalse(allow_redirects)
            yield SimpleNamespace(status=307, headers={"Location": "https://example.invalid/"})

        cloud = self.make_cloud(post, AsyncMock())
        with self.assertRaisesRegex(CloudError, "HTTP error 307"):
            await cloud.request("/device/devicepass", {"did": "fixture"})
        cloud.login_with_token.assert_not_awaited()
