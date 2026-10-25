# Xiaomi Camera Native v0.3.10 — HACS resubmission

Carries forward all fixes from [Frenck's review of #12439](https://github.com/hacs/default/pull/12439#pullrequestreview-5639185443):

- PTZ is limited to Mi 360 2K (`chuangmi.camera.029a02`), C200
  (`chuangmi.camera.046c04`) and C301 (`mxiang.camera.c301`), the three models
  physically tested through this native Python integration on 24 October 2026.
- English translations match `strings.json`, including `auto_update_ip`.
- Manifest and runtime/frontend/diagnostics version agree at 0.3.10.
- Root and bundled MIT licenses retain both Kosztyk and Alexey Khit attribution.

Documentation now links to the [published videos and review reply](https://github.com/hacs/default/pull/12439#issuecomment-6388692080),
describes automatic IP recovery, and explains the replacement for the closed
catalog PR. The [hardware report](https://github.com/Kosztyk/xiaomi_camera_native/blob/v0.3.10/docs/PTZ_HARDWARE_VERIFICATION_2026-10-24.md)
preserves the exact tested version (v0.3.8), model IDs, timestamps and limits.
Firmware versions were unavailable; no firmware-wide compatibility is claimed.

Seven offline structural tests cover packaging and the review fixes. HACS,
Hassfest and Python validation must pass on the source commit before this
release is published.

No streaming, authentication, PTZ payload or IP recovery behavior changed.
