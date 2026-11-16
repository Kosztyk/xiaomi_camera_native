# `chuangmi.camera.ipc020` hardware feedback — 14 November 2026

**Source:** Volunteer's own report using **private v0.3.14b3** integration
ZIP on the IMILAB Outdoor N Series (IPC025A01), firmware `4.0.9_0102`;
Home Assistant 2026.11.1, Xiaomi account region `cn` (from previous report).
No maintainer-reviewed video was supplied. No other firmware is validated.

## Streaming

- Direct TUTK+UDP, signed authentication, SDK-reported `TUTK/18`.
- Media negotiation `audio:ack,video:ack,quality:ack`; H.265 source.
- 5,300 video frames; 0 dropped, 0 malformed, 0 reconnects; no error.
- Prior b2 test confirmed valid 1920x1080 snapshots and 3/3 cold starts.

## Motor movement (b3, TUTK IOCtrl 0xF005)

| Direction | Observed physical movement | Matching ACKs | ACK timings |
| --- | --- | --- | --- |
| Left | 3/3 | 3/3 | 6, 3, 4 ms |
| Right | 3/3 | 3/3 | 5, 14, 6 ms |
| Down | 0/3 | 3/3 | 6, 4, 4 ms |
| Up | 0/3 | 3/3 | 4, 13, 4 ms |

Across all commands, unmatched ACKs 0, inbound app responses 0,
`last_control=transport_ack_only`, and `last_ptz_error=null`.
Transport ACKs do **not** confirm physical motion.

## Hardware capability verified in official app

The user subsequently confirmed that the Xiaomi Mi Home application exposes
**left and right only** for this exact camera; **up/down movement is not offered**.
The unit is mounted tightly between the garage roof and a wall, so the user
could not center it in Mi Home. Vertical snapshots in b3 remained unchanged.
An earlier b2 observation of occasional apparent down movement was not
replicated and should **not** be treated as evidence of a vertical motor.

## Design decision — private b4

- Retain the native direct-LAN TUTK streaming and b3 ACK/single-write fixes.
- `ipc020` supports only left/right controls when both experimental options
  are enabled; reject up/down at session and protocol layers.
- Remove obsolete b2/b3 Up/Down entity-registry rows for this model after a
  successful setup, without touching video, horizontal buttons or other entries.
- Hide unsupported arrows in the camera popup, not merely disable them.
- Preserve all four motor directions on the existing verified CS2 models.
- Do not publish or assert independent physical testing of b4.
