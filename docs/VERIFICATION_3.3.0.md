# 3.3.0 verification

Date: 2026-09-11. Windows; Maya 2025 / Python 3.11.4;
official Blender 5.2.1 LTS build `9e2066aef7ef`.

## Blender synthetic coverage

`tests/verify_blender_toolkit.py` generates its own redistributable fixtures:
single/dual attachment and skinned meshes; simultaneous/sequential playback;
one-side replacement preserving opposite-side poses; all four export formats;
FBX/CAST/BLEND round trips; scoped BLEND scene excluding unrelated objects;
batch `[ok, failed, ok]` continuation without object leakage; cancellation;
injected assembly/action failure rollback; static SMD triangle output;
per-format directories; zero-frame clips; relative reference-pose offset;
UI registration, preflight and queue operators. FBX conversion covers exact
and near ±90° pitch, varied roll/yaw and function restoration on exceptions.

Native 1280×900 Blender screenshots checked single and dual panels in a
280-pixel sidebar. File labels are above path fields to avoid truncation.
These checks do not establish every OS theme or display-scale combination.

## User-provided real single-weapon inputs

- `viewhands_mp_base_iw8_LOD0.cast`
- `att_vm_p27_pi_papa220_rec_v0_LOD0.cast`
- `vm_p27_pi_papa220_fire.cast`

The test assembled 141 viewhands bones and 49 weapon bones: 190 total,
38 frames at 60 FPS. Attachment translation is `(0, 0, 0)` and source-file
hashes were unchanged. Comparisons sampled frames 0, 18 and 37; these are
sampled checks, not an exhaustive per-vertex/per-frame proof.

| Round trip | Max bone-position error | Max bone-matrix component error | Max evaluated mesh-bounds error |
| --- | ---: | ---: | ---: |
| BLEND | 0 | 0 | 0 |
| CAST via patched backend | 0.000038147 | 0.000038147 | 0.005126953 |
| FBX, receiver DQS enabled | 0.000061035 | 0.000345439 | 0.000079602 |
| FBX, default linear receiver | 0.000061035 | 0.000345439 | 1.970546722 |

Distances are in source/scene units. The CAST bounds tolerance was 0.01.
Default linear FBX deformation is **not equivalent** to the source DQS;
enable Preserve Volume in Blender or Dual Quaternion in the receiving DCC.
The scoped numerical adapter improves the near-90° FBX rotation conversion;
it does not eliminate every floating-point difference.

No real dual-animation pair was supplied. Dual ownership/composition is
covered by synthetic fixtures only. Game assets and generated exports are
not redistributed in the repository or ZIPs.

## Maya and reproducibility

Maya changes are product labels/version only. English, Chinese and legacy
entry identity/localization checks pass; the backend bytes remain identical
to 3.2.0. Previous asset coverage is recorded in [3.2.0 verification](VERIFICATION_3.2.0.md).

The Maya reference-pose and batch-animation regression suites also pass;
batch coverage includes single/dual clips, all four formats, failure
continuation, cancellation and round-trip sampling. Both assembled Maya
language ZIPs passed clean package loading and translator hash checks.
The Blender ZIP passed Install from Disk, enable/disable, private-backend
resolution, assembly and four-format export in an isolated script directory.

```powershell
python tests/verify_vendored_cast.py
python tests/verify_vendored_blender_cast.py
mayapy tests/verify_plugin_identity.py
blender --background --factory-startup --python-exit-code 1 --python tests/verify_blender_toolkit.py
blender --background --factory-startup --python-exit-code 1 --python tests/verify_blender_assets.py -- hands.cast weapon.cast animation.cast output-dir
```

The real-asset runner requires local source files. It accepts paths as
arguments and does not embed the user's private directory structure.
