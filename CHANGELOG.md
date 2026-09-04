# Changelog

All notable changes to this project are documented here.

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

The version remains 3.0 for the product rename and publication preparation.
