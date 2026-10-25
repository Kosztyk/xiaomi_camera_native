# Changelog

## 0.3.10 — HACS resubmission documentation

- Link the three published PTZ recordings and review reply from the README,
  validation document and hardware report; remove stale upload instructions.
- Document the existing automatic camera IP recovery option and attributes.
- Update HACS publishing guidance for the closed #12439 and its replacement.
- Correct NOTICE and testing documentation to describe the seven shipped
  structural checks without claiming absent protocol/lifecycle test suites.
- Align manifest, runtime version, NOTICE, packaging checks and guarded release
  workflow at 0.3.10; retain every v0.3.9 review fix.

The tested motor implementation and three-model PTZ allowlist are unchanged.
No streaming, authentication, command payload or IP recovery behavior changed.

## 0.3.9 — HACS review fixes

- Document physical PTZ tests through Xiaomi Camera Native's Python control
  path on the three exactly whitelisted camera models (2026-10-24).
- Preserve the three-model PTZ whitelist; enable no additional models.
- Sync English translations to strings.json, restoring the auto_update_ip label.
- Align frontend/diagnostics VERSION and manifest on 0.3.9.
- Match root MIT license to bundled license with Kosztyk and Alexey Khit
  attribution and preserve NOTICE.
- Add static reviewer regression tests, and guarded release workflow.

No changes to command payloads, streaming, authentication or IP recovery.

## 0.3.8 — HACS publication preparation

- Add missing `documentation` and `issue_tracker` manifest fields.
- Normalize the display name in `hacs.json`.
- Add HACS, Hassfest and offline packaging validation workflows.
- Add basic packaging tests and a validation-status document.
- Clarify HACS installation, fix links in README and remove references to
  absent test files and development utilities.
- Preserve all existing Xiaomi streaming, cloud login, camera, PTZ and
  frontend implementation files unchanged.

This is a packaging/documentation update, not a camera protocol fix.
