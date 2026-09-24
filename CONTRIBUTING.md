# Contributing

Contributions are welcome when they preserve the Maya 2022/Python 3.7.7
compatibility target and can be release-tested in Autodesk Maya 2027. Maya
2025 results in older verification records are historical, not current-run coverage.

## Development setup

1. Install Maya 2022 or newer in Python 3 mode. Use the patched CAST v2.01
   files under `third_party/cast`; Maya 2027 on Windows is the current release
   verification environment.
2. Load the toolkit entry directly from the source checkout's `plug-ins`
   directory. `cod_viewmodel_cast_backend.py` resolves `third_party/cast`;
   no third-party file copies or separate CAST installation are needed.
3. Keep workflow changes in `viewmodel_weapon_toolkit.py`, backend identity and
   lifecycle in `cod_viewmodel_cast_backend.py`, and documented upstream
   translator patches in `third_party/cast/castplugin.py`.
4. Keep `attach_gun.py` as a compatibility loader only.
5. Check all Python files against Python 3.7 syntax and run
   `python tests/verify_vendored_cast.py` followed by
   `mayapy tests/verify_plugin_identity.py` before opening a pull request.
   Backend changes also need `verify_private_cast_backend.py`,
   `verify_cast_v201.py` and `verify_animation_read_session.py` under `mayapy`,
   plus the relevant single/dual, drop and export regression paths.

Keep `third_party/cast/cast.py` identical to the shared upstream v2.00/v2.01
serializer; v2.01 did not change it. Any change to
`castplugin.py` must update `third_party/cast/PATCHES.md`, the integrity test,
and the copied upstream license when applicable. Never commit `cast.cfg`.

The Maya release layout puts `cast.py` and `castplugin.py` under
`plug-ins/cod_viewmodel_cast`, not at the plugin-directory top level. The
private translator is `CoDToolkitCast`; do not resolve it through an external
`castplugin`, mutate an external CAST module, or use its persisted preferences.
GUI and batch must use the same backend. Use operation contexts for settings,
parsed documents and animation targets; never retain scene/API objects across
clips. Keep Maya API work on the main thread.

Blender retains its patched CAST v2.00 backend under `third_party/cast_blender`.
The 3.5.0 Blender package version is synchronized; its import/export algorithms
have not been upgraded to CAST 2.01.

For performance changes, compare an immutable baseline with the candidate and
check output equivalence. Distinguish parse-count reductions from measured
elapsed-time improvements; do not promise a universal percentage. See
`docs/CAST_BACKEND_BENCHMARK.md` for the current methodology and
`docs/CAST_BACKEND_RESEARCH.md` for the integration rationale.

Do not commit proprietary game assets, exported models, animation files,
personal paths, Maya preferences, or generated verification scenes. Describe
asset-dependent reproduction steps without attaching copyrighted inputs.

Pull requests should explain the affected workflow, Maya version, CAST plugin
version, expected result, actual result, and verification performed.
