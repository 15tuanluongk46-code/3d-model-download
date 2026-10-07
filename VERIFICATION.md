# Handoff verification — 2026-10-07

Baseline `8b546bf0c85f5028afbfc40ddcc70134fcd4fd4f`; isolated Linux clone,
Python 3.12.3, Node 22.23.2.

- PASS: `python3 -B -m unittest discover -s tests -v` — 34 tests.
- PASS: `npm --prefix scripts/sketchfab/vendor/sketchfab_downloader_extension test`
  — 205 tests; no npm dependencies needed for this test script.

NOT RUN: live downloads, authenticated Meshy/Rodin, visual inspection of newly
downloaded models and native Windows. At that baseline, `meshy-rodin-download`
was an external helper, not bundled; clone alone did not enable that feature. A structurally valid
GLB does not by itself prove correct materials, pose or animations.

**Verdict: offline tests passed; source-specific live integrations unverified.**

## Bundled-helper follow-up — 2026-10-07

`meshy-rodin-download` is now included under `bundled-skills/`; install both
sibling skills following SETUP.md. All nine bundled files match the installed
helper used for this handoff.

- PASS: main Python suite — 34 tests; vendor JavaScript suite — 205 tests.
- PASS: `python3 -B -m unittest discover -s bundled-skills/meshy-rodin-download/tests -v` — 6 tests.
- PASS: `node --check bundled-skills/meshy-rodin-download/scripts/decrypt.mjs`.
- PASS: `uvx ruff check --no-cache bundled-skills/meshy-rodin-download/scripts bundled-skills/meshy-rodin-download/tests`.
- PASS: SETUP installation snippet in an isolated temporary home: two skills,
  main CLI `--sources`, refusal to overwrite existing destinations.
- NOT RUN: fresh live Meshy/Rodin downloads for this packaging-only update.
