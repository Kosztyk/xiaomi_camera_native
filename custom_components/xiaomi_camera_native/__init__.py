"""Direct Xiaomi MISS/CS2 cameras, with no go2rtc runtime dependency."""

from __future__ import annotations

from dataclasses import dataclass

from aiohttp import DummyCookieJar
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_DEVICES, CONF_PROFILES, CONF_REGION
from .frontend import async_register_frontend
from .protocol.cloud import CameraDevice, XiaomiCloud
from .protocol.errors import AuthenticationError, CloudError
from .protocol.session import CameraSession, LoopbackServer, StreamOptions

PLATFORMS = [Platform.CAMERA, Platform.BUTTON]


@dataclass
class RuntimeData:
    cloud: XiaomiCloud
    server: LoopbackServer
    sessions: dict[str, CameraSession]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # Xiaomi account cookies must never mix with another integration/account.
    http = async_create_clientsession(hass, cookie_jar=DummyCookieJar())
    cloud = XiaomiCloud(http, entry.data[CONF_REGION])
    try:
        await cloud.authenticate(entry.data)
    except AuthenticationError as err:
        http.detach()
        raise ConfigEntryAuthFailed(str(err)) from None
    except CloudError as err:
        http.detach()
        raise ConfigEntryNotReady(str(err)) from None

    sessions: dict[str, CameraSession] = {}
    auth_requested = False

    def save_rotated_credentials() -> None:
        credentials = cloud.credentials.persistent()
        if any(entry.data.get(key) != value for key, value in credentials.items()):
            hass.config_entries.async_update_entry(entry, data={**entry.data, **credentials})

    def request_reauth() -> None:
        nonlocal auth_requested
        if not auth_requested:
            auth_requested = True
            entry.async_start_reauth(hass)

    save_rotated_credentials()
    profiles = entry.options.get(CONF_PROFILES, {})
    for raw in entry.data[CONF_DEVICES]:
        device = CameraDevice(**raw)
        profile = {
            "quality": "auto" if device.model == "mxiang.camera.c301" else "hd",
            **profiles.get(device.did, {}),
        }
        options = StreamOptions(
            **{
                key: value
                for key, value in profile.items()
                if key in StreamOptions.__dataclass_fields__
            }
        )
        sessions[device.did] = CameraSession(
            cloud,
            device,
            options,
            get_ffmpeg_manager(hass).binary,
            on_state=save_rotated_credentials,
            on_auth_error=request_reauth,
        )
    server = LoopbackServer(sessions)
    try:
        await server.start()
        await async_register_frontend(hass)
        entry.runtime_data = RuntimeData(cloud, server, sessions)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await server.close()
        raise
    entry.async_on_unload(entry.add_update_listener(_options_updated))

    async def shutdown(_event) -> None:
        await server.close()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, shutdown))
    return True


async def _options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.server.close()
        return True
    return False
