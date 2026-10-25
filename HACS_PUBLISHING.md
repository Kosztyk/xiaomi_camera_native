# Publishing Xiaomi Camera Native to HACS

Repository: https://github.com/Kosztyk/xiaomi_camera_native

## Review fixes and hardware evidence

The v0.3.9 review fixes are retained in v0.3.10: English translations match
`strings.json`, runtime and manifest versions agree, and the root/bundled MIT
licenses preserve Kosztyk and Alexey Khit attribution. The PTZ allowlist covers
only the three models tested through this native Python implementation.

The [hardware report](docs/PTZ_HARDWARE_VERIFICATION_2026-10-24.md) links to
the three public recordings already attached to the
[review reply on #12439](https://github.com/hacs/default/pull/12439#issuecomment-6388692080).
The tested v0.3.8 motor implementation remains unchanged in v0.3.10.

## GitHub Actions

Open https://github.com/Kosztyk/xiaomi_camera_native/actions

Confirm **HACS Validation**, **Hassfest Validation**, and **Packaging and
Python checks** are successful. Address any findings before releasing.

## GitHub release

The guarded v0.3.10 release workflow creates a full GitHub release only after
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
must reference that review history and the current v0.3.10 release.

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
