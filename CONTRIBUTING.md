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
   translator patches in `third_party/cast/castplugin.py`. Keep standalone
   scene snapshotting, worker lifetime, conversion and final-file publication
   behind the small `cod_viewmodel_exports.py` interface.
4. Keep `attach_gun.py` as a compatibility loader only.
5. Run `python tests/verify_source_contracts.py`, both vendored-backend
   checks and `python tests/verify_build_release.py`. The source check applies
   Python 3.7 syntax to Maya runtime files and the current interpreter's
   syntax to development tools and Blender sources. Then run
   `mayapy tests/verify_plugin_identity.py` before opening a pull request.
   Backend changes also need `verify_private_cast_backend.py`,
   `verify_cast_v201.py` and `verify_animation_read_session.py` under `mayapy`,
   plus the relevant single/dual, drop and export regression paths.
   Metric changes need `verify_metric_module_path.py` against the actual
   registered English/Chinese/legacy core and `verify_maya_units.py`; a second
   ordinary Python import does not reproduce Maya's missing module attributes.
   Output-default changes also need `mayapy tests/verify_optional_outputs.py`.
   Standalone export changes need `python tests/verify_standalone_exports.py`,
   `python tests/verify_standalone_export_ui.py` and
   `mayapy tests/verify_standalone_export_host.py`; use `--plugin <entry-path>`
   for the installed entry or the Chinese/legacy loader.
   CAST gateway changes also need `mayapy tests/verify_cast_import_gateway.py`
   with no external CAST loaded, plus relevant registered-entry/drop tests.

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

Keep menu and enabled external-drop imports behind `import_cast_file` using
the bundled backend. Model-only imports need a real fresh namespace for both
creation and lookup, must not reuse existing materials, and must not attach or
zero bones. Animation-only imports require a valid toolkit assembly and the
existing safe single/dual routing APIs. Reject mixed model/animation or Instance
containers rather than guessing a destination. Rejected, malformed and
multi-file CAST drops must not fall back to another translator while built-in
handling is on. Preserve the existing drag/drop preference key and explicit
opt-out. Ordinary Maya File Import and external translator calls are outside
this gateway; do not document them as protected.

Single/dual/quick builds with all four outputs disabled must remain in-memory:
no output folders, files, JSON reports or metric workers. Preserve non-output
preferences during the one-time defaults migration. Batch APIs still require
at least one explicitly enabled format. Standalone FBX/SMD export must preserve
the live scene and publish only the requested format, using an isolated worker
copy for conversion and animation skinning changes. Existing destinations must
never be overwritten. Static SMD retains attachment validation; animated SMD
may export an ordinary skeleton. MAX export is outside this release's scope.

Blender retains its patched CAST v2.00 backend under `third_party/cast_blender`.
The Blender package version is synchronized; its import/export algorithms
have not been upgraded to CAST 2.01. The 3.6.0 all-off output defaults and
standalone menu tools are Maya-only; Blender's existing defaults remain intact.

Keep release file selection, version checks and archive bookkeeping in
`scripts/build_release.py`. It reads and localizes all inputs before creating
packages, then publishes only a complete successful build. Existing ZIPs must
not be overwritten, and failure cleanup must affect only files this build owns.
The build test runs without Maya/Blender and checks these observable outcomes,
package layouts, localization and deterministic bytes. See the
[release checklist](docs/RELEASE_CHECKLIST.md) for host and publication checks.

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
