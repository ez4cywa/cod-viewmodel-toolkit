# Batch animation verification — 3.1.0

Verified on 2026-09-06 with Windows, Maya 2025 / Python 3.11.4, and the
project-patched CAST 1.99 translator. No CAST runtime source changes were made.

## Automated synthetic regression

`mayapy tests/verify_batch_animation_export.py` passes:

- Two single-weapon clips with different durations/frame rates, the same
  basename, and deliberately different joint-track coverage.
- Two dual pairs in each of simultaneous and sequential modes.
- MA, CAST, FBX, and skeletal SMD output, including independent directories.
- DQS skinning retained after MA, FBX, and CAST reloads.
- Per-frame bone-matrix comparisons for FBX/CAST round trips and decoded SMD;
  FBX/CAST mesh-bound comparisons include multi-influence deformation.
- Non-bind-pose initial rotations and combined-axis rotations. CAST retains
  the assembled rest model; explicit sampling prevents interpolation differences.
- Duplicate removal, same-name versioning, SMD-only selection, zero-format
  rejection, missing/unmatched animation failure, and continuation.
- Injected SMD writer failure: other selected formats succeed, incomplete
  files are not published, and total failure is not reported as partial success.
- Cancellation at a clip boundary and restoration of CAST export preferences.

The fixtures are generated in temporary folders; no game assets are distributed.

## Native interface checks

`tests/verify_batch_animation_ui.py:main()` passes inside interactive Maya
for English/Chinese and single/dual windows. The file picker and export runner
are stubbed here to isolate queue editing, deduplication, pairing, format
selection, and progress/result callbacks. Actual exports are covered above.
The batch progress and cancellation controls remain outside the scrolling form.

## Local asset checks

All four formats succeeded for a single-weapon inspect clip (0–277) and
reload clip (0–49), and for a dual inspect pair (0–325) using both IW8 hands
and Calisto hands with IW8 reference-pose compensation. All clips use 30 fps.
FBX reloads matched the MA attachment-bone matrices at start/middle/end.
Source assets were read only; generated scenes and exports were temporary.

Identity/localization, reference-pose compensation, CAST integrity, Python 3.7
syntax, and whitespace checks also pass. Maya 2022 has not been runtime-tested.
