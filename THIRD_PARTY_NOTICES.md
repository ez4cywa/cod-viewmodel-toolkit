# Third-party notices

## CAST

CoD Viewmodel Toolkit interoperates with the CAST serializer and Maya/Blender
translators from [dtzxporter/cast](https://github.com/dtzxporter/cast).

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

The Blender backend in `third_party/cast_blender` uses the same v2.00 commit.
Its baseline and local changes are recorded in `third_party/cast_blender/PATCHES.md`.
Blender archives include this backend, the unmodified shared serializer and
the upstream MIT license inside `cod_viewmodel_toolkit/vendor_cast`.

Blender itself and its built-in FBX add-on are not redistributed. The toolkit
calls Blender's built-in FBX exporter and temporarily substitutes its
quaternion-to-Euler conversion during that call; the original function is
restored even on failure. This adapter is not an upstream CAST modification.

Autodesk Maya is a product of Autodesk, Inc. This project is independent and
is not affiliated with or endorsed by Autodesk.
