"""Exercise CAST drop routing in Maya's real plugin globals without __file__.

Run with mayapy; optionally pass --plugin PATH to verify an installed copy.
Fixtures are synthetic and temporary. No user scene or preferences are needed.
"""

import gc
import os
from pathlib import Path
import sys
import tempfile
import types

import maya.cmds as cmds
import maya.standalone

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_batch_animation_export import make_animation, make_model


def loaded_plugin_globals(path):
    """Find the registered implementation; never import a second core module."""
    expected = os.path.normcase(os.path.abspath(str(path)))
    found = {}
    for obj in gc.get_objects():
        if isinstance(obj, types.FunctionType) and obj.__name__ == "initializePlugin":
            namespace = obj.__globals__
            registered = namespace.get("_TOOLKIT_PLUGIN_PATH", "")
            if registered and os.path.normcase(os.path.abspath(registered)) == expected:
                found[id(namespace)] = namespace
    assert len(found) == 1, "Expected one Maya-loaded plugin implementation: %r" % list(found)
    return next(iter(found.values()))


class DropData:
    def __init__(self, path):
        self.path = Path(path).resolve().as_uri()

    def hasUrls(self):
        return True

    def urls(self):
        return [self.path]


def accepted_drop(core, path):
    status = core.CastDropCallback().externalDropCallback(True, "modelPanel4", DropData(path))
    expected = core.OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndAccept
    assert status == expected, "CAST animation drop rejected: %s (status %s)" % (path, status)


def verify_roots(roots):
    for frame in range(4):
        cmds.currentTime(frame)
        for root in roots:
            assert max(abs(x) for x in cmds.getAttr(root + ".translate")[0]) < 1e-8


def main():
    plugin = Path(sys.argv[sys.argv.index("--plugin") + 1]) if "--plugin" in sys.argv else ROOT / "plug-ins/viewmodel_weapon_toolkit.py"
    cmds.loadPlugin(str(plugin), quiet=True)
    namespace = loaded_plugin_globals(plugin)
    missing = object()
    previous = namespace.pop("__file__", missing)
    namespace["_UNITS_MODULE"] = None
    core = types.SimpleNamespace(**namespace)
    try:
        with tempfile.TemporaryDirectory(prefix="cod_drop_module_path_") as temporary:
            folder = Path(temporary)
            hands, weapon = folder / "hands.cast", folder / "weapon.cast"
            clip = folder / "single.cast"
            left, right = folder / "vm_akimbo_l_test.cast", folder / "vm_akimbo_r_test.cast"
            make_model(core, hands, True)
            make_model(core, weapon, False)
            tracks = [("j_gun", "tx", 0, 2, "absolute"), ("j_slide", "tz", 1, 4, "absolute"),
                      ("j_wrist_le", "tx", -4, -8, "absolute"),
                      ("j_wrist_ri", "tx", 4, 8, "absolute")]
            for path in (clip, left, right):
                make_animation(core, path, 3, tracks)
            result = core._build_single_attachment(str(hands), str(weapon), core.AttachOptions(
                output_dir=str(folder / "single"), force_new_scene=True, export_cast=False))
            accepted_drop(core, clip)
            assert abs(cmds.getAttr("viewhands_j_gun.tx", time=3) - 2) < 1e-6
            assert abs(cmds.getAttr("j_slide.tz", time=3) - 4) < 1e-6
            verify_roots([result.source_node])
            print("MAYA_NO_FILE_SINGLE_DROP_OK")
            units = core._units_module()
            assert Path(units.__file__).resolve() == plugin.parent.resolve() / "cod_viewmodel_units.py"
            assert core._units_module() is units
            dual = core.attach_dual_wield(str(hands), str(weapon), str(left), str(right), core.DualWieldOptions(
                output_dir=str(folder / "dual"), force_new_scene=True, export_cast=False, export_animation=True))
            for path, side in ((left, "left"), (right, "right")):
                accepted_drop(core, path)
                assert abs(cmds.getAttr("akimbo_%s_j_slide.tz" % side[0], time=3) - 4) < 1e-6
                verify_roots([dual.source_node, dual.right_source_node])
                print("MAYA_NO_FILE_DUAL_%s_DROP_OK" % side.upper())
    finally:
        if previous is not missing:
            namespace["__file__"] = previous
    print("MAYA_DROP_MODULE_PATH_OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
