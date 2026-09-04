# Maya Viewmodel Weapon Toolkit

[简体中文](README.zh-CN.md)

Maya Viewmodel Weapon Toolkit 3.0 assembles Call of Duty-style CAST
viewhands and weapon models in Maya 2022 or newer running in Python 3 mode.
It supports single-weapon setups, duplicated-weapon dual wield,
collision-safe animation import, validation, and independently configured
model exports. The release is tested on Maya 2025 for Windows.

## Features

- Attach a weapon's `j_gun` below a viewhands `tag_weapon`.
- Duplicate one weapon for `tag_weapon_left` and `tag_weapon_right`.
- Compose left and right akimbo animations on the same frame range.
- Place the two clips sequentially when side-by-side review is preferable.
- Replace only the left or right clip in an existing dual-wield scene.
- Preserve existing animation during toolkit-managed CAST imports even when
  CAST's global **Import Resets Scene** option is enabled.
- Route a dropped pure-animation CAST safely around duplicate joint names.
- Export versioned Maya ASCII, CAST model, Source SMD, and static FBX files.
- Choose formats and output folders independently.
- Write a JSON verification manifest next to every result.
- Include the project-patched CAST Maya translator based on upstream v1.99,
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
  [dtzxporter/cast v1.99](https://github.com/dtzxporter/cast/releases/tag/v1.99).
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
   1.99 translator:
   - English: `viewmodel_weapon_toolkit.py`.
   - Simplified Chinese: `viewmodel_weapon_toolkit.py` plus
     `viewmodel_weapon_toolkit_zh_CN.py` (the first file is the shared core).
3. For an English upgrade from Attach Gun, copy `plug-ins/attach_gun.py`
   beside the primary file. To use the Chinese edition, disable auto-load for
   both the old `attach_gun.py` and the English primary entry instead.
4. In Maya's Plug-in Manager, load `viewmodel_weapon_toolkit.py` for English,
   or `viewmodel_weapon_toolkit_zh_CN.py` for Simplified Chinese.
5. Open the **Viewmodel Weapon Toolkit** menu in Maya's main menu bar.

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

## Output behavior

Maya ASCII (`.ma`) is the animation-authoritative output. CAST, SMD, and FBX
are combined/static model exports; they are useful for interchange but should
not be treated as replacements for the animated Maya scene.

All output formats are optional. Each enabled format can target a different
folder. Existing files are not overwritten: the toolkit appends a version
suffix such as `_v001`.

## Known source-data warnings

An animation may contain a `j_gripsafety` track even when the imported model
does not contain that joint. The toolkit reports and skips that orphan track;
the remaining animation is still imported.

## Compatibility

| Support level | Environment | Status |
| --- | --- | --- |
| Minimum expected | Maya 2022, Python 3.7.7, patched CAST 1.99 | Source syntax and required Maya APIs are compatible; asset-based workflows have not been regression-tested on Maya 2022. |
| Release verified | Maya 2025, Python 3.11.4, patched CAST 1.99, Windows | Single-weapon, dual-wield, localization, and export release target. |

Maya 2022 on Windows or Linux can also be launched in Python 2 mode; this
toolkit must run in Python 3 mode. Maya 2021 and older are unsupported. The
minimum-version statement is a compatibility assessment, not a claim that
the complete asset regression suite was executed in Maya 2022.

The old filename, command, option variables, and dual-scene metadata remain
supported in 3.0. This allows scenes and preferences created by Attach Gun to
continue working after the product rename.

## Testing

Run the release identity and localization smoke test with Maya's Python
interpreter:

```powershell
python tests/verify_vendored_cast.py
mayapy tests/verify_plugin_identity.py
```

Full animation tests require suitable CAST assets and are therefore not
included in the public repository.

## License

This project is released under the MIT License. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
