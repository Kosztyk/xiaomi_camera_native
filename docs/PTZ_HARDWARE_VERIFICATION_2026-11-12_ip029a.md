# Xiaomi Smart Camera PTZ Version 2K (`chuangmi.camera.ip029a`) — user hardware report, 2026-11-12

**Evidence type:** Owner-reported physical PTZ movement, **not independently reviewed video or camera telemetry**. This report is based on the user's direct test feedback, not an automated or simulated result. One camera was used to verify movement; a second camera of the same model was reported to stream successfully but **its PTZ was not tested**.

## Environment

- Camera: Chinese **Xiaomi Smart Camera PTZ Version 2K** (`chuangmi.camera.ip029a`).
- Xiaomi account region: **China (`cn`)**.
- Home Assistant **2026.11.1**.
- Xiaomi Camera Native **v0.3.11**, installed from the **integration-only ZIP**.
- Transport: **CS2 + UDP**.
- Source video: **H.265**; video output mode **H.264** (transcoding).

## Direct user observations

| Test | Reported result |
| --- | --- |
| First camera: video playback | Works |
| First camera: Pan left | Physical movement left confirmed |
| First camera: Pan right | Physical movement right confirmed |
| First camera: Tilt up | Physical movement up confirmed |
| First camera: Tilt down | Physical movement down confirmed |
| Repeated commands on first camera | Each direction pressed several times without reported errors |
| First camera: `last_ptz_error` | `null` after commands |
| First camera: `last_error` | `null` |
| Second camera: video playback | Works, same Xiaomi account |
| Second camera: PTZ | Experimental option enabled in v0.3.11; movement **not tested** |

The reporter explicitly confirmed the direction of physical movement for **one camera**, using Xiaomi Camera Native v0.3.11, and confirmed streaming on **two cameras**. This is sufficient to promote `ip029a` into the integration's *model-level* verified PTZ allowlist in v0.3.12, while preserving the limits of this evidence.

## Limitations

- No firmware version or device hardware revision was provided; compatibility across revisions remains unverified.
- No independently inspectable video, command/position acknowledgement, or instrumentation was supplied for this test.
- PTZ for the second camera was not physically tested; do not claim two PTZ-verified devices.
- These observations concern v0.3.11. v0.3.12 only changes the PTZ model gate; the motor packet/command implementation is not modified.
- Successful command submission and error-free diagnostics alone do not establish movement; the *report of observed physical movement* is the PTZ evidence.

See also the separate [24 October 2026 recordings](PTZ_HARDWARE_VERIFICATION_2026-10-24.md) for `029a02`, C200 and C301.
