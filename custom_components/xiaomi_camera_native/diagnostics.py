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
                "max_h264_height": session.options.height,
                "quality": session.options.quality,
                "frames": session.frames,
                "reconnects": session.reconnects,
                "encoder_restarts": session.encoder_restarts,
                "encoder_dropped_frames": session.encoder_dropped_frames,
                "last_error": session.last_error,
                **(
                    {"ipc020_legacy_probe": session.legacy_probe_status,
                      "ipc020_tutk_test_enabled": session.options.experimental_legacy_tutk,
                      "ipc020_tutk_stage": session.legacy_tutk_stage,
                      "ipc020_tutk_auth_mode": session.legacy_tutk_auth_mode,
                      "ipc020_tutk_sdk": session.legacy_tutk_sdk,
                      "ipc020_tutk_video_packets": session.legacy_tutk_video_packets,
                      "ipc020_tutk_dropped_packets": session.legacy_tutk_dropped_packets,
                      "ipc020_tutk_malformed_packets": session.legacy_tutk_malformed_packets,
                      "ipc020_tutk_last_control": session.legacy_tutk_last_control,
                      "ipc020_tutk_media_results": session.legacy_tutk_media_results,
                      "ipc020_tutk_ptz_command_seq": session.legacy_tutk_ptz_command_seq,
                      "ipc020_tutk_ptz_ack_state": session.legacy_tutk_ptz_ack_state,
                      "ipc020_tutk_ptz_ack_ms": session.legacy_tutk_ptz_ack_ms,
                      "ipc020_tutk_ptz_unmatched_acks": session.legacy_tutk_ptz_unmatched_acks,
                      "ipc020_tutk_ptz_app_responses": session.legacy_tutk_ptz_app_responses,
                      "ipc020_tutk_ptz_last_direction": session.legacy_tutk_ptz_last_direction}
                    if session.device.model == "chuangmi.camera.ipc020"
                    else {}
                ),
                "pan_tilt_supported": session.supports_pan_tilt,
                "pan_tilt_directions": list(session.supported_pan_tilt_directions),
                "pan_tilt_ready": session.pan_tilt_ready,
                "pan_tilt_experimental": session.pan_tilt_experimental,
                "last_ptz_error": session.last_ptz_error,
                "ip_address": session.host,
                "auto_update_ip": session.options.auto_update_ip,
                "address_source": session.address_source,
                "address_updates": session.address_updates,
            }
            for session in runtime.sessions.values()
        ],
    }
