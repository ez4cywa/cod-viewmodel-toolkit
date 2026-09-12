# 3.4.1 verification

## Regression and cause

The original Maya 2025 GUI failure was captured repeatedly in the registered
external-drop callback: `_temporary_cast_animation_settings` called
`_units_module`, which raised `NameError` at its direct `__file__` access.
The weapon attachment log already confirmed zero local translation.

`tests/verify_maya_drop_module_path.py` loads the plugin through `cmds.loadPlugin`,
finds that registered implementation's globals, removes `__file__` and clears the
units cache. It does not use an `importlib` fallback to create a second core module.
Before the fix, its single-animation drop reproduced the same exception and
rejected-drop status. After the fix, the same seam accepts the animation.

The synthetic regression checks single animation routing, both dual-wield drop
routes, keyed end values, weapon-root zero translation on every fixture frame,
the adjacent units-module path and module-cache identity. Run with Maya Python:

```text
mayapy tests/verify_maya_drop_module_path.py
mayapy tests/verify_maya_drop_module_path.py --plugin PATH_TO_INSTALLED_PLUGIN
```

## Live Maya confirmation

The fix was also applied to the already-registered function in the affected Maya
2025 GUI session, without reloading the complete plugin or rebuilding the scene.
Calling its registered external-drop callback with the originally failing local
animation succeeded: 429 animation curves, frames 0–580 (581 frames). All joint
paths and the weapon UUID were unchanged. Weapon-root translation was zero at
every frame. This is a live callback replay, not an automated Explorer mouse drag.
No proprietary fixture files are included in this repository or release.

## Scope

Only Maya units-module path resolution changes behavior. Blender package metadata
is synchronized; its assembly, animation and export logic is unchanged from 3.4.0.
