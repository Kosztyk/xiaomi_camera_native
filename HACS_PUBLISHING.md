# Publishing Xiaomi Camera Native to HACS

Repository: https://github.com/Kosztyk/xiaomi_camera_native

## Review fixes and hardware evidence

In v0.3.14 English translations match `strings.json`, runtime and manifest
versions agree, and the root and bundled MIT licenses preserve Kosztyk
and Alexey Khit attribution. The four verified CS2 models, including
`chuangmi.camera.ip029a`, have four movement directions by default.

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

The guarded v0.3.14 release workflow creates a full GitHub release only after
successful main-branch validation and only while the validated commit is still
the main branch head. It does not replace an existing release or tag.
Confirm that the release points to the validated commit and use its individual
HACS, Hassfest and Python job URLs in the catalog submission.

## HACS custom repository installation

HACS > three-dot menu > Custom repositories > paste:

https://github.com/Kosztyk/xiaomi_camera_native

Select **Integration**, install, restart HA and configure the integration.

## Replacement for closed HACS PR #12439

[The original submission](https://github.com/hacs/default/pull/12439) was
closed as stale on 24 October 2026. The maintainer's follow-up there records
the completed fixes and public hardware evidence. The replacement submission
should reference that review history and the v0.3.14 release after CI validation.

Before creating a replacement, check for an
[existing open Xiaomi Camera Native submission](https://github.com/hacs/default/pulls?q=is%3Apr+is%3Aopen+xiaomi_camera_native).
Maintain one open catalog PR. Use a dedicated branch based on current
`hacs/default:master`, add only `Kosztyk/xiaomi_camera_native` to `integration`
in alphabetical order, and allow maintainer edits. Complete the current PR
template with the release and successful validation links. Mark it ready
after the catalog checks pass, subject to the HACS review-queue limit.

Repository topics should include `homeassistant`,
`homeassistant-custom-component`, `homeassistant-integration`, `xiaomi` and
`xiaomi-camera`.

Reference: https://hacs.xyz/docs/publish/include/
