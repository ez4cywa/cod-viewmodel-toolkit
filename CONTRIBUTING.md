# Contributing

Contributions are welcome when they can be tested in Autodesk Maya 2025.

## Development setup

1. Install Maya 2025 and the CAST Maya translator version 1.99 or newer.
2. Place the files from `plug-ins` on `MAYA_PLUG_IN_PATH`.
3. Make focused changes in `viewmodel_weapon_toolkit.py`.
4. Keep `attach_gun.py` as a compatibility loader only.
5. Run `mayapy tests/verify_plugin_identity.py` before opening a pull request.

Do not commit proprietary game assets, exported models, animation files,
personal paths, Maya preferences, or generated verification scenes. Describe
asset-dependent reproduction steps without attaching copyrighted inputs.

Pull requests should explain the affected workflow, Maya version, CAST plugin
version, expected result, actual result, and verification performed.
