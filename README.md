<img width="256" height="256" alt="icon" src="https://github.com/user-attachments/assets/c3833052-52e9-4ef4-9595-f7bf21ac5f13" />

# Xiaomi Camera Native

**Direct Xiaomi camera streaming and pan/tilt controls for Home Assistant — without go2rtc.**

Xiaomi Camera Native connects to compatible Xiaomi cameras using a native Python implementation of **MISS over CS2**. Video travels over your local network, and the cameras appear as ordinary Home Assistant camera entities.

> **Experimental integration.** Camera compatibility depends on the model and firmware. Initial source video reception has been observed on the three models listed below. Pan/tilt movement and the camera pop-up controls still need broader hardware and frontend validation. See [VALIDATION.md](VALIDATION.md) for the tested scope.

## Features

- Direct camera video over CS2/UDP or CS2/TCP.
- Xiaomi account login, region selection, camera discovery and selection.
- Password login with CAPTCHA and email/SMS verification handling, or reuse of an existing Mi Home account credential.
- H.264 compatibility output through Home Assistant's FFmpeg, with configurable maximum resolution.
- Original H.264/H.265 video output without transcoding.
- A normal Home Assistant stream source for live view and snapshots.
- Four single-step controls: **Pan left**, **Pan right**, **Tilt up** and **Tilt down**.
- Movement arrows below the video in the standard camera pop-up, alongside **Download snapshot**.
- One shared video connection and, when required, one encoder per camera.
- On-demand streaming, idle disconnection, bounded reconnection attempts and credential-safe diagnostics.

No go2rtc process, bridge container, add-on or Xiaomi native SDK is required by this integration.

## Camera compatibility

| Camera | Model | Default camera quality |
| --- | --- | --- |
| Mi 360 Home Security Camera 2K | `chuangmi.camera.029a02` | HD, quality 2 |
| Xiaomi Smart Camera C200 | `chuangmi.camera.046c04` | HD, quality 3 |
| Xiaomi Smart Camera C301 | `mxiang.camera.c301` | Automatic, quality 0 |

Source video frames from all three models have been observed in an initial Home Assistant installation. This is not a guarantee for every firmware version or playback client.

Pan/tilt buttons are implemented for these three models. The underlying motor command has been [tested upstream on the Mi 360 2K](https://github.com/AlexxIT/go2rtc/pull/2531); physical movement through this Python implementation remains to be verified across the target cameras.

Other modern MISS/CS2 cameras may work for video, but are not verified. **TUTK, Agora, MTP and legacy camera protocols are not supported.** Movement buttons are limited to the models listed above.

## Requirements

- Cameras already paired with your Xiaomi account in Xiaomi Home/Mi Home.
- Home Assistant able to reach the cameras over the local network.
- Internet access for Xiaomi account authentication and fresh camera session keys.
- FFmpeg available to Home Assistant, including the `libx264` encoder for H.264 output.

The documented minimum baseline is **Home Assistant 2025.3.0**. Initial live streaming diagnostics were checked on Home Assistant 2026.10.2; not every Home Assistant version has been tested. The integration loads the standard `camera`, `ffmpeg`, `frontend` and `stream` dependencies automatically.

## Installation

### Installation through HACS (Custom repository)

1. Open **HACS** in Home Assistant.
2. From the three-dot menu, choose **Custom repositories**.
3. Add `https://github.com/Kosztyk/xiaomi_camera_native` and select **Integration**.
4. Find **Xiaomi Camera Native** in HACS and install it.
5. Restart Home Assistant; then add it from **Settings → Devices & services**.

Until the HACS default-catalog PR is accepted, the Custom repositories
step is required. After acceptance, the integration can be found by search.

### Manual installation

1. Download and extract the integration ZIP, or download this repository.
2. Copy the `custom_components/xiaomi_camera_native` directory into your Home Assistant configuration directory.
3. Confirm that the manifest is located at:

   ```text
   /config/custom_components/xiaomi_camera_native/manifest.json
   ```

4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**.
6. Search for **Xiaomi Camera Native**.
7. Sign in, select the same region used in Xiaomi Home/Mi Home, and choose your cameras.
8. Refresh your browser after setup so the camera pop-up controls can load. Use a hard refresh if necessary, or fully close and reopen the Home Assistant Companion app.

No YAML configuration or manual dashboard resource registration is required.

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
| CS2 transport | Automatic | Accept the camera's negotiated UDP or TCP transport; manual choices are also available. |
| Camera quality | HD; Automatic for C301 | Select the camera's own stream quality. |
| Video output | H.264 | Convert to H.264, or preserve the original encoded video. |
| Maximum H.264 height | 720p | Choose 360p, 720p, 1080p or 2160p. |
| Disconnect after no viewers | 30 seconds | Idle timeout, configurable from 10 to 300 seconds. |

The options menu also provides **Discover and select cameras** to update the camera selection. Existing camera entity IDs are retained for cameras that remain selected.

### H.264 output and CPU use

The default output is **H.264 with a maximum height of 720 pixels**. FFmpeg converts the camera video on the Home Assistant host, using `libx264`. Higher output resolutions increase CPU usage while a stream is active.

The height setting is an upper limit: the integration does not upscale a smaller camera image. Selecting 2160p therefore does not turn a lower-resolution camera into a 4K camera.

Select **Original** to retain the camera's encoded H.264 or H.265 video without transcoding. In this mode, the maximum-height setting is ignored. H.265 playback depends on the browser and device.

A camera's `source_codec` attribute describes its incoming video. Seeing `H.265` there while **H.264** output is selected is expected.

Hardware-accelerated transcoding is not implemented.

## Pan and tilt controls

### While watching video

Open a native Xiaomi camera's usual Home Assistant pop-up. The bottom bar contains **left, up, down and right** arrow buttons alongside **Download snapshot**.

Each press sends **one movement step**. The current video player stays in place, and the controls use the same button entities available on the camera's device page.

The frontend helper loads automatically. If the arrows do not appear after upgrading:

1. Restart Home Assistant and refresh the browser page.
2. Try a hard refresh or fully reopen the Companion app.
3. Confirm that you opened a `camera.*` entity from **Xiaomi Camera Native**.
4. Confirm that the camera's movement button entities are enabled.

The pop-up enhancement follows Home Assistant's current camera dialog structure. A future frontend change may require an update to the helper. The separate device buttons remain available if the helper cannot attach.

### Device buttons and automations

Each supported camera has four ordinary `button.*` entities:

- **Pan left**
- **Pan right**
- **Tilt up**
- **Tilt down**

Find their actual entity IDs on the camera's device page. Add them to a dashboard or use the standard `button.press` action in an automation. The pop-up resolves targets through the entity registry, so renamed button IDs remain supported.

While video is running, movement commands reuse its encrypted MISS connection. If the camera is idle, the integration opens a brief control-only connection and closes it after the step. This does not start video capture or an encoder; a cold connection still requires fresh cloud session keys.

Overlapping presses are rejected instead of queued. Movement commands are not automatically replayed on a new connection after a failure, because the camera may already have moved.

These controls perform discrete steps. Continuous movement, zoom, calibration, presets and position feedback are not implemented.

## HomeKit

The integration provides a standard camera stream source that can be used by Home Assistant's [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/).

Keep this integration's output set to **H.264**. In HomeKit Bridge options, select the camera under **Cameras that support native H.264 streams** to allow forwarding without another video encode; the YAML equivalent is `video_codec: copy`.

Select the native camera entity when exposing it to HomeKit. Audio is unavailable in this release. The movement controls do not appear inside Apple's camera interface, and HomeKit Bridge does not support HomeKit Secure Video recording.

End-to-end playback in Apple Home has not been verified by this project.

## How streaming works

Xiaomi's cloud supplies authentication and per-connection camera session keys. The integration then connects to the camera over the LAN using CS2 and decrypts its MISS video stream.

The video is packaged as MPEG-TS, optionally converted to H.264, and served to Home Assistant through an in-process endpoint bound to **127.0.0.1**. Home Assistant's built-in `stream` integration handles HLS playback.

Viewers and snapshots share the camera session. The connection closes after the configured idle timeout when there are no consumers. A live dashboard card, a preloaded stream or another playback client can keep it active.

CS2 starts with UDP communication to camera port **32108**, then uses the negotiated UDP or TCP port. Port forwarding is not required.

**Local video does not mean fully offline operation:** Xiaomi's cloud is still required when authenticating or obtaining fresh connection keys.

## Diagnostics and troubleshooting

Camera attributes include:

| Attribute | Meaning |
| --- | --- |
| `connection_status` | Idle, connecting, streaming, reconnecting or error. |
| `transport` | The negotiated CS2 transport. |
| `source_codec` | Incoming H.264 or H.265 video codec. |
| `video_mode` | Configured H.264 or Original output mode. |
| `frames_received` | Decrypted source frame count. |
| `reconnects` | Reconnection attempts. |
| `last_error` | Latest video-session error. |
| `pan_tilt_supported` | Whether controls are implemented for the model. |
| `last_ptz_error` | Latest movement-command error. |

`idle` is normal when nobody is watching. A nonzero source frame count confirms video reception, but does not by itself prove that a browser decoded the output.

| Symptom | Checks |
| --- | --- |
| No cameras discovered | Confirm the account, region and Mi Home device ownership. |
| Authentication failure | Reauthenticate the integration; check the missing field names in the error without sharing their values. |
| CS2 handshake timeout | Check the camera address, LAN reachability and transport. Close competing camera viewers during the first test. |
| Missing or poor-quality C200 video | Try HD or explicit Quality 3. |
| C301 does not produce video | Start with Automatic camera quality. |
| H.264 conversion fails | Confirm FFmpeg includes `libx264`, or try Original output. |
| High CPU usage | Lower the H.264 height, close unused live views, or use Original when your playback client supports it. |
| Movement controls report an error | Check `last_ptz_error`, camera reachability and account authentication. |

When reporting an issue, include the camera model, firmware, Home Assistant version, integration version, chosen transport/output mode, and relevant sanitized logs or integration diagnostics.

## Privacy and credentials

- Video travels from the camera to Home Assistant over the LAN; this integration does not proxy it through a go2rtc server.
- Account credentials and session keys are stored in Home Assistant and excluded from integration diagnostics.
- The internal media endpoint uses a random port and per-start secret and is bound to the loopback interface.
- Treat Home Assistant configuration storage and backups as sensitive. Do not publish passTokens, session keys, endpoint secrets or complete configuration dumps in issues.

## Current limitations

- No audio or two-way talk.
- No zoom, continuous PTZ, presets, calibration or position feedback.
- No SD-card playback or camera motion-event entities.
- No hardware transcoding or independent WebRTC server.
- No support for non-CS2 Xiaomi camera protocols.
- Cloud access remains necessary for connection provisioning.
- Camera firmware and Home Assistant frontend compatibility require further testing.

## Development and testing

Run from the repository root with Python 3.12 or later:

```bash
python3 tools/validate_package.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components
```

These commands check package metadata and Python syntax. The bundled
tests are **packaging tests only**; they are not a substitute for camera
integration or on-device testing. Remote GitHub Actions run HACS and
Hassfest validations after you push the repository.

Earlier documentation described a larger set of protocol and DOM tests
that is **not included** in the currently published repository.
See [VALIDATION.md](VALIDATION.md) for test scope and limits.

## Credits and license

Developed by **Kosztyk**.

The Xiaomi cloud and MISS/CS2 protocol implementations adapt work from [AlexxIT/go2rtc](https://github.com/AlexxIT/go2rtc), used under its MIT license. The motor-command reference is documented in [go2rtc PR #2531](https://github.com/AlexxIT/go2rtc/pull/2531).

Original copyright and permission notices are preserved in [LICENSE](License) and [NOTICE](custom_components/xiaomi_camera_native/NOTICE). go2rtc itself and Xiaomi's closed-source SDK are not bundled or executed by this integration.
