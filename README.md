# CoD Viewmodel Toolkit

[简体中文](README.zh-CN.md)

CoD Viewmodel Toolkit assembles **Call of Duty first-person viewhands,
weapons and CAST animations** in Maya or Blender. Build a single weapon or
duplicate one weapon for dual wield, compose left/right clips, and batch
export with independent format folders and JSON reports. Compatibility
depends on the supplied skeletons; this is not a promise of support for
every Call of Duty title or extractor.

Version **3.4.0** adds optional [ft-to-meter output conversion](docs/OUTPUT_UNITS.md).
The Blender edition is based on upstream **CAST 2.00**.
Maya has English and Simplified Chinese packages; Blender currently has an
English or Simplified Chinese native sidebar. Both platforms bundle their own project-patched
CAST backend. Blender does not require Maya.

[Download 3.4.0](https://github.com/ez4cywa/cod-viewmodel-toolkit/releases/tag/3.4.0)
· [What's new](docs/RELEASE_NOTES_3.4.0.md)
· [Blender guide](docs/BLENDER.md)

## Choose your platform

| Edition | Verified runtime | Scene format | Package suffix |
| --- | --- | --- | --- |
| Maya English / 简体中文 | Maya 2025, Windows; targets Maya 2022+ Python 3 | `.ma` | `maya-en` / `maya-zh-CN` |
| Blender English / 简体中文 | Blender 5.2.1 LTS, Windows; requires Blender 5.2+ | `.blend` assembly scene | `blender-en` / `blender-zh-CN` |

Both support single/dual assembly, skeletal animation composition, one-side
replacement, batch queues, CAST, FBX and SMD. Platform-specific import and
scene-editing behavior is not identical. Follow the [Blender guide](docs/BLENDER.md)
for installation, limitations and API examples. **The sections below describe Maya.**

## Features

- Attach a weapon's `j_gun` below a viewhands `tag_weapon`.
- Duplicate one weapon for `tag_weapon_left` and `tag_weapon_right`.
- Compose left and right akimbo animations on the same frame range.
- Place the two clips sequentially when side-by-side review is preferable.
- Replace only the left or right clip in an existing dual-wield scene.
- Optionally compensate relative/additive weapon-tag translation tracks from
  a compatible reference-viewhands rest pose.
- Preserve existing animation during toolkit-managed CAST imports even when
  CAST's global **Import Resets Scene** option is enabled.
- Route a dropped pure-animation CAST safely around duplicate joint names.
- Export versioned Maya ASCII, CAST model, Source SMD, and static FBX files.
- Choose formats and output folders independently.
- Batch-export multiple single-weapon animations or explicit left/right dual
  animation pairs, with progress, cancellation, and per-item reports.
- Use DQS skinning for toolkit animation batch exports.
- Write a JSON verification manifest next to every result.
- Include the project-patched CAST Maya translator based on upstream v2.00,
  with batch-mode, per-call option, and missing-UV export fixes.
- Choose the English entry point or the separately packaged Simplified
  Chinese UI; both editions use the same core implementation.

## Requirements

- Autodesk Maya 2022 or newer running in Python 3 mode. Maya 2022 includes
  Python 3.7.7, the minimum supported Python runtime.
- Windows is the verified operating system. **Open Output Folders** uses the
  Windows-only `os.startfile` integration; core Maya workflows are not yet
  certified on macOS or Linux.
- The release archives include a project-patched Maya translator based on
  [dtzxporter/cast v2.00](https://github.com/dtzxporter/cast/releases/tag/v2.00).
  No separate CAST download is required when installing from a release ZIP.
- CAST files whose skeleton names follow the conventions described below.

The bundled translator is derived from a separate MIT-licensed project and
is not an official upstream build. See
[`third_party/cast/PATCHES.md`](third_party/cast/PATCHES.md) for its exact
baseline, hashes, and local changes.

## Installation

1. Back up any existing `castplugin.py` and `cast.py` in your target Maya
   plug-in directory. Do not copy or overwrite `cast.cfg`; it contains your
   personal CAST preferences.
2. Choose one release edition and copy the complete contents of its
   `plug-ins` directory into a directory on `MAYA_PLUG_IN_PATH`, such as your
   Maya user `plug-ins` directory. Both editions include the patched CAST
   2.00 translator:
   - English: `viewmodel_weapon_toolkit.py`.
   - Simplified Chinese: `viewmodel_weapon_toolkit.py` plus
     `viewmodel_weapon_toolkit_zh_CN.py` (the first file is the shared core).
3. For an English upgrade from Attach Gun, copy `plug-ins/attach_gun.py`
   beside the primary file. To use the Chinese edition, disable auto-load for
   both the old `attach_gun.py` and the English primary entry instead.
4. In Maya's Plug-in Manager, load `viewmodel_weapon_toolkit.py` for English,
   or `viewmodel_weapon_toolkit_zh_CN.py` for Simplified Chinese.
5. Open the **CoD Viewmodel Toolkit** menu in Maya's main menu bar.

For a source checkout, copy `third_party/cast/cast.py` and
`third_party/cast/castplugin.py` beside the selected toolkit entry files.

The plugin registers both `viewmodelWeaponToolkit` and the legacy
`attachGun` Maya commands. Loading either command opens the single-weapon
builder. The English, Chinese, and legacy entry points register the same
commands, so enable auto-load for only one edition at a time.

## Expected skeletons

### Single weapon

- The weapon file supplies `j_gun`.
- The viewhands file supplies `tag_weapon`.
- The plugin parents the weapon `j_gun` with `absolute=True`, then sets its
  local X, Y, and Z translation to zero.
- Joint transforms are never frozen.

### Dual wield

- The viewhands file supplies `tag_weapon_left` and `tag_weapon_right`.
- One weapon model is imported twice and receives persistent `akimbo_l_` and
  `akimbo_r_` joint prefixes.
- Left animation drives the left hand branch and left weapon; right animation
  drives the right hand branch and right weapon.
- In simultaneous mode, shared torso/root tracks use the right clip by
  default. Sequential mode keeps both complete clips in consecutive ranges.

Dual mode is intentionally for two copies of the same weapon skeleton. It
does not combine two unrelated or asymmetric weapon rigs.

### Optional reference-pose compensation

Some animation CAST files contain `relative` or `additive` translation tracks
authored against a different viewhands rest pose. If a weapon follows the
animation but remains displaced from one hand, select the compatible
viewhands model in **Reference pose (optional)**. The toolkit calculates each
`tag_weapon_left/right` local rest-translation difference and shifts only the
affected relative/additive animation curves. Absolute tracks, rotations,
weapon roots, and skin bind data are unchanged.

Leave the field blank for the previous behavior. The current and reference
target joints must have the same parent joint name. Compensation values and
the reference path are saved in the scene metadata and verification manifest,
and are reused when replacing a dual animation clip.

## Output behavior

The original builders keep their existing output behavior: Maya ASCII (`.ma`)
preserves the scene and animation; CAST, SMD, and FBX are static model exports.
The new **Single Animation Batch...** and **Dual Animation Batch...** entries
export animation in every selected format:

| Format | Batch contents |
| --- | --- |
| MA | Complete Maya scene, skinning, and animation |
| CAST | Combined model and baked skeletal animation |
| FBX | Skinned model and baked animation |
| SMD | Skeletal animation only, without mesh; frame zero is the clip start |

Both batch workflows use **DQS (Dual Quaternion)** skinning. MA and FBX keep
the Maya skinning mode; CAST writes `quaternion` mesh metadata and combines
the original assembled rest model with sampled animation. Export sampling
does not replace the original animation curves in the working scene. The
installed/bundled CAST plugin files are not modified by this feature.

SMD v1 does not store frame rate, scale, or shear. Read the frame rate from
the JSON manifest and set it in the target application. Non-unit joint scale
or shear causes that SMD export to fail explicitly; other selected formats
can still succeed. SMD uses centimeters and XYZ Euler rotations in radians.

All output formats are optional. Each enabled format can target a different
folder. Existing files are not overwritten: the toolkit appends a version
suffix such as `_v001`.

## Batch animation workflow

1. Open **Single Animation Batch...** or **Dual Animation Batch...** from
   the toolkit menu or the corresponding builder.
2. Choose one viewhands file and one weapon file. In dual mode, choose
   simultaneous/sequential playback and, if needed, a reference pose.
3. Single: **Add Animations...** accepts multiple CAST animation files.
   Dual: select left/right paths and **Add Current Pair**, or use
   **Add Animation Pairs...** to select the same number of left and right
   files in corresponding order. Inspect the full-path pairs before running.
4. Independently check MA, CAST, SMD, and/or FBX and choose output folders.
   At least one format must be selected; blank folders use Manifest/default.
5. Start **Batch Export Animations**. Each clip/pair starts from an isolated
   scene. **Cancel After Current Item** finishes the current item and stops
   before the next. Save any working scene when prompted before the batch.

Each clip uses its imported frame range and frame rate; both clips in a dual
pair must share a frame rate. Output names use the animation filename (the
left filename for dual pairs) and a shared version suffix. Duplicate queue
entries are removed, while distinct clips with the same basename get new
versions. Failed items/formats are recorded and subsequent jobs continue.
The final JSON batch report lists successful paths and individual failures.

Python API: `batch_export_animations(hands, weapon, animation_paths, options)`
and `batch_export_dual_animations(hands, weapon, [(left, right), ...], options)`.
Use `AttachOptions` or `DualWieldOptions` respectively. The four existing
output booleans and directory fields apply to both APIs. Both return the
batch summary dictionary; they do not change the original static builder defaults.

## Known source-data warnings

An animation may contain a `j_gripsafety` track even when the imported model
does not contain that joint. The toolkit reports and skips that orphan track;
the remaining animation is still imported.

## Compatibility

| Support level | Environment | Status |
| --- | --- | --- |
| Minimum expected | Maya 2022, Python 3.7.7, patched CAST 2.00 | Source syntax and required Maya APIs are compatible; asset-based workflows have not been regression-tested on Maya 2022. |
| Release verified | Maya 2025, Python 3.11.4, patched CAST 2.00, Windows | Single-weapon, dual-wield, localization, and export release target. |

Maya 2022 on Windows or Linux can also be launched in Python 2 mode; this
toolkit must run in Python 3 mode. Maya 2021 and older are unsupported. The
minimum-version statement is a compatibility assessment, not a claim that
the complete asset regression suite was executed in Maya 2022.

The old filename, command, option variables, and dual-scene metadata remain
supported in 3.3.0. This allows scenes and preferences created by Attach Gun to
continue working after the product rename.

## Testing

Run the release identity and localization smoke test with Maya's Python
interpreter:

```powershell
python tests/verify_vendored_cast.py
mayapy tests/verify_plugin_identity.py
mayapy tests/verify_reference_pose_compensation.py
mayapy tests/verify_batch_animation_export.py
mayapy tests/verify_cast_v200.py
```

Batch regression tests generate synthetic CAST fixtures, check both dual
playback modes and all four outputs, and compare FBX round-trip samples.
Game assets are not included in the public repository.
See [batch verification notes](docs/BATCH_ANIMATION_VERIFICATION.md) for coverage.
See [3.2.0 verification](docs/VERIFICATION_3.2.0.md) for CAST 2.00 and native UI checks.

Build all three platform/language archives with `python scripts/build_release.py <output-dir>`.

## License

This project is released under the MIT License. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
