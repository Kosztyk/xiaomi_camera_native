"""Single-step pan and tilt controls for Xiaomi cameras."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TARGET_MODELS
from .protocol.errors import AuthenticationError, XiaomiError
from .protocol.session import CameraSession

BUTTONS = (
    ButtonEntityDescription(key="left", translation_key="pan_left", icon="mdi:arrow-left"),
    ButtonEntityDescription(key="right", translation_key="pan_right", icon="mdi:arrow-right"),
    ButtonEntityDescription(key="up", translation_key="tilt_up", icon="mdi:arrow-up"),
    ButtonEntityDescription(key="down", translation_key="tilt_down", icon="mdi:arrow-down"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        XiaomiPanTiltButton(session, description)
        for session in entry.runtime_data.sessions.values()
        if session.supports_pan_tilt
        for description in BUTTONS
    )


class XiaomiPanTiltButton(ButtonEntity):
    """One native motor step, with no additional video stream."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, session: CameraSession, description: ButtonEntityDescription) -> None:
        self.entity_description = description
        self._session = session
        device = session.device
        self._attr_unique_id = f"{device.did}_ptz_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.did)},
            name=device.name,
            manufacturer="Xiaomi",
            model=TARGET_MODELS.get(device.model, device.model),
        )

    async def async_press(self) -> None:
        try:
            await self._session.pan_tilt(self.entity_description.key)
        except AuthenticationError:
            raise HomeAssistantError(
                "Xiaomi authentication expired; reauthenticate Xiaomi Camera Native"
            ) from None
        except XiaomiError as err:
            raise HomeAssistantError(str(err)) from None
