# Xiaomi Camera Native v0.3.15

## Xiaomi cloud setup recovery

Home Assistant can recover from the cached-session HTTP 426 that left
Xiaomi Camera Native in **Setup retry**. When the response has no `Upgrade`
header, the integration uses the stored passToken to renew the Xiaomi session
and verifies it with a device-list request before saving the credentials.
After an attempt, another refresh is eligible after a one-minute cooldown.
[Issue #6](https://github.com/Kosztyk/xiaomi_camera_native/issues/6)

The reporter confirmed recovery on the China server with two `ip029a` cameras
and one `ipc020` using `v0.3.15b3` with diagnostics disabled. Snapshots, live
view and movement controls worked after restart. The production build uses
the same standard API and removes the beta cloud probes and debug logs.
[Reporter confirmation](https://github.com/Kosztyk/xiaomi_camera_native/issues/6#issuecomment-7097265445)

## Upgrade

Update through HACS or copy `custom_components/xiaomi_camera_native` from the
release archive into your Home Assistant configuration directory, then restart
Home Assistant. Existing Xiaomi accounts, selected cameras, and camera options
are used automatically.
