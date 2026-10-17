"""Home Assistant camera entities backed by the direct protocol client."""

from __future__ import annotations

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.ffmpeg import async_get_image
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TARGET_MODELS
from .protocol.session import CameraSession, LoopbackServer


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        NativeXiaomiCamera(session, runtime.server) for session in runtime.sessions.values()
    )


class NativeXiaomiCamera(Camera):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_brand = "Xiaomi"
    _attr_should_poll = False

    def __init__(self, session: CameraSession, server: LoopbackServer) -> None:
        super().__init__()
        self._session = session
        self._server = server
        self._attr_unique_id = session.device.did
        self._attr_model = TARGET_MODELS.get(session.device.model, session.device.model)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, session.device.did)},
            name=session.device.name,
            manufacturer="Xiaomi",
            model=self._attr_model,
        )
        # Home Assistant accepts a small set of stream options, not arbitrary
        # libavformat flags. MPEG-TS works with the built-in defaults.
        self.stream_options = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        previous = self._session.on_state

        def changed() -> None:
            previous()
            self.async_write_ha_state()

        self._session.on_state = changed
        self.async_on_remove(lambda: setattr(self._session, "on_state", previous))

    @property
    def is_streaming(self) -> bool:
        return self._session.status == "streaming"

    @property
    def extra_state_attributes(self) -> dict:
        session = self._session
        attributes = {
            "connection_status": session.status,
            "transport": session.protocol,
            "source_codec": session.codec,
            "video_mode": session.options.video_mode,
            "frames_received": session.frames,
            "reconnects": session.reconnects,
            "last_error": session.last_error,
            "pan_tilt_supported": session.supports_pan_tilt,
            "last_ptz_error": session.last_ptz_error,
        }
        if session.supports_pan_tilt and getattr(self, "hass", None) is not None:
            registry = er.async_get(self.hass)
            buttons = {}
            for direction in ("left", "right", "up", "down"):
                entity_id = registry.async_get_entity_id(
                    "button", DOMAIN, f"{session.device.did}_ptz_{direction}"
                )
                entry = registry.async_get(entity_id) if entity_id else None
                if entry is not None and entry.disabled_by is None:
                    buttons[direction] = entity_id
            if buttons:
                # Resolve through the registry so renamed buttons keep working.
                attributes["xiaomi_pan_tilt_buttons"] = buttons
        return attributes

    async def stream_source(self) -> str:
        # The stream URL is local to HA, not a go2rtc or Xiaomi cloud URL.
        return self._server.source(self._session.device.did)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        # Reuses the shared MISS session; it does not log in a second time.
        return await async_get_image(
            self.hass, await self.stream_source(), width=width, height=height
        )
