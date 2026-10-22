# Xiaomi Camera Native — validation status

This document distinguishes packaging checks from functional hardware testing.

## Packaging validation (0.3.8)

Run from the root of the repository:

```bash
python3 tools/validate_package.py
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components
```

These local checks validate HACS layout, JSON metadata, bundled files and Python
syntax; **they do not validate camera streaming, authentication or pan/tilt**.

Once published to GitHub, review the results of the `HACS Validation` and
`Hassfest Validation` jobs under GitHub Actions. Their result cannot be
confirmed by local packaging checks.

## Hardware and runtime compatibility

The original README reports preliminary reception of source video on:

| Camera | Model ID |
| --- | --- |
| Mi 360 Home Security Camera 2K | `chuangmi.camera.029a02` |
| Xiaomi Smart Camera C200 | `chuangmi.camera.046c04` |
| Xiaomi Smart Camera C301 | `mxiang.camera.c301` |

**Those are the project's documented observations, not new tests run while
preparing this distribution.** Hardware PTZ operation, firmware support,
audio, HomeKit end-to-end playback and multi-client performance are not
guaranteed. See the main README's compatibility and limitations sections.

## Historical testing reference

Earlier README revisions referred to 73 Python tests, 9 JavaScript DOM tests,
and standalone test tools. Those historical test sources are **not present**
in the published 0.3.7 repository and have not been reconstructed here.
The new `tests/` folder contains **packaging checks only**.

## Security and troubleshooting

Do not attach Mi Home passwords, passTokens, authorization cookies, personal
endpoint URLs or session keys to public bug reports. Use sanitized HA logs.
