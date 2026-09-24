# Maya guide — CoD Viewmodel Toolkit

[Project home](../README.md) · [简体中文](MAYA.zh-CN.md)

## Requirements

- Autodesk Maya 2022 or newer running in Python 3 mode. Maya 2022 includes
  Python 3.7.7, the minimum supported Python runtime.
- Windows is the verified operating system. **Open Output Folders** uses the
  Windows-only `os.startfile` integration; core Maya workflows are not yet
  certified on macOS or Linux.
- The release archives include a project-patched Maya translator based on
  [dtzxporter/cast v2.01](https://github.com/dtzxporter/cast/releases/tag/v2.01).
  No separate CAST download is required when installing from a release ZIP.
- CAST files whose skeleton names follow the conventions described below.

The bundled translator is derived from a separate MIT-licensed project and
is not an official upstream build. See
[`third_party/cast/PATCHES.md`](../third_party/cast/PATCHES.md) for its exact
baseline, hashes, and local changes.

## Installation

1. Save your scene, close Maya and back up your toolkit files before upgrading.
   Leave an independently installed `castplugin.py`, `cast.py` and `cast.cfg`
   unchanged; the toolkit no longer installs over these files.
2. Choose one release edition and copy the complete contents of its
   `plug-ins` directory into a directory on `MAYA_PLUG_IN_PATH`, such as your
   Maya user `plug-ins` directory. Copy subdirectories too. Both editions include
   `cod_viewmodel_cast_backend.py` and `cod_viewmodel_cast/{cast.py,castplugin.py}`
   alongside `cod_viewmodel_units.py` and the toolkit entry files:
   - English: `viewmodel_weapon_toolkit.py`.
   - Simplified Chinese: `viewmodel_weapon_toolkit.py` plus
     `viewmodel_weapon_toolkit_zh_CN.py` (the first file is the shared core).
3. For an English upgrade from Attach Gun, copy `plug-ins/attach_gun.py`
   beside the primary file. To use the Chinese edition, disable auto-load for
   both the old `attach_gun.py` and the English primary entry instead.
4. In Maya's Plug-in Manager, load `viewmodel_weapon_toolkit.py` for English,
   or `viewmodel_weapon_toolkit_zh_CN.py` for Simplified Chinese.
5. Open the **CoD Viewmodel Toolkit** menu in Maya's main menu bar.

For a source checkout, load the selected entry directly from `plug-ins`. The
backend resolves `third_party/cast` automatically; do not copy its files beside
the entry. For release installs, keep the `cod_viewmodel_cast` folder intact.
Do not load its nested `castplugin.py` as a separate Maya plugin.

The plugin registers both `viewmodelWeaponToolkit` and the legacy
`attachGun` Maya commands. Loading either command opens the single-weapon
builder. The English, Chinese, and legacy entry points register the same
commands, so enable auto-load for only one edition at a time.

### Private CAST backend

The toolkit registers `CoDToolkitCast`, separate from an external plugin's
`Cast` translator. It always uses the bundled implementation, regardless of
external CAST load order. GUI and batch workflows share this same backend;
per-operation options and runtime settings are restored on success or failure,
without loading or rewriting personal `cast.cfg` preferences.

Single/dual animation routing uses explicit full DAG paths rather than
temporarily renaming scene joints. Existing persistent assembly names, including
dual `akimbo_l_` / `akimbo_r_` prefixes, remain unchanged. Each clip has fresh
node, rest-transform and curve lookup caches. A single-animation drop regression
measured one physical CAST parse instead of four; separate operations still
reread the file, and changed files invalidate an active read session.

CAST 2.01 fixes exported skeleton parent indices beneath transform groups.
The project also fixes multiple curve-mode overrides being reduced to the last
entry, preserving independent translation/rotation/scale flags. These are
correctness fixes, not performance claims. See [3.5.0 notes](RELEASE_NOTES_3.5.0.md),
[backend design research](CAST_BACKEND_RESEARCH.md) and
[measurement details](CAST_BACKEND_BENCHMARK.md).

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

Attachment completion remains non-modal: successful builds do not open a
completion dialog. Errors, partial export failures and unsaved-scene prompts
remain visible.

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
| Minimum expected | Maya 2022, Python 3.7.7, private patched CAST 2.01 | Python 3.7 syntax/API compatibility target; no full Maya 2022 host regression. |
| Current verification | Maya 2027, Python 3.13.9, private patched CAST 2.01, Windows | 3.5.0 backend identity, parent indices, target routing and operation-lifetime regressions run in this host. See release notes for the completed checks. |
| Historical verification | Maya 2025, Python 3.11.4, earlier bundled CAST versions, Windows | Prior releases verified single/dual workflows, localization and exports; not re-tested for 3.5.0. |

Maya 2022 on Windows or Linux can also be launched in Python 2 mode; this
toolkit must run in Python 3 mode. Maya 2021 and older are unsupported. The
minimum-version statement is a compatibility assessment, not a claim that
the complete asset regression suite was executed in Maya 2022.

The old filename, command, option variables, and dual-scene metadata remain
supported since 3.3.0. This allows scenes and preferences created by Attach Gun to
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
mayapy tests/verify_cast_v201.py
mayapy tests/verify_private_cast_backend.py
mayapy tests/verify_animation_read_session.py
mayapy tests/verify_maya_drop_module_path.py
```

Batch regression tests generate synthetic CAST fixtures, check both dual
playback modes and all four outputs, and compare FBX round-trip samples.
Game assets are not included in the public repository.
See [batch verification notes](BATCH_ANIMATION_VERIFICATION.md) for coverage.
See [3.5.0 notes](RELEASE_NOTES_3.5.0.md) and
[backend measurements](CAST_BACKEND_BENCHMARK.md) for this release; the
[3.2.0 verification](VERIFICATION_3.2.0.md) records historical CAST 2.00/native UI checks.

Build all four platform/language archives with `python scripts/build_release.py <output-dir>`.

## License

This project is released under the MIT License. See [LICENSE](../LICENSE) and
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
