# Third-party notices

## CAST

CoD Viewmodel Toolkit interoperates with the CAST serializer and Maya/Blender
translators from [dtzxporter/cast](https://github.com/dtzxporter/cast).

- Copyright (c) 2020 Nick
- License: MIT
- Upstream license: <https://github.com/dtzxporter/cast/blob/v2.01/LICENSE>

The repository includes `third_party/cast/cast.py` and a modified
`third_party/cast/castplugin.py`, based on upstream release v2.01 at
commit `363cb39c0425844e29bf4c2457bbbb1d2b9bb4c6`, with the project's existing
local patches retained. The serializer is unchanged between v2.00 and v2.01.
Maya release archives place these files in the private `plug-ins/cod_viewmodel_cast`
directory, loaded through `cod_viewmodel_cast_backend.py`. They do not replace an
independently installed CAST translator or its preferences. The upstream MIT
license is reproduced at `third_party/cast/LICENSE`; local changes and source
hashes are documented in `third_party/cast/PATCHES.md`.

The bundled translator is project-maintained and is not an official upstream
CAST build. `cast.cfg`, which stores user preferences, is not distributed.

The Blender backend in `third_party/cast_blender` remains based on v2.00 commit
`a8ca18a0acf3b97b19332c53b54b47fcc3217755`; its algorithms are unchanged in the
toolkit 3.5.0 release.
Its baseline and local changes are recorded in `third_party/cast_blender/PATCHES.md`.
Blender archives include this backend, the unmodified shared serializer and
the upstream MIT license inside `cod_viewmodel_toolkit/vendor_cast`.

Blender itself and its built-in FBX add-on are not redistributed. The toolkit
calls Blender's built-in FBX exporter and temporarily substitutes its
quaternion-to-Euler conversion during that call; the original function is
restored even on failure. This adapter is not an upstream CAST modification.

Autodesk Maya is a product of Autodesk, Inc. This project is independent and
is not affiliated with or endorsed by Autodesk.
