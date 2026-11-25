# Publishing Xiaomi Camera Native to HACS

Repository: https://github.com/Kosztyk/xiaomi_camera_native

## Review fixes and hardware evidence

In v0.3.16 English translations match `strings.json`, runtime and manifest
versions agree, and the root and bundled MIT licenses preserve Kosztyk
and Alexey Khit attribution. The five supported CS2 models have four movement
directions by default. [Model and hardware evidence](VALIDATION.md#hardware-and-runtime-compatibility)

The [hardware report](docs/PTZ_HARDWARE_VERIFICATION_2026-10-24.md) links to
the three public recordings already attached to the
[review reply on #12439](https://github.com/hacs/default/pull/12439#issuecomment-6388692080).
The tested CS2 motor implementation remains unchanged in v0.3.14.
The [ip029a report](docs/PTZ_HARDWARE_VERIFICATION_2026-11-12_ip029a.md)
records owner testimony rather than an independently reviewed recording; it
does not claim two PTZ-tested devices or firmware-wide validation.

Version v0.3.14 adds opt-in TUTK direct-LAN video and live left/right
pan for `chuangmi.camera.ipc020`. One owner confirmed video and physical
pan on firmware `4.0.9_0102` with TUTK/18 using the b5 build. See the
[ipc020 hardware results](docs/IPC020.md#hardware-verification).

## GitHub Actions

Open https://github.com/Kosztyk/xiaomi_camera_native/actions

Confirm **HACS Validation**, **Hassfest Validation**, and **Packaging and
Python checks** are successful. Address any findings before releasing.

## GitHub release

The guarded v0.3.16 release workflow creates a full GitHub release only after
successful main-branch validation and only while the validated commit is still
the main branch head. Confirm that the release points to the validated commit.

## HACS catalog

Install **Xiaomi Camera Native** from the default HACS catalog, then restart
Home Assistant and configure the integration. [Default catalog](https://github.com/hacs/default/blob/master/integration)

The original submission records earlier review fixes and public hardware
evidence. [HACS review history](https://github.com/hacs/default/pull/12439)

Repository topics should include `homeassistant`,
`homeassistant-custom-component`, `homeassistant-integration`, `xiaomi` and
`xiaomi-camera`.

Reference: https://hacs.xyz/docs/publish/include/
