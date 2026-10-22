# Publishing Xiaomi Camera Native to HACS

Repository: https://github.com/Kosztyk/xiaomi_camera_native

## 1. Merge this PR

Merge the HACS publication PR only after checks succeed. No camera protocol,
PTZ, streaming or authentication implementation changes are included.

## 2. Fix GitHub repository topic (metadata, not versioned file)

In GitHub: repository home page > About > Topics, replace
`homeassistant-integraiton` with `homeassistant-integration`.

## 3. GitHub Actions

Open https://github.com/Kosztyk/xiaomi_camera_native/actions

Confirm **HACS Validation**, **Hassfest Validation**, and **Packaging and
Python checks** are successful. Address any findings before releasing.

## 4. GitHub Release

After the checks pass and the PR is merged, create a full release (not only
a tag) with tag `v0.3.8`, targeting the merged commit.
Use `RELEASE_NOTES_0.3.8.md` as the release description.

## 5. Test HACS custom repository installation

HACS > three-dot menu > Custom repositories > paste:

https://github.com/Kosztyk/xiaomi_camera_native

Select **Integration**, install, restart HA and configure the integration.

## 6. Request inclusion in default HACS catalog

- Fork https://github.com/hacs/default
- In a new branch based on `master`, add `"Kosztyk/xiaomi_camera_native"`
  into its `integration` JSON file in alphabetical order.
- Create a PR toward `hacs/default:master` and follow the template.

Reference: https://www.hacs.xyz/docs/publish/include/
