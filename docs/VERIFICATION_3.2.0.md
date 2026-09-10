# 3.2.0 verification

Verified on Windows, Maya 2025 / Python 3.11.4. The runtime checks use the
project-patched CAST 2.00, including when run directly from the source tree.

## Automated checks

- `verify_vendored_cast.py`: source hashes, local patch markers, Python 3.7 syntax.
- `verify_plugin_identity.py`: version 3.2.0, English/Chinese and legacy loaders.
- `verify_reference_pose_compensation.py`: compensation and persisted metadata.
- `verify_cast_v200.py`: normalized numeric, keyword, hyphen and whitespace
  joint names in single/dual animation workflows; ambiguous names rejected
  before scene modification.
- `verify_batch_animation_export.py`: MA/CAST/SMD/FBX, two single clips, four
  dual jobs, isolation, failure continuation, cancellation, export round trips.
- `verify_ui_accessibility.py`: eight English/Chinese single/dual builder/batch
  screens in interactive Maya. Checks 560/760 pixel widths, no horizontal
  scrolling, labels and browse accessible names, minimum field font size,
  expanded sections, and complete visibility of focused enabled fields.
  Includes the queue callback tests from `verify_batch_animation_ui.py`.
- `verify_release_package.py`: each assembled language package in a clean
  Maya profile, bundled CAST path/version/hashes, commands and localization.

## Native UI inspection

Representative English and Chinese screenshots were inspected at both widths,
including expanded sections. Primary actions remain outside the scroll area;
unchecked output folders remain disabled without losing their saved values.
Maya's explicit control fonts have a 10-point minimum. Keyboard focus scrolls
the whole field into view, not only the line-edit text area.

This is targeted native-widget verification, not a complete screen-reader or
OS high-DPI certification. Maya 2022 and non-Windows runtime tests were not run.

To reproduce UI checks, launch interactive Maya with an isolated `MAYA_APP_DIR`,
set `VWT_UI_QA_DIR` to a report directory, and run this in its Python tab:

```python
import runpy
runpy.run_path("<checkout>/tests/verify_ui_accessibility.py", run_name="__main__")
```

The test writes JSON/PNG results and exits that Maya session. Do not run it in
a session containing unsaved work.
