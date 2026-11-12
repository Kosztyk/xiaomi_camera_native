# Xiaomi Camera Native v0.3.11 — experimental ip029a compatibility build

This is a testable integration package, **not a claim of hardware verification**.

- Identify `chuangmi.camera.ip029a` as **Xiaomi Smart Camera PTZ Version 2K (China)**.
- Preserve generic MISS/CS2 streaming, without adding go2rtc or changing packet handling.
- Offer an **off-by-default, per-camera experimental PTZ switch** for `ip029a` only.
- With user opt-in, expose the existing left/right/up/down buttons using the same encrypted MISS `0x112` one-step motor command.
- Keep previously hardware-verified PTZ models unchanged and enabled as before.
- Expose `pan_tilt_experimental` in camera attributes and diagnostics to help testers report results.
- Extend English labels, documentation and offline tests.

Physical `ip029a` video and PTZ tests are still required. Do not report it as verified until an owner observes physical movement. No changes to streaming/authentication/CS2 commands or frontend JavaScript.
