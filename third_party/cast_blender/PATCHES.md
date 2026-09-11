# Bundled CAST Blender backend

Baseline: [dtzxporter/cast v2.00](https://github.com/dtzxporter/cast/releases/tag/v2.00),
commit `a8ca18a0acf3b97b19332c53b54b47fcc3217755`, directory `plugins/blender`.
Copyright (c) 2020 Nick; MIT license reproduced at `../cast/LICENSE` in the
source tree and at `vendor_cast/LICENSE` in the Blender ZIP.

| File | Upstream SHA-256 | Bundled SHA-256 |
| --- | --- | --- |
| `__init__.py` | `27e7d89379e7bee8b8e538f281435aca73b838405c3ea82e5cf6cde7b1d269a0` | same |
| `import_cast.py` | `4f77ccc65d2cf12132ef634f2368e1a8b1bce5b37cb2a418e95d84f80b049c24` | `5ca3055e4933aa92178a1bf159f6cb219a27f2822568c495efbdf8b77590c6d0` |
| `export_cast.py` | `a301b72f05f454bf7545119060919a71e76d7a3d95305be5380a825747d7784d` | `d62c9b2698e3e0f6619311fdacf1959105f25c36a48d9407bb2bd3fbca1e54c1` |
| `shared_cast.py` | `8f65cc1a4ee055127ecd202c65a10db2e3ceb3ba8d9273ca08888d3d4b9645ed` | same |

The shared `cast.py` serializer is unmodified upstream v2.00, SHA-256
`d1ff7fcb2a184f208b21be34485d1863834ae33811078a28a2ccf6ff61f2c577`.
It is stored in `third_party/cast` and included in each runtime package.

## Local changes

1. `importModelNode` returns its created armature. For a combined model and
   animation CAST, the importer targets the newly created sole armature, not
   the pre-existing selection. Multiple new animation targets are rejected.
2. Model export writes segment-scale compensation from `bone.inherit_scale`
   so a model/animation round trip preserves that skeleton behavior.

The toolkit loads these modules under its own private package without running
upstream `register()`. Upstream initialization source is kept for provenance,
not used to claim global CAST operator IDs. Routing, assembly, sampled action
composition, scoped exports and the temporary FBX numerical adapter are
toolkit code under `blender/cod_viewmodel_toolkit`, not upstream modifications.
This is a project-patched backend, not an official upstream CAST distribution.
