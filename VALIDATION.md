# Xiaomi Camera Native — validation status

This document distinguishes packaging checks from functional hardware testing.

## Packaging validation (0.3.10)

Run from the root of the repository:

```bash
python3 tools/validate_package.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components
```

The seven local tests validate HACS layout, JSON metadata, bundled files,
English translation parity, version/license consistency and the exact PTZ
model allowlist. Compilation checks Python syntax. **These checks do not
validate camera streaming, authentication or physical pan/tilt movement**.

Once published to GitHub, review the results of the `HACS Validation` and
`Hassfest Validation` jobs under GitHub Actions. Their result cannot be
confirmed by local packaging checks.

## Hardware and runtime compatibility

On **2026-10-24** the owner tested actual Xiaomi cameras using the native
Home Assistant Xiaomi Camera Native v0.3.8 buttons, **not go2rtc**. Screen
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
and v0.3.10. Firmware identifiers were not available in the HA device registry.
Recorder events alone do not prove motor movement; the changes in the video
provide that separate observation. This does not verify other firmware versions
or provide a motor position/command acknowledgement.

HACS and Hassfest CI check packaging/integration rules only, not motors.
Audio, HomeKit end-to-end playback and multi-client performance remain
unverified.

## Historical testing reference

Earlier README revisions referred to 73 Python tests, 9 JavaScript DOM tests,
and standalone test tools. Those historical test sources are **not present**
in the published 0.3.7 repository and have not been reconstructed here.
The current `tests/` folder contains **seven offline structural checks**, not
the historical protocol, lifecycle or JavaScript test suites.

## Security and troubleshooting

Do not attach Mi Home passwords, passTokens, authorization cookies, personal
endpoint URLs or session keys to public bug reports. Use sanitized HA logs.
