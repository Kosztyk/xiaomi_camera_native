"""Interactive Xiaomi login and per-camera configuration."""

from __future__ import annotations

import ipaddress
from dataclasses import asdict
from typing import Any

import voluptuous as vol
from aiohttp import DummyCookieJar
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_DEVICES, CONF_PASS_TOKEN, CONF_PROFILES, CONF_REGION, CONF_USER_ID, DOMAIN
from .protocol.cloud import REGIONS, CameraDevice, XiaomiCloud
from .protocol.errors import AuthenticationError, CloudError, LoginChallenge
from .protocol.session import StreamOptions


def _password() -> selector.TextSelector:
    return selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )


def _choices(devices: list[CameraDevice]) -> dict[str, str]:
    return {device.did: f"{device.name} — {device.model}" for device in devices}


class XiaomiCameraConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._cloud: XiaomiCloud | None = None
        self._devices: list[CameraDevice] = []
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._challenge: LoginChallenge | None = None
        self._region = "de"

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(step_id="user", menu_options=["login", "token"])

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        self._reauth_entry = self._get_reauth_entry()
        self._region = entry_data[CONF_REGION]
        return await self.async_step_user()

    def _client(self, region: str) -> XiaomiCloud:
        if self._cloud is None or region != self._region:
            if self._cloud is not None:
                self._cloud.session.detach()
            self._cloud = XiaomiCloud(
                async_create_clientsession(self.hass, cookie_jar=DummyCookieJar()), region
            )
        self._region = region
        return self._cloud

    async def async_step_login(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                await self._client(user_input[CONF_REGION]).login(
                    user_input["username"], user_input["password"]
                )
                return await self._authenticated()
            except LoginChallenge as challenge:
                self._challenge = challenge
                return await self._challenge_step()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CloudError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="login",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("username"): str,
                    vol.Required("password"): _password(),
                    vol.Required(CONF_REGION, default=self._region): vol.In(REGIONS),
                }
            ),
        )

    async def async_step_token(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                await self._client(user_input[CONF_REGION]).login_with_token(
                    user_input[CONF_USER_ID], user_input[CONF_PASS_TOKEN]
                )
                return await self._authenticated()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CloudError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="token",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USER_ID): str,
                    vol.Required(CONF_PASS_TOKEN): _password(),
                    vol.Required(CONF_REGION, default=self._region): vol.In(REGIONS),
                }
            ),
        )

    async def _challenge_step(self):
        if self._challenge is not None and self._challenge.kind == "captcha":
            return await self.async_step_captcha()
        return await self.async_step_verification()

    async def async_step_captcha(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                assert self._cloud is not None
                await self._cloud.submit_captcha(user_input["captcha"])
                return await self._authenticated()
            except LoginChallenge as challenge:
                self._challenge = challenge
                if challenge.kind != "captcha":
                    return await self._challenge_step()
                errors["base"] = "invalid_captcha"
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CloudError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="captcha",
            errors=errors,
            description_placeholders={
                "captcha_image": self._challenge.image if self._challenge else ""
            },
            data_schema=vol.Schema({vol.Required("captcha"): str}),
        )

    async def async_step_verification(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            try:
                assert self._cloud is not None
                await self._cloud.submit_verification(user_input["code"])
                return await self._authenticated()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except CloudError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="verification",
            errors=errors,
            description_placeholders={
                "destination": self._challenge.destination if self._challenge else "your account"
            },
            data_schema=vol.Schema({vol.Required("code"): str}),
        )

    async def _authenticated(self):
        assert self._cloud is not None
        credentials = self._cloud.credentials.persistent()
        unique_id = f"{credentials[CONF_USER_ID]}:{self._region}"
        if self._reauth_entry is not None:
            if self._reauth_entry.unique_id != unique_id:
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(self._reauth_entry, data_updates=credentials)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        try:
            self._devices = await self._cloud.devices()
        except (CloudError, AuthenticationError):
            return self.async_abort(reason="discovery_failed")
        if not self._devices:
            return self.async_abort(reason="no_cameras")
        return await self.async_step_cameras()

    async def async_step_cameras(self, user_input: dict[str, Any] | None = None):
        errors = {}
        if user_input is not None:
            selected = set(user_input.get("cameras", []))
            devices = [asdict(device) for device in self._devices if device.did in selected]
            if devices:
                assert self._cloud is not None
                return self.async_create_entry(
                    title=f"Xiaomi cameras ({self._region})",
                    data={
                        **self._cloud.credentials.persistent(),
                        CONF_REGION: self._region,
                        CONF_DEVICES: devices,
                    },
                )
            errors["base"] = "select_camera"
        return self.async_show_form(
            step_id="cameras",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "cameras", default=[device.did for device in self._devices]
                    ): cv.multi_select(_choices(self._devices)),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return XiaomiCameraOptionsFlow()


class XiaomiCameraOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._did = ""
        self._discovered: list[CameraDevice] = []
        self._credentials: dict[str, str] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        return self.async_show_menu(step_id="init", menu_options=["camera", "rediscover"])

    async def async_step_camera(self, user_input: dict[str, Any] | None = None):
        devices = [CameraDevice(**raw) for raw in self.config_entry.data[CONF_DEVICES]]
        if user_input is not None:
            self._did = user_input["camera"]
            return await self.async_step_profile()
        return self.async_show_form(
            step_id="camera",
            data_schema=vol.Schema(
                {
                    vol.Required("camera"): vol.In(_choices(devices)),
                }
            ),
        )

    async def async_step_profile(self, user_input: dict[str, Any] | None = None):
        device = next(
            raw for raw in self.config_entry.data[CONF_DEVICES] if raw["did"] == self._did
        )
        profiles = self.config_entry.options.get(CONF_PROFILES, {})
        current = {
            **asdict(StreamOptions()),
            "host": device["host"],
            "quality": "auto" if device["model"] == "mxiang.camera.c301" else "hd",
            **profiles.get(self._did, {}),
        }
        errors = {}
        if user_input is not None:
            try:
                address = ipaddress.IPv4Address(user_input["host"])
                if address.is_unspecified or address.is_multicast or int(address) == 0xFFFFFFFF:
                    raise ValueError
            except ValueError:
                errors["host"] = "invalid_host"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        **self.config_entry.options,
                        CONF_PROFILES: {**profiles, self._did: user_input},
                    },
                )
        return self.async_show_form(
            step_id="profile",
            errors=errors,
            description_placeholders={"camera": device["name"]},
            data_schema=vol.Schema(
                {
                    vol.Required("host", default=current["host"]): str,
                    vol.Required("transport", default=current["transport"]): vol.In(
                        {"auto": "Automatic", "udp": "UDP", "tcp": "TCP"}
                    ),
                    vol.Required("quality", default=current["quality"]): vol.In(
                        {
                            "hd": "HD (model default)",
                            "sd": "SD",
                            "auto": "Automatic",
                            "2": "Quality 2",
                            "3": "Quality 3",
                            "4": "Quality 4",
                            "5": "Quality 5",
                        }
                    ),
                    vol.Required("video_mode", default=current["video_mode"]): vol.In(
                        {"h264": "H.264 (FFmpeg)", "original": "Original (no transcoding)"}
                    ),
                    vol.Required("height", default=current["height"]): vol.In(
                        {360: "360p", 720: "720p", 1080: "1080p", 2160: "2160p"}
                    ),
                    vol.Required("idle_timeout", default=current["idle_timeout"]): vol.All(
                        vol.Coerce(int), vol.Range(min=10, max=300)
                    ),
                }
            ),
        )

    async def async_step_rediscover(self, user_input: dict[str, Any] | None = None):
        if not self._discovered:
            cloud = XiaomiCloud(
                async_create_clientsession(self.hass, cookie_jar=DummyCookieJar()),
                self.config_entry.data[CONF_REGION],
            )
            try:
                await cloud.authenticate(self.config_entry.data)
                self._discovered = await cloud.devices()
                self._credentials = cloud.credentials.persistent()
            except AuthenticationError:
                return self.async_abort(reason="reauth_required")
            except CloudError:
                return self.async_abort(reason="discovery_failed")
            finally:
                cloud.session.detach()
        errors = {}
        if user_input is not None:
            selected = set(user_input.get("cameras", []))
            devices = [asdict(device) for device in self._discovered if device.did in selected]
            if devices:
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **self.config_entry.data,
                        **self._credentials,
                        CONF_DEVICES: devices,
                    },
                )
                # A changed options value ensures the update listener reloads.
                return self.async_create_entry(
                    title="",
                    data={
                        **self.config_entry.options,
                        "discovery_revision": self.config_entry.options.get("discovery_revision", 0)
                        + 1,
                    },
                )
            errors["base"] = "select_camera"
        known = {raw["did"] for raw in self.config_entry.data[CONF_DEVICES]}
        return self.async_show_form(
            step_id="rediscover",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "cameras",
                        default=[device.did for device in self._discovered if device.did in known],
                    ): cv.multi_select(_choices(self._discovered)),
                }
            ),
        )
