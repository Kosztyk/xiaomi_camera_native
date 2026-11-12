# Xiaomi Camera Native v0.3.12 — ip029a hardware-verified PTZ

Promotes the Chinese Xiaomi Smart Camera PTZ Version 2K (`chuangmi.camera.ip029a`) from an opt-in field test to the **hardware-verified PTZ allowlist**.

- A v0.3.11 owner report confirms **physical movement in all four directions** (left, right, up, down) on **one `ip029a` camera**, including repeated button presses and no reported errors.
- **Two `ip029a` cameras streamed video**, but PTZ movement on the second camera was **not tested**. Tested environment: Home Assistant 2026.11.1, Xiaomi China (`cn`) region, CS2/UDP, H.265 source transcoded to H.264.
- Native `button.*` PTZ controls now appear **automatically**, without the experimental option. Existing profiles saved with that option set to either true or false still receive verified PTZ controls.
- The experimental PTZ opt-in is no longer offered for `ip029a`; there are currently no other opt-in experimental PTZ models.
- Adds [the user-supplied verification report](docs/PTZ_HARDWARE_VERIFICATION_2026-11-12_ip029a.md), refreshed compatibility documentation and regression checks.

**Unchanged:** MISS `0x112` motor command and directional mapping, CS2/UDP and CS2/TCP transport, encryption, cloud provisioning, video decoding/transcoding, camera session management and frontend JavaScript.

**Evidence limit:** User-reported movement on one camera rather than an independently reviewed recording; other firmware/hardware revisions and the second camera's PTZ remain unverified. No on-device testing of this v0.3.12 package was performed here.
