# Third-party notices

## CAST

Maya Viewmodel Weapon Toolkit interoperates with the CAST serializer and Maya
translator from [dtzxporter/cast](https://github.com/dtzxporter/cast).

- Copyright (c) 2020 Nick
- License: MIT
- Upstream license: <https://github.com/dtzxporter/cast/blob/v2.00/LICENSE>

The repository includes `third_party/cast/cast.py` and a modified
`third_party/cast/castplugin.py`, derived from upstream release v2.00 at
commit `a8ca18a0acf3b97b19332c53b54b47fcc3217755`. Release archives place these
files beside the toolkit in their `plug-ins` directory. The upstream MIT
license is reproduced at `third_party/cast/LICENSE`; local changes and source
hashes are documented in `third_party/cast/PATCHES.md`.

The bundled translator is project-maintained and is not an official upstream
CAST build. `cast.cfg`, which stores user preferences, is not distributed.

Autodesk Maya is a product of Autodesk, Inc. This project is independent and
is not affiliated with or endorsed by Autodesk.
