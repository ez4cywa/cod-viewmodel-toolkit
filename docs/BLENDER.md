# Blender — CoD Viewmodel Toolkit 3.4.1

The 3.4.1 release also offers `cod-viewmodel-toolkit-3.4.1-blender-zh-CN.zip`.
Blender functionality is unchanged from 3.4.0; this patch fixes Maya animation imports.
It localizes the add-on UI without changing Blender's language. English and
Chinese packages share the same module: stop batches and disable the old
edition before installing and enabling the other. Do not load renamed copies
of both editions together. Backend exceptions and JSON technical keys remain
English. Both editions contain identical assembly/export logic.

[简体中文](BLENDER.zh-CN.md) · [Project](../README.md)

Requires Blender 5.2+; verified with official Blender 5.2.1 LTS on Windows.
Earlier Blender versions are not supported by this edition. The Maya edition
remains independent. No game assets, Blender executable or Maya runtime are bundled.

## Install

1. Download `cod-viewmodel-toolkit-3.4.1-blender-en.zip` (English) or `cod-viewmodel-toolkit-3.4.1-blender-zh-CN.zip` (Simplified Chinese).
2. In Blender, open Edit > Preferences > Add-ons > menu > Install from Disk.
   Select the ZIP as a legacy add-on and enable **CoD Viewmodel Toolkit**.
3. In the 3D Viewport press `N`, then select **Viewmodel**.

The archive has an installable `cod_viewmodel_toolkit` root. Its private CAST
backend does not register `import_scene.cast` or `export_scene.cast`, so it
does not replace an independently installed CAST add-on. That separate add-on
is optional and may have different round-trip behavior from our patched backend.
For a source checkout, add the repository's `blender` directory to `sys.path`,
import `cod_viewmodel_toolkit`, and call `register()`.

## Build and animate

Choose Single Weapon or Dual Wield. Select model-only Viewhands CAST and Weapon
CAST files, then optionally select an animation-only CAST (both left and right
clips for dual wield). **Check Inputs** runs without importing; **Build Assembly**
creates a dedicated collection and preserves other scene objects.

The weapon must have a single root `j_gun`. Viewhands must contain `tag_weapon`,
or `tag_weapon_left` and `tag_weapon_right` for dual wield. Joint Mapping can
override these names. Each model must contain exactly one skeleton. Ambiguous
overlapping names are rejected, except shared `j_gun`, whose animation belongs
to viewhands. Weapon bones are isolated with `weapon__`, `akimbo_l__` and
`akimbo_r__` prefixes before joining into one armature. Weapon-root heads are
aligned to their tags, parented, and their pose translation is zeroed. No
destructive scene reset is used.

Dual wield duplicates the same weapon; it does not combine unrelated weapon
rigs. Left/right ownership follows `_le`/`_left` and `_ri`/`_right` names and
their descendants. Simultaneous playback uses the right clip for shared
root/torso bones. Sequential playback starts the right clip after the left;
each side holds its first/last pose outside its own interval. Frame rates
must agree. The result is sampled at each integer frame into one action.

Select the toolkit armature to apply clips without rebuilding meshes, or
use **Replace Left / Replace Right**. Optional Reference Viewhands compensates
matching relative/additive tag-translation axes; absolute axes are unchanged.
The reference tag must have the same parent as the current tag.

## Outputs and batch

Choose a Default Output folder and formats; blank per-format folders inherit
that folder. Existing output files are not overwritten: filenames use `_001`,
`_002`, etc. Export Selected Assembly writes only the chosen rig and bound
meshes, not unrelated objects. A JSON report records inputs, attachment checks,
warnings and output paths.

| Format | Content / receiving-side requirements |
| --- | --- |
| BLEND | A scoped assembly scene with animation and DQS. Not a snapshot of the current workspace. Blender may print “Library file, loading empty scene” while opening the file; the `CoD Viewmodel` scene contains the exported assembly. |
| CAST | Model plus skeletal animation when present, through patched upstream CAST 2.00. Combined-file round-trip verification uses this package's backend. |
| FBX | Selected rig and meshes, baked skeletal animation. Enable **Dual Quaternion / Preserve Volume** skinning in the receiving app; Blender's default FBX import uses linear skinning. Use animation offset `0` when comparing frame-for-frame in Blender. |
| SMD | Animated export contains the skeleton and animation only. A build with no animation exports a static skinned triangle model. SMD does not encode bone scale or DQS. |

Animation Batch accepts multiple single clips or explicit left/right pairs.
Start Batch Export processes one item at a time, continues after failed items,
and removes only its temporary scene objects. Escape or Stop After Current
stops between items, preserving completed files. A single heavy import/export
can temporarily block Blender's UI; cancellation cannot interrupt that call.
Open Last Report shows the completed/failed items. Scene frame range, FPS and
selection are restored after each item.

## Scope and limitations

- This release composes skeletal animation; blend-shape animation is skipped
  with a warning. Model shape keys are imported. CAST IK, constraints and hair
  are disabled in this workflow.
- Keep source models, clips and texture files available. Textures remain
  external references; the exporter does not copy or pack all image files.
- Replacement reads the original opposite-side clip path from assembly metadata.
- Unknown animation tracks are reported and skipped; all-unmatched clips fail.
- Skinning/material support varies by output format. FBX DQS must be selected
  by the receiving application; the file does not enforce it.
- Real single-weapon data and synthetic dual-wield fixtures were tested. This
  release has not been tested against a real left/right dual-clip pair.

## Python API

```python
from cod_viewmodel_toolkit import core, exporting

rig = core.build(hands_path, weapon_path, core.BuildOptions(), left=clip_path)
report = exporting.export(rig, exporting.ExportOptions(
    directory=output_dir, blend=True, cast=True, fbx=True, smd=True))

batch = exporting.Batch(hands_path, weapon_path, [(clip_path, "")],
    core.BuildOptions(), exporting.ExportOptions(directory=output_dir))
while not batch.done:
    batch.step()
report_path = batch.finish()
```

See [verification](VERIFICATION_3.3.0.md) and [CAST patch provenance](../third_party/cast_blender/PATCHES.md).
