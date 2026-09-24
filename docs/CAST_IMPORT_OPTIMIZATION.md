# Further CAST import optimization — 3.4.3

The toolkit already bundles the upstream CAST 2.00 serializer and a locally
patched Maya translator. These changes extend that integration; no replacement
parser, optional native dependency, or reduced-quality import mode was added.

## Implementation

- Prepare interleaved positions without a Python slice/list for every vertex.
- Build UV arrays directly by face index; do not change UV count, index sharing,
  per-corner values, material creation, normals, colors, skinning or DQS settings.
  Short optional UV buffers retain the prior slice-based path.
- Reuse read-only parsed CAST documents only within a single/dual attachment
  operation. Nested operations share the session. File size, modification and
  change timestamps invalidate an entry; success and exceptions release it.
  A subsequent build and ordinary translator imports read files afresh.
- Inspect unique face indices once on healthy meshes. Invalid inputs still
  count every invalid occurrence and retain existing diagnostics.

Automatic initial skinCluster binding is deliberately unchanged. No scene undo,
evaluation mode, material, skin or validation settings are disabled for speed.

## Measurement and evidence

Windows Maya 2027, Python 3.13.9; source baseline is immutable commit
`e49fd4c76ff221ff175bec4980ff33b21b3fd907` (release 3.4.2).
The user's arms/weapon pair contains 46 skinClusters. Model inputs were not modified.

`tests/benchmark_cast_import.py` alternates baseline/current order, uses a new
scene for each run, and compares scene snapshots outside the timed section.
Both paths preserve topology, positions, normals and normal indices, every UV
table and assignment, vertex colors, material assignments, texture paths/colorspaces,
joint transforms, skin influence weights and skinning method.

Final 3-run attachment samples (seconds):

| Version | Samples | Median |
| --- | --- | --- |
| 3.4.2 | 2.211, 2.216, 2.425 | 2.216 |
| 3.4.3 | 1.684, 1.814, 1.817 | 1.814 |

This was an 18.1% median reduction for preflight + import + attachment, excluding
Maya startup and export. Direct translator imports without toolkit preflight
reuse showed a smaller initial gain (~6%); do not generalize attachment results
to every standalone import or machine. Timings are not deterministic CI gates.

Reproduce with Maya's `mayapy`:

```text
tests/benchmark_cast_import.py --models HANDS.cast WEAPON.cast --runs 3 --attachment
tests/benchmark_cast_import.py --models HANDS.cast WEAPON.cast --runs 3
tests/verify_cast_import_optimization.py
tests/verify_maya_drop_module_path.py
tests/verify_batch_animation_export.py
tests/verify_cast_v200.py
```

The regression tests verify two parser calls rather than four for a single
attachment, multi-layer UV/color equivalence, degenerate-face handling, nested
cache sessions, metadata invalidation, uncached ordinary reads, exception cleanup,
and exact malformed-input preflight reports. Existing single/dual animation,
CAST/FBX/SMD round trips and upstream 2.00 integration checks also passed.

These changes are included in 3.4.3. See [release notes](RELEASE_NOTES_3.4.3.md)
for installation details. Blender behavior is unchanged.
