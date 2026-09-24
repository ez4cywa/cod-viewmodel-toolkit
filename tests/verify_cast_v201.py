"""Mayapy regression for CAST 2.01 parents and explicit animation targets."""

import argparse
import importlib.util
import math
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

import maya.standalone
import maya.cmds as cmds
if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "third_party" / "cast"))
spec = importlib.util.spec_from_file_location(
    "cast_v201_regression", str(ROOT / "third_party" / "cast" / "castplugin.py"))
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def full(name):
    return cmds.ls(name, long=True)[0]


def verify_parents():
    cmds.file(new=True, force=True)
    group = cmds.createNode("transform", name="rig_group")
    root = cmds.createNode("joint", name="root", parent=group)
    child = cmds.createNode("joint", name="child", parent=root)
    tip = cmds.createNode("joint", name="tip", parent=child)
    cmds.select([root, child, tip], replace=True)
    document = backend.Cast()
    cast_root = document.CreateRoot()
    backend.exportModel(cast_root, True, "unused.cast")
    bones = cast_root.ChildrenOfType(backend.Model)[0].Skeleton().Bones()
    parents = {bone.Name(): bone.ParentIndex() for bone in bones}
    assert parents == {"root": -1, "child": 0, "tip": 1}, parents
    print("CAST_V201_PARENTS_OK")


def animation(mode, overrides=False):
    document = backend.Cast()
    node = document.CreateRoot().CreateAnimation()
    node.SetFramerate(30)
    for name, prop, values in (
            ("cast_child", "tx", [2.0, 4.0]),
            ("cast_child", "ty", [0.0, 0.0]),
            ("cast_child", "rq", [(0, 0, 0, 1),
                                   (0, 0, 0.5, math.sqrt(0.75))]),
            ("fallback", "tx", [3.0, 5.0]),
            ("skipped", "tx", [100.0, 200.0])):
        curve = node.CreateCurve()
        curve.SetNodeName(name)
        curve.SetKeyPropertyName(prop)
        curve.SetKeyFrameBuffer([0, 2])
        curve.SetMode(mode)
        if prop == "rq":
            curve.SetVec4KeyValueBuffer(values)
        else:
            curve.SetFloatKeyValueBuffer(values)
    if overrides:
        override = node.CreateCurveModeOverride()
        override.SetNodeName("cast_parent")
        override.SetMode("relative")
        override.SetOverrideTranslationCurves(True)
        # The final rotation-only override must not hide an earlier matching
        # translation override or override translation curves itself.
        override = node.CreateCurveModeOverride()
        override.SetNodeName("unrelated")
        override.SetMode("absolute")
        override.SetOverrideRotationCurves(True)
    return node


def verify_targets():
    for mode, value, rotation in (("absolute", 4, 60),
                                   ("relative", 14, 90),
                                   ("additive", 14, 90)):
        cmds.file(new=True, force=True)
        parent = cmds.createNode("joint", name="renamed_parent")
        child = cmds.createNode("joint", name="renamed_child", parent=parent)
        fallback = cmds.createNode("joint", name="fallback")
        skipped = cmds.createNode("joint", name="skipped")
        cmds.setAttr(child + ".tx", 10)
        cmds.setAttr(child + ".rz", 30)
        names = cmds.ls(type="joint", long=True)
        targets = {"cast_parent": full(parent), "cast_child": full(child),
                   "skipped": None}
        with backend.utilityAnimationTargets(targets):
            with patch.object(backend, "utilitySaveNodeData",
                              wraps=backend.utilitySaveNodeData) as save:
                backend.importAnimationNode(animation(mode), "unused.cast")
                assert save.call_count == 2, save.call_args_list
            # Nested mappings do not leak even when the inner operation fails.
            try:
                with backend.utilityAnimationTargets({"cast_child": None}):
                    assert backend.utilityResolveAnimationTarget("cast_child") is None
                    raise ValueError("fixture failure")
            except ValueError:
                pass
            assert backend.utilityResolveAnimationTarget("cast_child") == full(child)
        assert backend._animationState is None
        cmds.currentTime(2)
        assert abs(cmds.getAttr(child + ".tx") - value) < 1e-5, mode
        assert abs(cmds.getAttr(child + ".rz") - rotation) < 1e-4, mode
        assert abs(cmds.getAttr(fallback + ".tx") - 5) < 1e-5, mode
        assert cmds.getAttr(skipped + ".tx") == 0
        assert not cmds.listConnections(skipped, type="animCurve")
        assert cmds.ls(type="joint", long=True) == names
    # Additive must sample existing curves, not accidentally reuse stale data.
    cmds.file(new=True, force=True)
    parent = cmds.createNode("joint", name="renamed_parent")
    child = cmds.createNode("joint", name="renamed_child", parent=parent)
    cmds.setAttr(child + ".tx", 10)
    cmds.setKeyframe(child, attribute="tx", time=0, value=20)
    cmds.setKeyframe(child, attribute="tx", time=2, value=20)
    targets = {"cast_child": full(child), "cast_parent": full(parent),
               "fallback": None, "skipped": None}
    with backend.utilityAnimationTargets(targets):
        backend.importAnimationNode(animation("additive"), "unused.cast")
    cmds.currentTime(2)
    assert abs(cmds.getAttr(child + ".tx") - 24) < 1e-5
    cmds.file(new=True, force=True)
    parent = cmds.createNode("joint", name="renamed_parent")
    child = cmds.createNode("joint", name="renamed_child", parent=parent)
    cmds.setAttr(child + ".tx", 10)
    targets.update(cast_child=full(child), cast_parent=full(parent))
    with backend.utilityAnimationTargets(targets):
        backend.importAnimationNode(animation("absolute", True), "unused.cast")
    cmds.currentTime(2)
    assert abs(cmds.getAttr(child + ".tx") - 14) < 1e-5
    assert abs(cmds.getAttr(child + ".rz") - 60) < 1e-4
    # A second clip in the same routing session must see a changed rest value.
    with backend.utilityAnimationTargets(targets):
        backend.importAnimationNode(animation("relative"), "unused.cast")
        matrix = list(cmds.getAttr(child + ".castRestPosition"))
        matrix[12] = 30
        cmds.setAttr(child + ".castRestPosition", matrix, type="matrix")
        backend.importAnimationNode(animation("relative"), "unused.cast")
    cmds.currentTime(2)
    assert abs(cmds.getAttr(child + ".tx") - 34) < 1e-5
    # The importer itself must unwind its nested caches on errors.
    with backend.utilityAnimationTargets(targets):
        state = backend._animationState
        try:
            with patch.object(backend, "importCurveNode", side_effect=ValueError("fixture")):
                backend.importAnimationNode(animation("absolute"), "unused.cast")
        except ValueError:
            pass
        assert backend._animationState is state
    assert backend._animationState is None
    print("CAST_V201_TARGETS_OK")


def verify_blendshapes():
    cmds.file(new=True, force=True)
    deformers, meshes = [], []
    for suffix in ("a", "b"):
        mesh = cmds.polyCube(name="base_" + suffix)[0]
        shape = cmds.duplicate(mesh, name="target_" + suffix)[0]
        deformer = cmds.blendShape(shape, mesh, name="blend_" + suffix)[0]
        cmds.aliasAttr("smile", deformer + ".weight[0]")
        meshes.append(full(mesh))
        deformers.append(deformer)
    document = backend.Cast()
    node = document.CreateRoot().CreateAnimation()
    node.SetFramerate(30)
    curve = node.CreateCurve()
    curve.SetNodeName("smile")
    curve.SetKeyPropertyName("bs")
    curve.SetKeyFrameBuffer([0, 2])
    curve.SetFloatKeyValueBuffer([0, 0.75])
    with backend.utilityAnimationTargets({"smile": None}):
        backend.importAnimationNode(node, "unused.cast")
    assert not cmds.ls(type="animCurve")
    with backend.utilityAnimationTargets({"smile": meshes[0]}):
        backend.importAnimationNode(node, "unused.cast")
    cmds.currentTime(2)
    assert abs(cmds.getAttr(deformers[0] + ".smile") - 0.75) < 1e-6
    assert cmds.getAttr(deformers[1] + ".smile") == 0
    print("CAST_V201_BLENDSHAPES_OK")


def verify_shape_name_collision():
    """An absent bone that matches a mesh shape must skip, not abort the clip."""
    cmds.file(new=True, force=True)
    mesh = cmds.polyCube(name="collision_mesh")[0]
    shape = cmds.listRelatives(mesh, shapes=True, fullPath=True)[0]
    shape = cmds.rename(shape, "cast_child")
    fallback = cmds.createNode("joint", name="fallback")
    backend.importAnimationNode(animation("absolute"), "unused.cast")
    cmds.currentTime(2)
    assert abs(cmds.getAttr(fallback + ".tx") - 5) < 1e-5
    assert not cmds.objExists(shape + ".castRestPosition")
    assert not cmds.listConnections(shape, type="animCurve")
    assert backend._animationState is None
    print("CAST_V201_SHAPE_NAME_COLLISION_OK")


def verify_overrides():
    """Also reproduce the upstream loop bug without any new routing API."""
    cmds.file(new=True, force=True)
    parent = cmds.createNode("joint", name="cast_parent")
    child = cmds.createNode("joint", name="cast_child", parent=parent)
    cmds.createNode("joint", name="fallback")
    cmds.createNode("joint", name="skipped")
    cmds.setAttr(child + ".tx", 10)
    backend.importAnimationNode(animation("absolute", True), "unused.cast")
    cmds.currentTime(2)
    assert abs(cmds.getAttr(child + ".tx") - 14) < 1e-5, cmds.getAttr(child + ".tx")
    assert abs(cmds.getAttr(child + ".rz") - 60) < 1e-4
    print("CAST_V201_OVERRIDES_OK")


def verify_options():
    settings, runtime = dict(backend.sceneSettings), dict(backend.runtimeSettings)
    with patch("builtins.open", side_effect=AssertionError("Private cfg access")):
        backend.utilityLoadSettings()
        backend.utilitySaveSettings()
        try:
            with backend.utilityOperationOptions({"importSkin": False},
                                                 {"retargetScale": 3.0}):
                assert not backend.sceneSettings["importSkin"]
                assert backend.runtimeSettings["retargetScale"] == 3
                with backend.utilityOperationOptions({"importSkin": True}):
                    assert backend.sceneSettings["importSkin"]
                assert not backend.sceneSettings["importSkin"]
                raise ValueError("fixture failure")
        except ValueError:
            pass
    assert backend.sceneSettings == settings
    assert backend.runtimeSettings == runtime
    print("CAST_V201_OPTIONS_OK")


def verify_standalone():
    # Maya's registered Python plugin namespace has no __file__/__package__.
    # Use a disposable copy so preference creation cannot touch user cfg files.
    with tempfile.TemporaryDirectory(prefix="cast201_standalone_") as folder:
        folder = Path(folder)
        plugin = folder / "cast201_standalone.py"
        shutil.copy2(ROOT / "third_party" / "cast" / "castplugin.py", plugin)
        cmds.loadPlugin(str(plugin), quiet=True)
        try:
            assert (folder / "cast.cfg").is_file()
            assert "Cast" in cmds.pluginInfo("cast201_standalone", query=True, translator=True)
        finally:
            cmds.unloadPlugin("cast201_standalone", force=True)
    assert backend._settingsPath is None
    print("CAST_V201_STANDALONE_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("parents", "targets", "blendshapes", "shape_collision", "overrides", "options", "standalone", "all"),
                        default="all")
    args = parser.parse_args()
    for name, verify in (("parents", verify_parents), ("targets", verify_targets),
                         ("blendshapes", verify_blendshapes),
                         ("shape_collision", verify_shape_name_collision),
                         ("overrides", verify_overrides), ("options", verify_options),
                         ("standalone", verify_standalone)):
        if args.case in (name, "all"):
            verify()
    cmds.file(new=True, force=True)
    print("CAST_V201_REGRESSION_OK")
