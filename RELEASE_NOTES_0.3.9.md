# Xiaomi Camera Native v0.3.9 — HACS review fixes

Addresses requested changes in [hacs/default #12439](https://github.com/hacs/default/pull/12439).

- Document physical PTZ testing via this Python Home Assistant integration
  for Mi 360 2K, C200 and C301. The existing three-model whitelist is unchanged.
- Restore the auto_update_ip options label by syncing en.json and strings.json.
- Align const.py VERSION and manifest at 0.3.9.
- Align root/bundled MIT license, preserving Kosztyk and Alexey Khit attribution.
- Add regression checks for the reviewer issues.

See [hardware verification](https://github.com/Kosztyk/xiaomi_camera_native/blob/v0.3.9/docs/PTZ_HARDWARE_VERIFICATION_2026-10-24.md).
The three screen recordings were subsequently published in the
[review reply on HACS PR #12439](https://github.com/hacs/default/pull/12439#issuecomment-6388692080).
No camera protocol, authentication, video, or motor-command behavior changed.
