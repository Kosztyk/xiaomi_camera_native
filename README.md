<img width="256" height="256" alt="icon" src="https://github.com/user-attachments/assets/c3833052-52e9-4ef4-9595-f7bf21ac5f13" />

# Xiaomi Camera Native

**Direct Xiaomi camera streaming and pan/tilt controls for Home Assistant — without go2rtc.**

Xiaomi Camera Native streams compatible cameras to Home Assistant over the local network. It uses **MISS over CS2** on most supported cameras. Version **0.3.14** adds opt-in **TUTK LAN streaming and horizontal pan** for the China-region IMILAB outdoor PTZ camera `chuangmi.camera.ipc020`. [ipc020 setup and hardware results](docs/IPC020.md)

Camera compatibility depends on model and firmware. The table below lists the hardware exercised in Home Assistant. [Validation details](VALIDATION.md)

## Features

- Local video over CS2/UDP, CS2/TCP or, for `ipc020`, TUTK/UDP.
- Xiaomi account login, region selection, camera discovery and selection.
- Password login with CAPTCHA and email/SMS verification handling, or reuse of an existing Mi Home account credential.
- H.264 compatibility output through Home Assistant's FFmpeg, with configurable maximum resolution.
- Original H.264/H.265 video output without transcoding.
- A normal Home Assistant stream source for live view and snapshots.
- Single-step movement in four directions on verified CS2 cameras and optional **left/right** on `ipc020`.
- Movement arrows below the video in the standard camera pop-up, alongside **Download snapshot**.
- One shared video connection and, when required, one encoder per camera.
- On-demand streaming, idle disconnection, bounded reconnection attempts and credential-safe diagnostics.

No go2rtc process, bridge container, add-on or Xiaomi native SDK is required by this integration.

## Camera compatibility

| Camera | Model | Transport | Movement | Default quality |
| --- | --- | --- | --- | --- |
| Mi 360 Home Security Camera 2K | `chuangmi.camera.029a02` | MISS/CS2 | Left, right, up, down | HD, quality 2 |
| Xiaomi Smart Camera PTZ Version 2K (China) | `chuangmi.camera.ip029a` | MISS/CS2 | Left, right, up, down | HD, quality 2 |
| Xiaomi Smart Camera C200 | `chuangmi.camera.046c04` | MISS/CS2 | Left, right, up, down | HD, quality 3 |
| Xiaomi Smart Camera C301 | `mxiang.camera.c301` | MISS/CS2 | Left, right, up, down | Automatic, quality 0 |
| IMILAB outdoor PTZ (China) | `chuangmi.camera.ipc020` | TUTK/UDP, opt-in | Left and right, opt-in and live-only | HD |

The four CS2 models create their movement buttons automatically. For `ipc020`, the tester confirmed H.265 source video, H.264 output, and physical left/right movement with both the device buttons and the popup on firmware `4.0.9_0102` using `v0.3.14b5`. The camera uses the same two directions in Mi Home. [CS2 hardware evidence](VALIDATION.md#hardware-and-runtime-compatibility) · [ipc020 hardware evidence](docs/IPC020.md#hardware-verification)

Other MISS/CS2 models may stream video. Movement controls require a supported model.

## Requirements

- Cameras already paired with your Xiaomi account in Xiaomi Home/Mi Home.
- Home Assistant able to reach the cameras over the local network.
- Internet access for Xiaomi account authentication and fresh camera session keys.
- FFmpeg available to Home Assistant, including the `libx264` encoder for H.264 output.

The documented minimum baseline is **Home Assistant 2025.3.0**. Initial live streaming diagnostics were checked on Home Assistant 2026.10.2; not every Home Assistant version has been tested. The integration loads the standard `camera`, `ffmpeg`, `frontend` and `stream` dependencies automatically.

## Installation

### HACS installation (recommended)

1. Open **HACS** in Home Assistant and search the default catalog for **Xiaomi Camera Native**.
2. Open the listing and select **Download**.
3. Restart Home Assistant, then [configure the integration](#configure-in-home-assistant).

### Manual installation

1. Download and extract the source ZIP from the [latest GitHub release](https://github.com/Kosztyk/xiaomi_camera_native/releases/latest).
2. Copy the `custom_components/xiaomi_camera_native` directory to `/config/custom_components/`.
3. Confirm that the manifest is located at:

   ```text
   /config/custom_components/xiaomi_camera_native/manifest.json
   ```

4. Restart Home Assistant, then [configure the integration](#configure-in-home-assistant).

### Configure in Home Assistant

1. Go to **Settings → Devices & services → Add integration** and select **Xiaomi Camera Native**.
2. Sign in, select the same region used in Xiaomi Home/Mi Home, and choose your cameras.
3. Refresh your browser after setup so the camera pop-up controls can load. Use a hard refresh if necessary, or fully close and reopen the Home Assistant Companion app.

No YAML configuration or manual dashboard resource registration is required.

### Remove a camera / Rediscover

Open **Settings → Devices & services → Xiaomi Camera Native → Configure →
Rediscover**, then **deselect** any cameras you no longer want and save.
The integration reloads with the selected cameras and removes the deselected
camera's Home Assistant device record and its camera/PTZ entity records.
Previous camera-specific streaming/PTZ options for removed cameras are also cleared.

The cleanup also runs after a successful integration restart/reload, fixing
empty camera devices left behind by older releases (for example, "Outdoor Garage").
If an orphan remains, open its device page and choose **Delete device**:
v0.3.13 supports deletion of orphaned Xiaomi camera devices. A **currently
selected** camera cannot be deleted that way; deselect it in Rediscover first.
A camera still visible in the Mi Home account may appear in the Rediscover list,
but will not be re-added until explicitly selected.

### Account and region

Choose the region where the cameras are registered:

| Region | Code |
| --- | --- |
| China | `cn` |
| Europe | `de` |
| India | `i2` |
| Russia | `ru` |
| Singapore | `sg` |
| United States | `us` |

For a European Mi Home account, select **Europe (`de`)**. Selecting another region can result in an empty or incomplete camera list.

You can also select **Use an existing Mi Home account credential** and supply your numeric Xiaomi account ID and account **passToken**. If migrating from go2rtc, this is the account credential under its `xiaomi:` configuration section. It is different from an individual camera's 32-character device token.

The password is used only during interactive login. Home Assistant stores the reusable account credential and completed authentication session so the integration can reconnect.

## Camera options

Open **Settings → Devices & services → Xiaomi Camera Native → Options → Configure a camera**.

| Option | Default | Purpose |
| --- | --- | --- |
| Camera IPv4 address | Discovered address | Local address used to connect to the camera. |
| Automatically update camera IP | Enabled | Recover a changed address from matching router trackers or Xiaomi cloud discovery, and save it after a successful connection. |
| CS2 transport | Automatic | Accept the camera's negotiated UDP or TCP transport; manual choices are also available. |
| Camera quality | HD; Automatic for C301 | Select the camera's own stream quality. |
| Video output | H.264 | Convert to H.264, or preserve the original encoded video. |
| Maximum H.264 height | 720p | Choose 360p, 720p, 1080p or 2160p. |
| Disconnect after no viewers | 30 seconds | Idle timeout, configurable from 10 to 300 seconds. |
| Use TUTK LAN transport (ipc020) | Off | Connect to the IMILAB `ipc020` over direct LAN UDP. |
| Enable horizontal pan (ipc020) | Off | Create Left and Right buttons when TUTK is enabled. Pan becomes ready after live video arrives. |

The options menu also provides **Discover and select cameras** to update the camera selection. Existing camera entity IDs are retained for cameras that remain selected.

### Set up the IMILAB ipc020

1. Add the camera from its Mi Home account region. The tested region was **China (`cn`)**.
2. In **Configure a camera**, choose the `ipc020` and turn on **Use TUTK LAN transport (ipc020)**. Start with **HD** and **H.264** to match the tested setup.
3. To use movement controls, turn on **Enable horizontal pan (ipc020)**. Save and open the camera in a fresh browser tab after upgrading.
4. Wait for live video. The popup offers only Left and Right, and the integration accepts presses once `pan_tilt_ready` becomes true.

The TUTK option is specific to this model. [Full setup and troubleshooting](docs/IPC020.md)

### H.264 output and CPU use

The default output is **H.264 with a maximum height of 720 pixels**. FFmpeg converts the camera video on the Home Assistant host, using `libx264`. Higher output resolutions increase CPU usage while a stream is active.

The height setting is an upper limit: the integration does not upscale a smaller camera image. Selecting 2160p therefore does not turn a lower-resolution camera into a 4K camera.

Select **Original** to retain the camera's encoded H.264 or H.265 video without transcoding. In this mode, the maximum-height setting is ignored. H.265 playback depends on the browser and device.

A camera's `source_codec` attribute describes its incoming video. Seeing `H.265` there while **H.264** output is selected is expected.

Hardware-accelerated transcoding is not implemented.

## Pan and tilt controls

### While watching video

Open the camera's standard Home Assistant popup. The bottom bar shows the directions supported by that camera alongside **Download snapshot**. The `ipc020` popup shows Left and Right when horizontal pan is enabled.

Each press sends **one movement step**. The current video player stays in place, and the controls use the same button entities available on the camera's device page.

The frontend helper loads automatically. If the arrows do not appear after upgrading:

1. Restart Home Assistant and refresh the browser page.
2. Try a hard refresh or fully reopen the Companion app.
3. Confirm that you opened a `camera.*` entity from **Xiaomi Camera Native**.
4. Confirm that the camera's movement button entities are enabled.

The pop-up enhancement follows Home Assistant's current camera dialog structure. A future frontend change may require an update to the helper. The separate device buttons remain available if the helper cannot attach.

### Device buttons and automations

The four CS2 models provide four ordinary `button.*` entities:

- **Pan left**
- **Pan right**
- **Tilt up**
- **Tilt down**

The `ipc020` provides **Pan left** and **Pan right** after both options are enabled. An upgrade removes old `ipc020` tilt entities created by early betas. Find the current entity IDs on the camera's device page. The standard `button.press` action can target them, and the popup resolves renamed buttons through the entity registry.

CS2 movement reuses an active MISS connection. When the CS2 camera is idle, the integration opens a brief control-only connection and closes it after the step. The `ipc020` uses the current TUTK video session for horizontal pan and requires `pan_tilt_ready` before sending a command.

Overlapping presses are rejected instead of queued. Movement commands are not automatically replayed on a new connection after a failure, because the camera may already have moved.

These controls perform discrete steps. Continuous movement, zoom, calibration, presets and position feedback are not implemented.

### Chinese `ip029a` model — verified PTZ support (12 November 2026)

1. Sign in to the Xiaomi account region where the camera is registered (the reported test used **China, `cn`**).
2. Choose `chuangmi.camera.ip029a`. The four PTZ `button.*` entities are created automatically; **there is no experimental pan/tilt switch to enable** since v0.3.12.
3. To match the tested playback setup, begin with **CS2 transport: Automatic** (the confirmed negotiated transport was UDP) and **Video output: H.264**. The tested source codec was **H.265**.
4. Open the native camera entity and try single movement presses in a clear, safe area. The buttons send discrete steps; no calibration, presets or position feedback are implemented.
5. If a camera revision behaves differently, report the model, firmware, region, transport, playback and physical PTZ result, along with sanitized `pan_tilt_supported` and `last_ptz_error` diagnostics. Do not post Xiaomi credentials or camera keys.

**Scope of evidence:** One `ip029a` camera was physically tested for left, right, up and down movement on integration v0.3.11 with Home Assistant 2026.11.1. A second `ip029a` camera streamed successfully but its motors were not tested. This is a user report, not a video recording independently reviewed by maintainers. [Full report](docs/PTZ_HARDWARE_VERIFICATION_2026-11-12_ip029a.md).

### Physical motor verification (24 October 2026)

The owner tested **Mi 360 2K / `chuangmi.camera.029a02`**, **C200 / `chuangmi.camera.046c04`**, and **C301 / `mxiang.camera.c301`** with Xiaomi Camera Native v0.3.8. The screen recordings show changes in the camera scene alongside native PTZ button presses. The Home Assistant recorder independently logged matching left/right/up/down events. The CS2 motor command is the same in v0.3.14. [Model-specific report](docs/PTZ_HARDWARE_VERIFICATION_2026-10-24.md) · [Published recordings](https://github.com/hacs/default/pull/12439#issuecomment-6388692080)

## HomeKit

The integration provides a standard camera stream source that can be used by Home Assistant's [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/).

Keep this integration's output set to **H.264**. In HomeKit Bridge options, select the camera under **Cameras that support native H.264 streams** to allow forwarding without another video encode; the YAML equivalent is `video_codec: copy`.

Select the native camera entity when exposing it to HomeKit. Audio is unavailable in this release. The movement controls do not appear inside Apple's camera interface, and HomeKit Bridge does not support HomeKit Secure Video recording.

End-to-end playback in Apple Home has not been verified by this project.

## How streaming works

Xiaomi's cloud supplies authentication and per-connection credentials. The integration connects over the LAN to receive MISS/CS2 video or, when enabled for `ipc020`, TUTK video. It refreshes an expired Xiaomi service token once and retries the camera credential request.

The video is packaged as MPEG-TS, optionally converted to H.264, and served to Home Assistant through an in-process endpoint bound to **127.0.0.1**. Home Assistant's built-in `stream` integration handles HLS playback.

Viewers and snapshots share the camera session. The connection closes after the configured idle timeout when there are no consumers. A live dashboard card, a preloaded stream or another playback client can keep it active.

CS2 starts on camera UDP port **32108**, then uses the negotiated UDP or TCP port. TUTK starts on camera UDP port **32761** and uses the peer selected during the handshake.

**Local video does not mean fully offline operation:** Xiaomi's cloud is still required when authenticating or obtaining fresh connection keys.

## Diagnostics and troubleshooting

Camera attributes include:

| Attribute | Meaning |
| --- | --- |
| `connection_status` | Idle, connecting, streaming, reconnecting or error. |
| `transport` | The negotiated transport, such as `cs2+udp`, `cs2+tcp` or `tutk+udp`. |
| `source_codec` | Incoming H.264 or H.265 video codec. |
| `video_mode` | Configured H.264 or Original output mode. |
| `frames_received` | Decrypted source frame count. |
| `reconnects` | Reconnection attempts. |
| `last_error` | Latest video-session error. |
| `pan_tilt_supported` | Whether any movement controls are enabled for this camera. |
| `pan_tilt_directions` | Directions exposed by the camera's device buttons and popup. |
| `pan_tilt_ready` | Whether a movement command is allowed now. For `ipc020`, the current session must be streaming. |
| `pan_tilt_experimental` | Compatibility attribute for the `ipc020` horizontal-pan opt-in. |
| `last_ptz_error` | Latest movement-command error. |
| `ip_address` | Current local camera address. |
| `auto_update_ip` | Whether automatic address recovery is enabled. |
| `address_source` | Configured address, matching router tracker, or Xiaomi cloud discovery. |
| `address_updates` | Number of address changes accepted after a successful connection. |

`idle` is normal when nobody is watching. A nonzero source frame count confirms video reception, but does not by itself prove that a browser decoded the output.

| Symptom | Checks |
| --- | --- |
| No cameras discovered | Confirm the account, region and Mi Home device ownership. |
| Authentication failure | Reauthenticate the integration; check the missing field names in the error without sharing their values. |
| CS2 handshake timeout | Check the camera address, LAN reachability and transport. Close competing camera viewers during the first test. |
| `ipc020` provisioning fails with code `-6` | Enable **Use TUTK LAN transport (ipc020)**. See the [ipc020 guide](docs/IPC020.md#troubleshooting) for the next diagnostic fields. |
| Missing or poor-quality C200 video | Try HD or explicit Quality 3. |
| C301 does not produce video | Start with Automatic camera quality. |
| H.264 conversion fails | Confirm FFmpeg includes `libx264`, or try Original output. |
| High CPU usage | Lower the H.264 height, close unused live views, or use Original when your playback client supports it. |
| Movement controls report an error | Check `last_ptz_error`, camera reachability and account authentication. |

When reporting an issue, include the camera model, firmware, Home Assistant version, integration version, chosen transport/output mode, and relevant sanitized logs or integration diagnostics.

## Privacy and credentials

- Video travels from the camera to Home Assistant over the LAN; this integration does not proxy it through a go2rtc server.
- Home Assistant stores the Xiaomi account credential. Per-connection TUTK credentials stay in memory. Integration diagnostics omit credentials and media endpoint tokens.
- Authenticated Xiaomi API requests reject redirects. Requested snapshots are limited to 4,096 pixels per side and 8,847,360 pixels total.
- The internal media endpoint uses a random port and per-start secret and is bound to the loopback interface.
- Treat Home Assistant configuration storage and backups as sensitive. Do not publish passTokens, session keys, endpoint secrets or complete configuration dumps in issues.

## Current limitations

- No audio or two-way talk.
- No zoom, continuous PTZ, presets, calibration or position feedback.
- No SD-card playback or camera motion-event entities.
- No hardware transcoding or independent WebRTC server.
- TUTK support is limited to direct LAN access for `chuangmi.camera.ipc020`. Other supported cameras use MISS/CS2.
- Cloud access remains necessary for connection provisioning.
- Camera firmware and Home Assistant frontend compatibility require further testing.

## Development and testing

Run from the repository root with Python 3.12 or later:

```bash
python3 tools/validate_package.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components
node --test tests/test_ipc020_frontend.js
```

The suite covers packaging, translations, device cleanup, transport and
stream recovery, movement restrictions and the camera popup. GitHub Actions
also runs HACS and Hassfest validation. [Test scope and hardware results](VALIDATION.md)

## Credits and license

Developed by **Kosztyk**.

The Xiaomi cloud, MISS/CS2 and TUTK protocol implementations adapt work from [AlexxIT/go2rtc](https://github.com/AlexxIT/go2rtc) under its MIT license. The CS2 motor-command reference is [go2rtc PR #2531](https://github.com/AlexxIT/go2rtc/pull/2531).

Original copyright and permission notices are preserved in [LICENSE](License) and [NOTICE](custom_components/xiaomi_camera_native/NOTICE). go2rtc itself and Xiaomi's closed-source SDK are not bundled or executed by this integration.
