# Publishing Xiaomi Camera Native to HACS

Repository: https://github.com/Kosztyk/xiaomi_camera_native

## 1. Merge reviewer fixes

Merge v0.3.9 only after HACS, Hassfest and packaging checks succeed. The PTZ
whitelist has not expanded and covers the three models with owner-provided
physical test recordings.

## 2. Fix GitHub repository topic (metadata, not versioned file)

In GitHub: repository home page > About > Topics, replace
`homeassistant-integraiton` with `homeassistant-integration`.

## 3. GitHub Actions

Open https://github.com/Kosztyk/xiaomi_camera_native/actions

Confirm **HACS Validation**, **Hassfest Validation**, and **Packaging and
Python checks** are successful. Address any findings before releasing.

## 4. GitHub Release

The v0.3.9 release workflow automatically creates a full GitHub release after
the successful main-branch validation run. Confirm release and CI job URLs.

## 5. Test HACS custom repository installation

HACS > three-dot menu > Custom repositories > paste:

https://github.com/Kosztyk/xiaomi_camera_native

Select **Integration**, install, restart HA and configure the integration.

## 6. Update existing HACS PR #12439

Do **not** create a duplicate catalog PR. Instead update
https://github.com/hacs/default/pull/12439 with the v0.3.9 release,
HACS/Hassfest validation jobs and evidence report. Attach the three videos,
mark the draft ready and re-request review as Frenck requested.

Reference: https://www.hacs.xyz/docs/publish/include/
