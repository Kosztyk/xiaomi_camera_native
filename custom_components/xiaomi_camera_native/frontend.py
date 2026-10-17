"""Load the camera pop-up controls without dashboard configuration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION

DATA_FRONTEND = f"{DOMAIN}_frontend"
FRONTEND_PATH = f"/{DOMAIN}/frontend"
FRONTEND_URL = f"{FRONTEND_PATH}/camera-controls.js?v={VERSION}"


@dataclass
class FrontendRegistration:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    registered: bool = False


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register once per HA process, also when accounts load concurrently."""
    state = hass.data.setdefault(DATA_FRONTEND, FrontendRegistration())
    async with state.lock:
        if state.registered:
            return
        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_PATH, str(Path(__file__).parent / "frontend"), False)]
        )
        frontend.add_extra_js_url(hass, FRONTEND_URL)
        state.registered = True
