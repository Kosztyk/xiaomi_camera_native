# Xiaomi Camera Native v0.3.16

The **Mi 360 Home Security Camera 2K Pro** (`chuangmi.camera.021a04`) now has
**Pan left**, **Pan right**, **Tilt up**, and **Tilt down** in Home Assistant.
The device buttons and popup arrows use the existing MISS/CS2 controls.

The camera owner confirmed physical movement in all four directions from both
interfaces. The test used a Europe (`de`) account on Home Assistant Core
2026.11.3 with Home Assistant OS on a Raspberry Pi 4. Gimigym shared the test
results and patch. [Issue #7](https://github.com/Kosztyk/xiaomi_camera_native/issues/7)

Update through HACS and restart Home Assistant. The controls appear
automatically for this model, including cameras already configured in the
integration. Refresh the browser or reopen the Companion app to load the
updated camera popup.
