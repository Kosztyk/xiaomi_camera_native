# Xiaomi Camera Native v0.3.14

## IMILAB outdoor PTZ support

- Adds local TUTK/UDP streaming for the China-region IMILAB outdoor PTZ
  camera `chuangmi.camera.ipc020`. This gives the model a provisioning path
  when Xiaomi's MISS endpoint returns code `-6`.
- Adds optional Left and Right buttons in the camera popup and device page.
  Pan becomes available after the current stream receives video.
- A tester confirmed signed TUTK/18 streaming and physical movement on
  firmware `4.0.9_0102`, with H.265 input and H.264 output on the b5 build.
  [Setup and hardware results](https://github.com/Kosztyk/xiaomi_camera_native/blob/v0.3.14/docs/IPC020.md)

## Streaming, security and reliability

- Recovers a changed TUTK camera IP and refreshes an expired Xiaomi service
  token during provisioning.
- Rejects redirects on authenticated Xiaomi API requests and checks
  requested snapshot dimensions before starting FFmpeg.
- Reaps the encoder when a stream is cancelled, caps queued media by bytes
  and packetizes MPEG-TS in linear time.
- Recovers after H.264/H.265 source changes and after missing packets on the
  TUTK 25+ path. TUTK 25+ recovery was tested with synthetic packets.
- Uses current Home Assistant device ownership fields for safe cleanup
  after Rediscover, with a fallback for older registries.

## Upgrade

Update Xiaomi Camera Native through HACS or copy the component from this
release's source archive, then restart Home Assistant. Refresh your browser
or reopen the Companion app to load the updated camera popup.

For `ipc020`, open the camera's integration options and turn on **Use TUTK LAN
transport (ipc020)**. Turn on **Enable horizontal pan (ipc020)** to get the
two movement controls. Existing settings from the beta are carried forward.
