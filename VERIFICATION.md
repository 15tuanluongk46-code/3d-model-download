# Handoff verification — 2026-10-07

Baseline `8b546bf0c85f5028afbfc40ddcc70134fcd4fd4f`; isolated Linux clone,
Python 3.12.3, Node 22.23.2.

- PASS: `python3 -B -m unittest discover -s tests -v` — 34 tests.
- PASS: `npm --prefix scripts/sketchfab/vendor/sketchfab_downloader_extension test`
  — 205 tests; no npm dependencies needed for this test script.

NOT RUN: live downloads, authenticated Meshy/Rodin, visual inspection of newly
downloaded models and native Windows. `meshy-rodin-download` is an external helper,
not bundled here; clone alone does not enable that feature. A structurally valid
GLB does not by itself prove correct materials, pose or animations.

**Verdict: offline tests passed; source-specific live integrations unverified.**
