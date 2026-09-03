"""Maya smoke test for the primary and legacy plugin entry points."""

import os
import pathlib

import maya.cmds as cmds

if not hasattr(cmds, "pluginInfo"):
    import maya.standalone
    maya.standalone.initialize(name="python")


ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "plug-ins" / "viewmodel_weapon_toolkit.py"
LEGACY = ROOT / "plug-ins" / "attach_gun.py"


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == \
        os.path.normcase(os.path.abspath(str(right)))


def _assert_loaded(path, plugin_name):
    loaded_path = cmds.pluginInfo(plugin_name, query=True, path=True)
    version = str(cmds.pluginInfo(plugin_name, query=True, version=True))
    if not _same_path(loaded_path, path):
        raise RuntimeError("Maya loaded the wrong path: %s" % loaded_path)
    if version != "3.0":
        raise RuntimeError("Expected version 3.0, got %s" % version)
    if not hasattr(cmds, "viewmodelWeaponToolkit"):
        raise RuntimeError("viewmodelWeaponToolkit command is missing")
    if not hasattr(cmds, "attachGun"):
        raise RuntimeError("attachGun compatibility command is missing")


def main():
    cmds.loadPlugin(str(PRIMARY), quiet=True)
    cmds.loadPlugin(str(LEGACY), quiet=True)
    _assert_loaded(PRIMARY, "viewmodel_weapon_toolkit")
    _assert_loaded(LEGACY, "attach_gun")
    cmds.unloadPlugin("attach_gun", force=True)
    if not hasattr(cmds, "viewmodelWeaponToolkit"):
        raise RuntimeError("Unloading the legacy loader removed primary commands")
    cmds.unloadPlugin("viewmodel_weapon_toolkit", force=True)

    cmds.loadPlugin(str(LEGACY), quiet=True)
    _assert_loaded(LEGACY, "attach_gun")
    _assert_loaded(PRIMARY, "viewmodel_weapon_toolkit")
    cmds.unloadPlugin("attach_gun", force=True)
    if not hasattr(cmds, "viewmodelWeaponToolkit"):
        raise RuntimeError("Primary command did not survive legacy unload")
    cmds.unloadPlugin("viewmodel_weapon_toolkit", force=True)
    print("PLUGIN_IDENTITY_VERIFICATION_OK")


if __name__ == "__main__":
    main()
