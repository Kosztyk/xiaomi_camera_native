"""Direct Xiaomi MISS/CS2 cameras, with no go2rtc runtime dependency."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from aiohttp import DummyCookieJar
from homeassistant.components.ffmpeg import get_ffmpeg_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_DEVICES, CONF_PROFILES, CONF_REGION
from .frontend import async_register_frontend
from .protocol.address import CameraAddressResolver, router_addresses
from .protocol.cloud import CameraDevice, XiaomiCloud
from .protocol.errors import AuthenticationError, CloudError
from .protocol.session import CameraSession, LoopbackServer, StreamOptions

PLATFORMS = [Platform.CAMERA, Platform.BUTTON]


@dataclass
class RuntimeData:
    cloud: XiaomiCloud
    server: LoopbackServer
    sessions: dict[str, CameraSession]
    entry_data: dict[str, Any]
    entry_options: dict[str, Any]


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
    known_data = deepcopy(dict(entry.data))
    known_options = deepcopy(dict(entry.options))
    resolver = CameraAddressResolver(
        cloud, lambda device: router_addresses(device, hass.states.async_all("device_tracker"))
    )

    def save_rotated_credentials() -> None:
        credentials = cloud.credentials.persistent()
        if any(entry.data.get(key) != value for key, value in credentials.items()):
            known_data.update(credentials)
            hass.config_entries.async_update_entry(entry, data={**entry.data, **credentials})

    def save_camera_address(device: CameraDevice, host: str) -> None:
        # If a user changed configuration while connect() was awaiting I/O,
        # let its pending reload win. Never absorb that edit into our baseline.
        if entry.data != known_data or entry.options != known_options:
            return
        data = deepcopy(known_data)
        options = deepcopy(known_options)
        for raw in data[CONF_DEVICES]:
            if raw["did"] == device.did:
                raw["host"] = host
        profile = options.get(CONF_PROFILES, {}).get(device.did, {})
        if "host" in profile:
            profile["host"] = host
        known_data.clear()
        known_data.update(data)
        known_options.clear()
        known_options.update(options)
        hass.config_entries.async_update_entry(entry, data=data, options=options)

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
        options = StreamOptions.from_profile(profile)
        sessions[device.did] = CameraSession(
            cloud,
            device,
            options,
            get_ffmpeg_manager(hass).binary,
            on_state=save_rotated_credentials,
            on_auth_error=request_reauth,
            address_resolver=resolver,
            on_address_changed=save_camera_address,
        )
    server = LoopbackServer(sessions)
    try:
        await server.start()
        await async_register_frontend(hass)
        entry.runtime_data = RuntimeData(cloud, server, sessions, known_data, known_options)
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
    # Internal IP/credential saves must not tear down a newly recovered stream.
    # Real profile edits and rediscovery still reload the integration.
    runtime = entry.runtime_data
    if entry.data == runtime.entry_data and entry.options == runtime.entry_options:
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.server.close()
        return True
    return False
