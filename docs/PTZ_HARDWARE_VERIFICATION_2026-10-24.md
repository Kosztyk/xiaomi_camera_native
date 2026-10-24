# Xiaomi Camera Native PTZ hardware verification — 2026-10-24

**Tested software:** Xiaomi Camera Native v0.3.8, using its native Python
MISS/CS2 integration and Home Assistant `button.*` entities. **NOT go2rtc.**
**Time zone:** EEST (Europe/Bucharest, UTC+03:00).

Physical-camera screen recordings were submitted by the device owner.
In each recording, viewpoint changes coincide with pressing the native PTZ
controls. These observations were cross-checked against the Home Assistant
recorder's timestamps for exactly those button entities.

**Reviewer access to recordings:** The original MOV videos are not part of
this source tree. The maintainer should attach compressed MP4 copies to
[hacs/default PR #12439](https://github.com/hacs/default/pull/12439) before
requesting review, so the visual evidence is independently accessible.

## Mi 360 Home Security Camera 2K (`chuangmi.camera.029a02`)

**Recording:** `Screen Recording 2026-10-24 at 21.55.21.mov` (20.13 s).
**Observable result:** Living Room framing moves between distinct viewpoints,
including sofa/curtains/doorway, during PTZ control activations.

| Local time | HA PTZ action |
| --- | --- |
| 21:55:24.829 | Tilt up |
| 21:55:28.278 | Tilt down |
| 21:55:30.697 | Pan right |
| 21:55:32.949 | Pan left |
| 21:55:35.853 | Tilt up |
| 21:55:38.257 | Pan right |

## Xiaomi Smart Camera C200 (`chuangmi.camera.046c04`)

**Recording:** `Screen Recording 2026-10-24 at 21.48.09.mov` (26.96 s).
**Observable result:** Entry hallway framing changes during PTZ activation.

| Local time | HA PTZ action |
| --- | --- |
| 21:48:13.721 | Tilt down |
| 21:48:17.107 | Tilt up |
| 21:48:19.278 | Pan left |
| 21:48:21.645 | Pan right |
| 21:48:24.183 | Pan right |
| 21:48:27.199 | Tilt up |

## Xiaomi Smart Camera C301 (`mxiang.camera.c301`)

**Recording:** `Screen Recording 2026-10-24 at 22.05.16.mov` (17.50 s).
**Observable result:** The kitchen framing changes laterally and vertically,
including a downward view of the floor.

| Local time | HA PTZ action |
| --- | --- |
| 22:05:19.827 | Tilt up |
| 22:05:20.930 | Tilt up |
| 22:05:21.998 | Tilt up |
| 22:05:23.451 | Pan right |
| 22:05:24.683 | Pan right |
| 22:05:25.952 | Pan left |
| 22:05:27.025 | Pan left |
| 22:05:27.955 | Pan left |
| 22:05:29.005 | Pan left |
| 22:05:30.154 | Tilt down |
| 22:05:31.068 | Tilt down |

## Limits of verification

- HA recorder events prove PTZ buttons were activated, not a camera command ACK.
- Physical movement evidence derives from changing camera views in recordings
  during those events; no independent physical position sensor was used.
- The existing integration's WARNING-level logs do not capture individual
  successful MISS `0x112` transmissions. No proof of ACK is claimed.
- The three cameras' firmware versions were unavailable in Home Assistant's
  device registry. No broader firmware or model compatibility is asserted.
- No PTZ models outside these three are enabled.
- Original video files must be available to the HACS reviewer to inspect.

This is real-user, model-specific physical evidence for the three models
already in `PAN_TILT_MODELS`, not simulated or mocked hardware validation.
