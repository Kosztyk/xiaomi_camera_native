"""Useful diagnostics with no account credentials or media endpoint tokens."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import VERSION


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict:
    runtime = entry.runtime_data
    return {
        "version": VERSION,
        "region": entry.data["region"],
        "cameras": [
            {
                "model": session.device.model,
                "status": session.status,
                "transport": session.protocol,
                "source_codec": session.codec,
                "video_mode": session.options.video_mode,
                "quality": session.options.quality,
                "frames": session.frames,
                "reconnects": session.reconnects,
                "last_error": session.last_error,
                "pan_tilt_supported": session.supports_pan_tilt,
                "last_ptz_error": session.last_ptz_error,
            }
            for session in runtime.sessions.values()
        ],
    }
