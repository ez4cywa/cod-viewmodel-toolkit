# Changelog

All notable changes to this project are documented here.

## [3.4.3] - 2026-09-24

- Further reduce Maya CAST import buffer allocation without changing UV tables,
  normals, colors, topology or skin weights.
- Reuse parsed documents within one attachment operation and release them on
  success/error; count preflight face health using unique indices for healthy meshes.
- Add alternating 3.4.2/current benchmarks with scene equivalence checks, cache
  lifetime/invalidation checks, and malformed-face diagnostic comparisons.
- See `docs/CAST_IMPORT_OPTIMIZATION.md` for measurements and validation.
- Blender functionality is unchanged; package versions remain synchronized.

## [3.4.2] - 2026-09-23

- Speed up Maya model attachment by writing CAST skin weights in bounded API
  blocks instead of one command per vertex. Preserve influence mapping, duplicate
  influence accumulation, non-normalized weights and rigid-mesh behavior.
- Remove completion dialogs from single, quick, dual and batch attachment.
  Keep error dialogs, partial export failures, and unsaved-scene confirmation.
- Verify Maya 2027 loading, attachment, weights and animation regression paths.
- Blender behavior is unchanged; release versions remain synchronized.

## [3.4.1] - 2026-09-12

- Fix Maya CAST animation drops failing with `NameError: __file__` in the
  registered plugin. Resolve the units module from the recorded plugin path;
  cover single and dual drops without importing a second core module in tests.
- Blender functionality is unchanged; package versions are synchronized.

## [3.4.0] - 2026-09-11

- Optional ft-to-meter output copies for Maya and Blender, with original behavior as the default.
- Native meter scenes, numeric-meter CAST/SMD, correctly sized FBX, conversion reports and repeat-export protection. Maya FBX retains centimeter storage metadata; see `docs/OUTPUT_UNITS.md`.
- Preserve source scenes and foot-valued inputs. Fix Maya repeated clip imports when existing animation curves are reused.

## [3.3.0] - 2026-09-11

- Renamed the cross-platform project to CoD Viewmodel Toolkit, focused on
  Call of Duty first-person CAST workflows. Maya loader filenames, commands
  and saved settings remain compatible.
- Added an independent Blender 5.2+ edition using pinned upstream CAST 2.00:
  single/dual assembly, routed skeletal animation, sequential/simultaneous
  playback, single-side replacement and reference-pose translation compensation.
- Added scoped BLEND/CAST/FBX/SMD exports, per-format directories, versioned
  outputs and cancellable batch queues with per-item failure reports.
- Patched Blender CAST combined-file animation targeting and segment-scale
  export. Added a scoped double-precision FBX rotation adapter for near-90°
  CoD skeleton orientations; documented receiving-side DQS requirements.
- Added native English Blender panels, Chinese/English guides, synthetic
  regressions, real single-weapon round-trip checks and backend hash checks.
- Release ZIPs now identify platform and language: Maya EN, Maya ZH-CN,
  Blender EN. Blender packages do not include or require Maya.

## [3.2.0] - 2026-09-11

- Updated the bundled Maya CAST translator to upstream v2.00, retaining
  batch-mode support, UV fallback, and per-operation option isolation.
- Matched model and animation preflight names to CAST v2.00 normalization;
  fixed hyphen and curve-mode override handling and reject name collisions.
- Resolve the bundled translator in both source checkouts and release packages.
- Unified temporary CAST preference handling and shared native UI builders.
- Grouped source files, joint mapping, output formats, and scene actions;
  added resizable scrolling forms with persistent primary actions.
- Added descriptive accessible names, visible keyboard focus, larger controls,
  wrapping labels, disabled unselected output folders, and queue empty feedback
  in both English and Simplified Chinese.
- Added CAST v2.00 special-name integration and interactive UI regression checks.

## [3.1.0] - 2026-09-06

- Fixed simultaneous one-frame dual animations being rejected after Maya
  expanded the zero-duration time-slider range, while keeping CAST, SMD, and
  FBX exports limited to the real animation frame.
- Rewrote About as a structured capability summary covering single/dual
  workflows, batch/export behavior, DQS, compatibility, and dual-wield scope.
- Added single-weapon animation queues and explicit left/right dual-animation
  pair queues in the English and Simplified Chinese interfaces.
- Added independently selected animated MA, CAST, FBX, and skeletal SMD
  outputs with separate folders, versioned names, progress, and cancellation.
- Use DQS skinning for both batch workflows and preserve it in MA/FBX/CAST.
- Preserve the assembled rest model for animated CAST exports instead of
  rebinding a posed mesh, and explicitly sample multi-axis rotation before
  CAST/FBX conversion while restoring the original scene curves afterward.
- Isolated every clip/pair to prevent leftover keys; record per-format and
  per-item failures without stopping subsequent jobs.
- Preserved dual simultaneous/sequential modes and reference-pose compensation;
  original builder model-export behavior remains unchanged.
- Added generated-fixture Maya regression coverage, including animated FBX
  round trips, queue deduplication, same-name collision handling, and failure continuation.
- Prefer a release package's adjacent CAST translator when no CAST plugin is
  already loaded, allowing self-contained installs without overwriting Maya's
  existing CAST files.

## [3.0.3] - 2026-09-04

- Added optional reference-viewhands rest-pose compensation for dual-wield
  target translation tracks.
- Limited compensation to CAST `relative` and `additive` translation axes;
  absolute tracks, rotations, weapon roots, and skin binding stay unchanged.
- Persisted reference paths and per-side offsets for validation and animation
  replacement while retaining compatibility with older dual-scene metadata.
- Added English and Simplified Chinese UI controls, documentation, and Maya
  regression coverage.

## [3.0.2] - 2026-09-04

- Fixed dual-wield validation rejecting scenes whose rig and animation
  metadata was complete but whose optional output bookkeeping was absent.
- Prevented interrupted dual-wield builds from persisting metadata before
  both weapon sides pass their initial animation and attachment validation.
- Added Maya regression coverage for incomplete dual-output metadata.

## [3.0.1] - 2026-09-04

- Fixed the Simplified Chinese file and folder browsers failing with
  `unhashable type: 'list'` after a selection.
- Limited localized return-value mapping to confirmation dialogs, while
  preserving Maya file-dialog path lists unchanged.
- Added a Maya regression test for localized file-dialog list results.

## [3.0] - 2026-09-03

- Renamed the product to Maya Viewmodel Weapon Toolkit.
- Added the `viewmodelWeaponToolkit` command while retaining `attachGun`.
- Added a legacy `attach_gun.py` loader for existing Maya installations.
- Added duplicated-weapon dual-wield assembly.
- Added simultaneous and sequential left/right animation composition.
- Added per-side animation replacement and persistent dual-scene metadata.
- Added collision-safe CAST animation drag and drop.
- Prevented CAST's global `Import Resets Scene` option from deleting the
  first animation when composing or replacing dual-wield clips.
- Added independently selectable Maya ASCII, CAST, SMD, and FBX outputs.
- Added output validation and JSON manifests.
- Added a separately loadable Simplified Chinese UI entry point backed by the
  same implementation and kept the release version at `3.0`.
- Documented Maya 2022 in Python 3 mode as the minimum compatibility target,
  while retaining Maya 2025, Python 3.11.4, CAST 1.99, and Windows as the
  verified release environment.
- Bundled a documented project-patched CAST Maya translator based on upstream
  v1.99, including its unmodified serializer and upstream MIT license.
