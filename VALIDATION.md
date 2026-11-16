# Xiaomi Camera Native — validation status

This document distinguishes packaging checks from functional hardware testing.

## Release validation (0.3.14)

Run from the root of the repository:

```bash
python3 tools/validate_package.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components
node --test tests/test_ipc020_frontend.js
```

The Python tests cover packaging, translations, version and license
consistency, device-registry cleanup, Xiaomi request handling, media transport,
snapshot limits, stream and encoder recovery, and supported movement
directions. The JavaScript test checks popup controls for both `ipc020` and
four-direction CS2 cameras. These checks use synthetic inputs and test doubles.

The GitHub workflow also runs the `HACS Validation` and
`Hassfest Validation` jobs before publishing the release.

## Hardware and runtime compatibility

On **2026-10-24** the owner tested actual Xiaomi cameras using the native
Home Assistant Xiaomi Camera Native v0.3.8 buttons. Screen
recordings show the scene moving during PTZ button presses. Home Assistant's
recorder logged the same native button entities at the corresponding times.

| Camera | Verified model ID | Recording start (EEST) |
| --- | --- | --- |
| Mi 360 Home Security Camera 2K | `chuangmi.camera.029a02` | 21:55:21 |
| Xiaomi Smart Camera C200 | `chuangmi.camera.046c04` | 21:48:09 |
| Xiaomi Smart Camera C301 | `mxiang.camera.c301` | 22:05:16 |

Detailed timestamp evidence: [PTZ verification report](docs/PTZ_HARDWARE_VERIFICATION_2026-10-24.md).
The three videos and report are publicly attached to the owner's
[review reply on #12439](https://github.com/hacs/default/pull/12439#issuecomment-6388692080)
and remain available after that PR was closed. Direct recording links are in
the report. The tested motor command implementation is unchanged in v0.3.9
through v0.3.14. Firmware identifiers were not available in the HA device registry.
Recorder events alone do not prove motor movement; the changes in the video
provide that separate observation. This does not verify other firmware versions
or provide a motor position/command acknowledgement.

On **2026-11-12**, a separate owner of `chuangmi.camera.ip029a` tested **v0.3.11**
from the integration-only ZIP using Home Assistant **2026.11.1** and Mi Home
**China (`cn`)** account region. The user confirmed actual physical movement
left, right, up and down, including repeated presses, on **one camera**.
Streaming worked on **two** cameras of the model, using CS2/UDP and incoming
H.265 video with H.264 output; **PTZ on the second was not tested**.
The report contained `last_ptz_error: null` and `last_error: null`.
This is **user-reported physical movement, not an independently reviewed video**.
It supports model-level PTZ promotion but cannot guarantee every firmware.
See the [dated ip029a report](docs/PTZ_HARDWARE_VERIFICATION_2026-11-12_ip029a.md).

For `chuangmi.camera.ipc020`, a user confirmed TUTK/18 streaming,
physical horizontal pan and popup behavior on firmware `4.0.9_0102`
using v0.3.14b5. [Hardware evidence and diagnostics](docs/IPC020.md#hardware-verification)

The release covers the tested protocols and models. The TUTK 25+ recovery
and codec-change checks used synthetic streams. The integration exposes
video only. HomeKit end-to-end playback remains unverified.

## Security and troubleshooting

Do not attach Mi Home passwords, passTokens, authorization cookies, personal
endpoint URLs or session keys to public bug reports. Use sanitized HA logs.

## Private test v0.3.14b3 — ipc020 TUTK PTZ ACK behavior

- Exercises TUTK/18 command/request-ID ACK matching, stale-ACK rejection,
  one-attempt-only motor commands, media retry preservation and sanitized
  counter behavior in offline Python tests.
- Video success is separately reported by a user on v0.3.14b2, documented in
  `docs/IPC020_HARDWARE_TEST_FEEDBACK_2026-11-13.md`.
- Subsequent b3 field testing on 14 November 2026 confirmed 6/6 horizontal movements and
  no vertical movement; see the private b4 section below.

## Private test v0.3.14b4 — ipc020 horizontal-only PTZ

- On 14 November 2026, the owner of an `ipc020` reported b3 TUTK/18 H.265
  video with 5,300 frames, 0 drops, 0 malformed packets and 0 reconnects.
  In a controlled trial, **left 3/3** and **right 3/3** produced physical
  movement; up/down did not (0/3 each) despite matching transport ACKs.
- Official Mi Home UI was independently checked by the user and offers
  left/right only. This is a horizontal-pan-only camera. See the
  [hardware feedback](docs/IPC020_HARDWARE_TEST_FEEDBACK_2026-11-14.md).
- b4 offline tests verify: only two buttons on ipc020, four on verified CS2
  models, explicit protocol rejection of tilt, targeted registry cleanup,
  and frontend suppression of unavailable controls. TUTK media and b3 ACK
  implementations are unchanged.
- Later hardware results use b5.

## Private test v0.3.14b5 — ipc020 recovery

- Offline tests cover automatic IP recovery, fixed addresses, concurrent
  service-token refresh, UDP port negotiation, live-session pan readiness,
  and immediate publication of motor timeouts.
- The owner confirmed H.265 input, H.264 output, and six physical left/right
  moves on TUTK/18. In a fresh browser tab with the b5 asset, both popup arrows
  also moved the camera and live video continued. [b5 hardware report](https://github.com/Kosztyk/xiaomi_camera_native/issues/5#issuecomment-6910597109)
  · [Popup retest](https://github.com/Kosztyk/xiaomi_camera_native/issues/5#issuecomment-6911560788)

## Private test v0.3.14b6 — security and stream recovery

- Regression tests cover snapshot size limits, authenticated redirect
  rejection, cancellation-safe encoder shutdown, byte-limited media queues,
  MPEG-TS payload integrity, codec changes, and TUTK 25+ sequence gaps and
  rollover.
- Device registry tests cover both single-entry ownership and the older
  multi-entry registry.
- Local loopback tests exercised signed TUTK/18 streaming and pan ACKs, a
  concurrent JPEG snapshot while encoding H.264, and H.265-to-H.264
  reconnection in both output modes. A separate test checked that an
  authenticated HTTP 307 sent no request to its destination. Repeated
  cancellation reaped a subprocess that ignored SIGTERM.
- On Home Assistant 2026.11.1, b6 received frames on the C200 and C301
  without reconnects or fresh registry deprecation warnings. The `029a02`
  hit a CS2 handshake timeout before video reception during that check.
  The Home Assistant host used for this check did not have an `ipc020`.
