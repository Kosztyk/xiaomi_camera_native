# Changelog

## 0.3.16 — Mi 360 Home Security Camera 2K Pro pan and tilt

- Enable left, right, up and down on `chuangmi.camera.021a04` through the
  Home Assistant device buttons and camera popup. The owner confirmed physical
  movement over MISS/CS2 with a Europe (`de`) account. [Issue #7](https://github.com/Kosztyk/xiaomi_camera_native/issues/7)
- Show **Mi 360 Home Security Camera 2K Pro** as the model name in Home Assistant.

## 0.3.15 — Xiaomi cloud setup recovery

- Recover when Xiaomi rejects the cached session with HTTP 426 and sends
  no `Upgrade` header. Sign in with the stored passToken and verify the
  renewed session before saving it. [Issue #6](https://github.com/Kosztyk/xiaomi_camera_native/issues/6)
- Rate-limit account refreshes so Home Assistant can retry after a temporary
  Xiaomi login or API failure.
- Remove the beta cloud probes and integration debug logging. Routine camera
  warnings identify the model instead of the device ID.

## 0.3.14 — IMILAB ipc020 and streaming reliability

- Add opt-in direct TUTK LAN video for `chuangmi.camera.ipc020`, with a
  separate provisioning path for cameras affected by Xiaomi MISS error `-6`.
- Add optional left/right movement for `ipc020` once live video is ready.
  The device page and popup show only supported directions. Old beta tilt
  entities are cleaned up during setup.
- Recover changed TUTK camera IPs, pin the UDP peer after the handshake and
  share service-token refresh across concurrent provisioning requests.
- Limit snapshot dimensions, refuse authenticated API redirects and reap
  FFmpeg when an encoder session is cancelled.
- Cap queued media by bytes, speed up MPEG-TS packetization and recover
  after source codec changes or missing packets on the TUTK 25+ path.
- Use current Home Assistant device-registry ownership fields with an
  older-version fallback. [ipc020 setup and evidence](docs/IPC020.md)

## 0.3.14b6 — Private security and streaming test

- Limit requested snapshot sizes to 4,096 pixels per side and 8,847,360
  pixels total before starting FFmpeg.
- Reject redirects from authenticated Xiaomi API requests.
- Reap the FFmpeg encoder during cancellation and keep its pipes draining
  until it exits.
- Packetize MPEG-TS frames in linear time and cap transport and viewer
  queues by payload bytes.
- Recover TUTK 25+ streams after packet loss and restart the video pipeline
  when the source switches codecs.
- Use the current Home Assistant device ownership field with a fallback for
  older device registries.

## 0.3.14b5 — Private ipc020 recovery test

- Recover a changed TUTK camera IP through the existing router and Xiaomi
  discovery resolver. Save a recovered address after the camera handshake.
- Refresh an expired Xiaomi service token once and retry TUTK provisioning.
  Concurrent provisioning requests share a successful account refresh.
- Confirm the UDP peer during the handshake and use it for the live session.
- Enable horizontal pan once the current TUTK session receives video.
- Publish the motor ACK outcome immediately, including timeouts and aborted sends.

## 0.3.14b4 — PRIVATE ipc020 horizontal-pan-only test (unpublished)

- Owner reported stable TUTK/18 H.265 streaming in b3 and **6/6 physical
  horizontal movements**. Mi Home offers **left/right only** for this camera.
- Expose Left and Right buttons on the `ipc020` test model; suppress Tilt Up
  and Down. Reject any vertical TUTK motor command before sending it.
- Remove obsolete Up/Down Home Assistant entity-registry records on reload
  for configured `ipc020` cameras, without removing the camera device or
  affecting other models or configuration entries.
- Hide unsupported directional arrows entirely in the camera popup; maintain
  four arrows for the four existing hardware-verified CS2 models.
- Add `pan_tilt_directions` capability to safe camera attributes/diagnostics.
- Preserve b3 ACK matching, no motor retries and all streaming/CS2 code.
- Include dated owner hardware evidence and offline regression tests.
- This private test required both the TUTK and horizontal-pan opt-ins.

## 0.3.14b3 — PRIVATE ipc020 PTZ acknowledgement reliability test (unpublished)

- Based on experimental b2, which a volunteer confirmed working for
  `ipc020` 1080p H.265 TUTK/18 streaming on 2026-11-13.
- Match TUTK/18 PTZ ACKs to both request sequence and request ID. Ignore
  stale ACKs; never infer physical motor movement from transport ACKs.
- Send a **single** `0xF005` motor request per press, without transport retries.
  Existing audio/video/quality initialization retries are unchanged.
- Record safe PTZ sequence, ACK correlation state, ACK elapsed milliseconds,
  unmatched-ACK count and inbound `0xF005` message count. No secrets exposed.
- Add b3 packet regression tests and a dated hardware-feedback report.
- PTZ remains opt-in and hardware verification of the b3 change is pending.
  Official published GitHub/HACS release remains v0.3.13.


## 0.3.13 — safe device removal after Rediscover

- Automatically prune device- and entity-registry records for Xiaomi cameras
  deselected in Rediscover once the remaining camera platforms have loaded.
  This also cleans up already-orphaned records after restart/reload.
- Implement `async_remove_config_entry_device` to permit deleting an orphaned
  camera from the Home Assistant device page. Active/selected cameras and
  devices belonging to other integration entries cannot be removed this way.
- Remove saved profiles for deselected cameras so re-adding them starts with
  clean defaults. Preserve the other cameras' profiles.
- Add offline regression tests for active-camera protection, orphan removal,
  foreign/shared-device protection, PTZ entity cleanup and repeat cleanup.
- No changes to Xiaomi transport, provisioning, stream handling or PTZ commands.


## 0.3.12 — `ip029a` PTZ promoted after hardware test

- Promote `chuangmi.camera.ip029a` into the verified PTZ model allowlist.
  All four step buttons are now available without the prior experimental switch.
- Record owner-reported physical left/right/up/down movement on **one**
  `ip029a` camera, confirmed working repeatedly on v0.3.11, plus video on
  two same-model cameras using China (`cn`) region (HA 2026.11.1).
- Keep saved experimental-option profiles compatible, while hiding the
  opt-in control for the now-verified model. No other models gain access.
- Add evidence and updated offline regression tests. Keep streaming and
  MISS `0x112` motor command implementations unchanged.

## 0.3.11 — experimental Chinese `chuangmi.camera.ip029a` support

- Recognize the Chinese Xiaomi Smart Camera PTZ Version 2K model ID.
- Expose native PTZ step buttons for this model **only after explicit opt-in**
  in its camera options. Default is disabled and verified models are unchanged.
- Keep MISS 0x112 motor commands, CS2 transport, stream decoding and Xiaomi
  cloud provisioning unchanged; streaming/PTZ remain unverified on ip029a.
- Add a diagnostic flag, English UI strings, compatibility instructions,
  regression checks, and align packaging/release metadata with 0.3.11.


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
