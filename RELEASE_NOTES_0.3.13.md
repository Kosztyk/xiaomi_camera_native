# Xiaomi Camera Native v0.3.13 — Rediscover device cleanup

- Fix orphaned/empty camera devices left in Home Assistant after a camera is
  deselected via Options → Rediscover. Clean up device registry records and
  this integration's camera and PTZ button entities after a successful reload.
- Add `async_remove_config_entry_device` so existing orphaned devices may also
  be deleted through the Home Assistant device page. Still-configured cameras
  are protected: remove them using Rediscover first.
- Drop stream/PTZ option profiles belonging to deselected cameras; keep the
  retained cameras' options unchanged.
- Keep all four hardware-verified PTZ models, including
  `chuangmi.camera.ip029a`, exactly as in v0.3.12.

No changes to CS2 transport, MISS PTZ commands, FFmpeg, credentials, or video.
Hardware/runtime cleanup must still be tested on Home Assistant; bundled
regression tests run without a Home Assistant instance.
