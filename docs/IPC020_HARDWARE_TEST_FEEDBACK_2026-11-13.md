# `chuangmi.camera.ipc020` field-test feedback — 13 November 2026

**Source:** Independent user report for private integration ZIP v0.3.14b2 on
Home Assistant 2026.11.1; camera firmware `4.0.9_0102`, China (`cn`) account.
This is owner testimony, **not** an independently reviewed recording.

## Confirmed in reported setup

- Legacy `/device/devicepass`: `legacy_p2p_credentials_available`.
- Transport `tutk+udp` on SDK-reported TUTK/18, signed authorization.
- Candidate media commands: `audio:ack,video:ack,quality:ack`.
- H.265 video received in 1920×1080; valid timestamped snapshot.
- Three of three cold starts worked; first HLS segment after approximately
  5–10 seconds, without reconnects or Home Assistant log errors.
- `ipc020_tutk_video_packets`: 3,100 first session, 5,873 latest session;
  `ipc020_tutk_malformed_packets`: zero. Drop counter first session 76,
  latest session zero; this is an **internal drop counter**, not a network
  packet-loss measurement.
- Reported successful physical movements using opt-in `0xF005`:
  right 1/1, left 2/3, down 1/2, up 0/2. A suspected upper travel limit
  was not verified. No motor-position feedback exists.

## Limitations and next step

Transport-only `0x71` acknowledgements were not correlated to a specific
motor request in b2; previous ACKs could be mistaken for success, and the
shared sender could retry motor commands up to three times. The new private
b3 test changes **only acknowledgement interpretation and motor retry policy**:
TUTK/18 responses must match the sequence and echoed request ID, and a motor
press produces one datagram regardless of acknowledgement. It also exposes
sanitized PTZ diagnostic counters. No PTZ direction mapping, media-start,
codec, cloud provisioning, camera model allowlist or official release is changed.

We **do not claim firmware-wide streaming support or reliable PTZ** based on
these observations. No hardware test of the b3 changes has been reported yet.
