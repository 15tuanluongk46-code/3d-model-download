# Third-party notices

## Sketchfab Public Downloader

- Upstream: https://github.com/seryi882/sketchfab-downloader-extension
- Copyright: Copyright (C) 2026 seryi882, as stated in the bundled license.
- License: GNU General Public License version 3 or later, as stated in the
  bundled notice.
- Location: `scripts/sketchfab/vendor/sketchfab_downloader_extension/`
- Full license: [LICENSE](scripts/sketchfab/vendor/sketchfab_downloader_extension/LICENSE)

This repository includes a locally modified copy. Modifications made on
2026-10-06 include a headless raw-GLB export path, authenticated localhost
transport, extraction options, diagnostic metadata and regression tests.
Related files include `headless.js`, `lib/export-contract.js`, `lib/pipeline.js`,
`lib/sf-api.js` and `test/export-contract.test.js`. The headless wrapper retains
the extension's original ZIP export path for extension users. Upstream notices
and license text are preserved; this notice does not relicense upstream code.

## External Meshy/Rodin helper

`meshy-rodin-download` is a separately installed dependency, not vendored here.
Its own `THIRD_PARTY_NOTICES.md` covers its upstream components.

## Downloaded assets

Model licenses belong to their respective creators and are recorded in download
metadata when available. Software notices do not grant rights to downloaded
models. Downloaded models are not included in this repository.
