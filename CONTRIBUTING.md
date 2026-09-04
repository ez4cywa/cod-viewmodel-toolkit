# Contributing

Contributions are welcome when they preserve the Maya 2022/Python 3.7.7
minimum runtime and can be release-tested in Autodesk Maya 2025.

## Development setup

1. Install Maya 2022 or newer in Python 3 mode. Use the patched CAST v1.99
   files under `third_party/cast`; Maya 2025 on Windows is the release
   verification environment.
2. Place the files from `plug-ins` plus `third_party/cast/cast.py` and
   `third_party/cast/castplugin.py` together on `MAYA_PLUG_IN_PATH`.
3. Make focused changes in `viewmodel_weapon_toolkit.py`.
4. Keep `attach_gun.py` as a compatibility loader only.
5. Check all Python files against Python 3.7 syntax and run
   `python tests/verify_vendored_cast.py` followed by
   `mayapy tests/verify_plugin_identity.py` before opening a pull request.

Keep `third_party/cast/cast.py` identical to upstream v1.99. Any change to
`castplugin.py` must update `third_party/cast/PATCHES.md`, the integrity test,
and the copied upstream license when applicable. Never commit `cast.cfg`.

Do not commit proprietary game assets, exported models, animation files,
personal paths, Maya preferences, or generated verification scenes. Describe
asset-dependent reproduction steps without attaching copyrighted inputs.

Pull requests should explain the affected workflow, Maya version, CAST plugin
version, expected result, actual result, and verification performed.
