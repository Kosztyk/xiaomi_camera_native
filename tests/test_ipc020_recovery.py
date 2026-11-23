"""Offline regression tests for ipc020 address, account, and pan recovery."""

import asyncio
import base64
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from importlib import import_module
import logging
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from test_ipc020_horizontal_only import COMP, IPC020, isolated_code
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


def load_cloud():
    """Import the complete cloud client with offline dependency stubs."""
    package = ModuleType("_test_xiaomi_cloud")
    package.__path__ = [str(COMP / "protocol")]
    aiohttp = ModuleType("aiohttp")
    aiohttp.ClientTimeout = lambda **kwargs: None
    aiohttp.ClientError = OSError
    crypto = ModuleType(f"{package.__name__}.crypto")
    crypto.b64 = lambda payload: base64.b64encode(payload).decode("ascii")
    crypto.encrypt_cloud_request = lambda *_: ({}, b"")
    crypto.rc4_drop1024 = lambda _key, payload: payload
    crypto.generate_keypair = lambda: (bytes(32), bytes(32))
    with patch.dict(sys.modules, {
        package.__name__: package, aiohttp.__name__: aiohttp, crypto.__name__: crypto,
    }):
        return import_module(f"{package.__name__}.cloud")


class TokenRefreshTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = load_cloud()
        self.credentials = self.module.Credentials(
            user_id="fixture", pass_token="pass", service_token="expired", security=b"initial"
        )
        self.saved = self.credentials.persistent()

    def make_cloud(self, post, login):
        cloud = self.module.XiaomiCloud(SimpleNamespace(post=post), "cn")
        self.module.XiaomiCloud.login_with_token = login
        cloud.credentials = replace(self.credentials)
        return cloud

    def device_list(self, *statuses, headers=None):
        @asynccontextmanager
        async def result(status):
            yield SimpleNamespace(
                status=status,
                headers=headers or {},
                read=AsyncMock(return_value=b'{"code":0,"result":{"list":[]}}'),
            )

        return Mock(side_effect=[result(status) for status in statuses])

    def renew_credentials(self, client, user_id, pass_token):
        client.credentials = self.module.Credentials(
            user_id=user_id, pass_token=pass_token, service_token="renewed", security=b"renewed"
        )

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
            self.renew_credentials(client, user_id, pass_token)

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
            client.credentials = self.module.Credentials(user_id, pass_token)
            raise self.module.CloudError("temporary login failure")

        cloud = self.make_cloud(post, failed_refresh)
        active = cloud.credentials
        with self.assertRaises(self.module.CloudError):
            await cloud.legacy_provision_ipc020(SimpleNamespace(model=IPC020, did="fixture"))
        self.assertIs(cloud.credentials, active)

    async def test_authenticated_post_rejects_redirect(self):
        @asynccontextmanager
        async def post(_url, *, allow_redirects=True, **_kwargs):
            self.assertFalse(allow_redirects)
            yield SimpleNamespace(status=307, headers={"Location": "https://example.invalid/"})

        cloud = self.make_cloud(post, AsyncMock())
        with self.assertRaisesRegex(self.module.CloudError, "HTTP error 307"):
            await cloud.request("/device/devicepass", {"did": "fixture"})
        cloud.login_with_token.assert_not_awaited()

    async def test_426_refresh_verifies_new_session_on_standard_host(self):
        async def refresh(client, user_id, pass_token):
            self.assertEqual((user_id, pass_token), ("fixture", "pass"))
            self.renew_credentials(client, user_id, pass_token)

        post = self.device_list(426, 200)
        cloud = self.make_cloud(post, refresh)
        await cloud.authenticate(self.saved)

        self.assertEqual(cloud.credentials.service_token, "renewed")
        self.assertEqual(
            [call.kwargs["cookies"]["serviceToken"] for call in post.call_args_list],
            ["expired", "renewed"],
        )
        for call in post.call_args_list:
            self.assertEqual(call.args[0], "https://api.io.mi.com/app/v2/home/device_list_page")
            self.assertNotIn("ssecurity", call.kwargs["data"])
            self.assertFalse(call.kwargs["allow_redirects"])

    async def test_426_refresh_retries_after_a_temporary_failure(self):
        attempts = []

        async def refresh(client, user_id, pass_token):
            attempts.append(user_id)
            self.renew_credentials(client, user_id, pass_token)
            if len(attempts) == 1:
                raise self.module.CloudError("Cannot connect to Xiaomi login service")

        with patch.object(self.module, "monotonic", return_value=100.0) as clock:
            initial = self.make_cloud(self.device_list(426), refresh)
            with self.assertRaisesRegex(self.module.CloudError, "Cannot connect"):
                await initial.authenticate(self.saved)
            self.assertEqual(initial.credentials.persistent(), self.saved)

            no_refresh = AsyncMock()
            early_retry = self.make_cloud(self.device_list(426), no_refresh)
            with self.assertRaises(self.module.CloudHTTP426):
                await early_retry.authenticate(self.saved)
            no_refresh.assert_not_awaited()

            clock.return_value += self.module.HTTP426_REFRESH_COOLDOWN
            later_retry = self.make_cloud(self.device_list(426, 200), refresh)
            await later_retry.authenticate(self.saved)

        self.assertEqual(attempts, ["fixture", "fixture"])
        self.assertEqual(later_retry.credentials.service_token, "renewed")

    async def test_426_with_upgrade_header_does_not_refresh(self):
        login = AsyncMock()
        cloud = self.make_cloud(self.device_list(426, headers={"Upgrade": "h2"}), login)
        with self.assertRaisesRegex(self.module.CloudHTTP426, "^Xiaomi cloud HTTP error 426$"):
            await cloud.authenticate(self.saved)
        login.assert_not_awaited()

    async def test_426_verification_failure_keeps_previous_credentials(self):
        async def refresh(client, user_id, pass_token):
            self.renew_credentials(client, user_id, pass_token)

        cloud = self.make_cloud(self.device_list(426, 503), refresh)
        with self.assertRaisesRegex(self.module.CloudError, "HTTP error 503"):
            await cloud.authenticate(self.saved)
        self.assertEqual(cloud.credentials.persistent(), self.saved)

    async def test_426_does_not_start_a_second_refresh_while_one_is_in_flight(self):
        started = asyncio.Event()
        finish = asyncio.Event()
        attempts = []

        async def refresh(client, user_id, pass_token):
            attempts.append(user_id)
            started.set()
            await finish.wait()
            self.renew_credentials(client, user_id, pass_token)

        with patch.object(self.module, "monotonic", return_value=100.0) as clock:
            first = self.make_cloud(self.device_list(426, 200), refresh)
            second = self.make_cloud(self.device_list(426), refresh)
            async with asyncio.timeout(2), asyncio.TaskGroup() as group:
                group.create_task(first.authenticate(self.saved))
                await started.wait()
                clock.return_value += 2 * self.module.HTTP426_REFRESH_COOLDOWN
                with self.assertRaises(self.module.CloudHTTP426):
                    await second.authenticate(self.saved)
                finish.set()
        self.assertEqual(attempts, ["fixture"])
