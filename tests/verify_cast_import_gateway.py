"""Mayapy: a private CAST gateway isolates models and safely routes animations."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import maya.cmds as cmds
import maya.standalone

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_batch_animation_export import make_animation, make_model
from verify_maya_drop_module_path import loaded_plugin_globals
from verify_standalone_export_host import assert_preserved, snapshot


class DropData:
    def __init__(self, *paths):
        self.paths = paths

    def hasUrls(self):
        return True

    def urls(self):
        return [Path(path).resolve().as_uri() for path in self.paths]


def assert_private_only(core):
    assert not core._is_plugin_loaded("castplugin"), "External CAST plugin unexpectedly loaded"
    assert "cast" not in sys.modules and "castplugin" not in sys.modules
    assert "_cod_viewmodel_cast.cast" in sys.modules
    assert "_cod_viewmodel_cast.castplugin" in sys.modules
    assert core.cast_translator_name() == "CoDToolkitCast"


def assert_rejected(runtime, path):
    before = snapshot()
    before_shaders, before_graph = shader_links(), material_graph()
    namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
    relative = cmds.namespace(query=True, relativeNames=True)
    try:
        runtime().import_cast_file(str(path))
    except (RuntimeError, ValueError) as error:
        assert str(error), "CAST gateway returned an empty error"
        message = str(error)
    else:
        raise AssertionError("CAST gateway accepted an unsupported/ambiguous import: %s" % path)
    assert_preserved(before, snapshot())
    assert cmds.namespaceInfo(currentNamespace=True, absoluteName=True) == namespace
    assert cmds.namespace(query=True, relativeNames=True) == relative
    assert shader_links() == before_shaders
    assert material_graph() == before_graph
    return message


def shader_links():
    result = {}
    for node in cmds.ls(materials=True) or []:
        if not cmds.objExists(node + ".outColor"):
            continue
        result[node] = {
            "outputs": tuple(sorted(cmds.listConnections(
                node + ".outColor", source=False, destination=True, plugs=True) or [])),
            "attributes": {attribute: cmds.getAttr(node + "." + attribute)
                           for attribute in ("color", "baseColor", "metalness", "specularIOR", "specularRoughness")
                           if cmds.attributeQuery(attribute, node=node, exists=True)},
        }
    return result


def material_graph():
    attributes = {
        "file": ("fileTextureName", "colorSpace", "ignoreColorSpaceFileRules", "defaultColor"),
        "place2dTexture": ("repeatUV", "offset"),
        "colorConstant": ("inColor", "inAlpha"),
        "reverse": ("input",),
        "bump2d": ("bumpInterp", "bumpDepth"),
    }
    return {node: {
        "attributes": {attribute: cmds.getAttr(node + "." + attribute)
                       for attribute in names},
        "connections": tuple(sorted(cmds.listConnections(
            node, connections=True, plugs=True) or [])),
    } for kind, names in attributes.items() for node in cmds.ls(type=kind) or []}


def model_import(runtime, path, prefix="cast_import", explicit=False):
    before = snapshot()
    old_shaders = shader_links()
    old_graph = material_graph()
    current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
    relative = cmds.namespace(query=True, relativeNames=True)
    report = runtime().import_cast_file(str(path), namespace=prefix if explicit else None)
    assert isinstance(report, dict)
    assert cmds.namespaceInfo(currentNamespace=True, absoluteName=True) == current
    assert cmds.namespace(query=True, relativeNames=True) == relative
    after = snapshot()
    assert set(before["nodes"]).issubset(after["nodes"])
    new_nodes = set(after["nodes"]) - set(before["nodes"])
    assert new_nodes, "Model gateway created no model nodes"
    namespaces = {node.rsplit("|", 1)[-1].rsplit(":", 1)[0]
                  for node in new_nodes if ":" in node.rsplit("|", 1)[-1]}
    assert len(namespaces) == 1 and next(iter(namespaces)).startswith(prefix), namespaces
    imported_namespace = next(iter(namespaces))
    assert cmds.namespace(exists=":" + imported_namespace)
    assert all(node.rsplit("|", 1)[-1].startswith(imported_namespace + ":")
               for node in new_nodes), sorted(new_nodes)
    for field in ("scene", "frame", "units", "up_axis", "playback", "keys"):
        assert before[field] == after[field], (field, before[field], after[field])
    for cluster, method in before["skin_methods"].items():
        assert after["skin_methods"][cluster] == method
    for frame, poses in before["poses"].items():
        for node, matrix in poses.items():
            assert max(abs(a-b) for a,b in zip(matrix, after["poses"][frame][node])) < 1e-8, (frame, node)
    for node, connections in old_shaders.items():
        assert shader_links()[node] == connections, ("Existing shader was altered", node)
    for node, values in old_graph.items():
        assert material_graph()[node] == values, ("Existing material utility was altered", node)
    shader_groups = [node for node in new_nodes if cmds.nodeType(node) == "shadingEngine"]
    assert shader_groups, "Namespaced model reused an existing shader instead of creating its own"
    kinds = {cmds.nodeType(node) for node in new_nodes}
    assert {"standardSurface", "shadingEngine", "file", "place2dTexture", "colorConstant", "reverse", "bump2d"}.issubset(kinds), kinds
    shader = next(node for node in new_nodes if cmds.nodeType(node) == "standardSurface")
    for attribute in ("baseColor", "specularRoughness", "normalCamera", "emissionColor"):
        source = cmds.listConnections(shader + "." + attribute, source=True,
                                      destination=False, plugs=True) or []
        assert len(source) == 1 and source[0].lstrip(":").startswith(imported_namespace + ":"), (attribute, source)
    for node in new_nodes:
        if cmds.nodeType(node) == "file":
            slot = node.rsplit("_", 1)[-1]
            assert slot in ("albedo", "gloss", "normal"), node
            assert cmds.getAttr(node + ".fileTextureName").replace("\\", "/").endswith("/missing-synthetic/" + slot + ".png")
            placement = cmds.listConnections(node + ".uvCoord", source=True,
                                             destination=False, plugs=True) or []
            assert len(placement) == 1 and placement[0].lstrip(":").startswith(imported_namespace + ":"), (node, placement)
        elif cmds.nodeType(node) == "colorConstant":
            assert abs(cmds.getAttr(node + ".inAlpha") - 1.0) < 1e-8
        elif cmds.nodeType(node) == "bump2d":
            assert cmds.getAttr(node + ".bumpInterp") == 1
        if cmds.nodeType(node) == "shadingEngine":
            shader = cmds.listConnections(node + ".surfaceShader", source=True,
                                          destination=False, plugs=True) or []
            assert len(shader) == 1, ("Imported shader group has no shader", node, shader)
            assert shader[0].split(".", 1)[0].startswith(imported_namespace + ":"), (node, shader)
    assert_private_only(runtime())
    print("CAST_GATEWAY_MODEL_OK", imported_namespace, len(new_nodes), flush=True)
    return imported_namespace


def assert_single_routed(result, end=3):
    for frame in range(end + 1):
        cmds.currentTime(frame)
        assert max(abs(value) for value in cmds.getAttr(result.source_node + ".translate")[0]) < 1e-8
    assert abs(cmds.getAttr("viewhands_j_gun.tx", time=end) - 10) < 1e-6
    assert abs(cmds.getAttr("j_slide.tz", time=end) - 4) < 1e-6
    assert not cmds.listConnections(result.source_node + ".translate", source=True,
                                    destination=False, type="animCurve")


def offset_model(core, path, positions):
    serializer = core._cast_backend().serializer
    document = serializer.Cast.load(str(path))
    model = next(node for node in document.Roots()[0].childNodes
                 if isinstance(node, serializer.Model))
    for bone in model.Skeleton().Bones():
        if bone.Name() in positions:
            bone.SetLocalPosition(positions[bone.Name()])
    for material in model.Materials():
        material.SetName("gateway_fixture_mat")
        material.SetType("pbr")
        for slot in ("albedo", "gloss", "normal"):
            texture = material.CreateFile()
            texture.SetPath("missing-synthetic/%s.png" % slot)
            material.SetSlot(slot, texture.Hash())
        color = material.CreateChild(serializer.Color())
        color.SetColorSpace("srgb")
        color.SetRgba((0.2, 0.3, 0.4, 1))
        material.SetSlot("emissive", color.Hash())
    document.save(str(path))


def fixtures(core, folder):
    hands, weapon, clip = [folder / (name + ".cast") for name in ("hands", "weapon", "clip")]
    make_model(core, hands, True)
    make_model(core, weapon, False)
    offset_model(core, hands, {"j_gun": (70, 2, 3), "tag_weapon": (5, 6, 7)})
    offset_model(core, weapon, {"j_gun": (99, 88, 77)})
    tracks = [("j_gun", "tx", 0, 10, "absolute"),
              ("j_slide", "tz", 1, 4, "absolute"),
              ("j_wrist_le", "tx", -4, -8, "absolute"),
              ("j_wrist_ri", "tx", 4, 8, "absolute")]
    make_animation(core, clip, 3, tracks)
    left, right = folder / "vm_akimbo_l_fixture.cast", folder / "vm_akimbo_r_fixture.cast"
    for path in (left, right):
        make_animation(core, path, 3, tracks)
    serializer = core._cast_backend().serializer
    mixed = folder / "mixed.cast"
    document = serializer.Cast.load(str(hands))
    animation = document.Roots()[0].CreateAnimation()
    animation.SetFramerate(30)
    curve = animation.CreateCurve()
    curve.SetNodeName("j_gun")
    curve.SetKeyPropertyName("tx")
    curve.SetMode("absolute")
    curve.SetKeyFrameBuffer([0, 3])
    curve.SetFloatKeyValueBuffer([0, 10])
    document.save(str(mixed))
    instance = folder / "instance.cast"
    document = serializer.Cast()
    root = document.CreateRoot()
    child = root.CreateInstance()
    child.SetName("fixture_instance")
    file = child.CreateChild(serializer.File())
    file.SetPath("missing-synthetic.cast")
    child.SetReferenceFile(file.Hash())
    child.SetPosition((0, 0, 0))
    child.SetRotation((0, 0, 0, 1))
    child.SetScale((1, 1, 1))
    document.save(str(instance))
    empty = folder / "empty.cast"
    document = serializer.Cast()
    document.CreateRoot()
    document.save(str(empty))
    return hands, weapon, clip, left, right, mixed, instance, empty


def run_gateway(namespace, folder):
    runtime = namespace["_core_runtime"]
    core = runtime()
    assert callable(getattr(core, "import_cast_file", None)), "Private CAST import gateway is not implemented"
    assert_private_only(core)
    # Autodesk's bundled lookdevKit owns colorConstant, including in Maya 2027.
    # Load it for the same-name old-node fixture; no external CAST is used.
    cmds.loadPlugin("lookdevKit", quiet=True)
    hands, weapon, clip, left, right, mixed, instance, empty = fixtures(core, folder)
    cmds.file(new=True, force=True)
    existing_material = cmds.shadingNode("standardSurface", asShader=True, name="gateway_fixture_mat")
    cmds.setAttr(existing_material + ".baseColor", 0.21, 0.32, 0.43, type="double3")
    cmds.setAttr(existing_material + ".metalness", 0.6)
    cmds.setAttr(existing_material + ".specularIOR", 1.9)
    existing_group = cmds.sets(renderable=True, empty=True, name="gateway_fixture_matSG")
    cmds.connectAttr(existing_material + ".outColor", existing_group + ".surfaceShader", force=True)
    existing_mesh = cmds.polyCube(name="retained_model")[0]
    cmds.sets(existing_mesh, edit=True, forceElement=existing_group)
    existing_members = cmds.sets(existing_group, query=True)
    for slot in ("albedo", "gloss", "normal"):
        texture = cmds.shadingNode("file", asTexture=True, name="gateway_fixture_mat_" + slot)
        cmds.setAttr(texture + ".fileTextureName", "preserved-root-" + slot + ".png", type="string")
        cmds.setAttr(texture + ".colorSpace", "Raw", type="string")
        cmds.setAttr(texture + ".defaultColor", 0.61, 0.62, 0.63, type="double3")
        placement = cmds.shadingNode("place2dTexture", asUtility=True,
                                     name="place2dTexture_gateway_fixture_mat_" + slot)
        cmds.setAttr(placement + ".repeatUV", 2, 3, type="double2")
        cmds.connectAttr(placement + ".outUV", texture + ".uvCoord", force=True)
    color = cmds.shadingNode("colorConstant", asUtility=True, name="color_emissive")
    cmds.setAttr(color + ".inColor", 0.11, 0.22, 0.33, type="double3")
    cmds.setAttr(color + ".inAlpha", 0.75)
    reverse = cmds.shadingNode("reverse", asUtility=True, name="reverse1")
    cmds.setAttr(reverse + ".input", 0.8, 0.7, 0.6, type="double3")
    bump = cmds.shadingNode("bump2d", asUtility=True, name="bump2d1")
    cmds.setAttr(bump + ".bumpInterp", 0)
    cmds.setAttr(bump + ".bumpDepth", 0.47)
    dummy = cmds.createNode("joint", name="j_gun")
    cmds.setKeyframe(dummy, attribute="translateX", time=0, value=90)
    cmds.setKeyframe(dummy, attribute="translateX", time=3, value=99)
    cmds.currentTime(1)
    assert_rejected(runtime, clip)
    before = snapshot()
    rejected = core.handle_external_cast_drop(DropData(clip), True)
    assert rejected == core.OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
    assert_preserved(before, snapshot())
    model_import(runtime, hands)
    assert cmds.sets(existing_group, query=True) == existing_members, (
        "Existing material binding changed", existing_members, cmds.sets(existing_group, query=True))
    cmds.namespace(addNamespace="caller")
    cmds.namespace(setNamespace=":caller")
    model_import(runtime, weapon, prefix="chosen_import", explicit=True)
    model_import(runtime, weapon, prefix="chosen_import", explicit=True)
    module = core._castplugin_module()
    original_import, original_delete = module.importModelNode, cmds.delete
    for cleanup_failure in (False, True):
        phase = {"failed": False}

        def fail_model(*args, **kwargs):
            original_import(*args, **kwargs)
            phase["failed"] = True
            raise RuntimeError("Injected gateway primary failure")

        def delete_with_failure(*args, **kwargs):
            if cleanup_failure and phase["failed"]:
                raise RuntimeError("Injected gateway cleanup failure")
            return original_delete(*args, **kwargs)

        with patch.object(module, "importModelNode", side_effect=fail_model), \
                patch.object(cmds, "delete", side_effect=delete_with_failure):
            message = assert_rejected(runtime, hands)
        assert "Injected gateway primary failure" in message, message
        if cleanup_failure:
            assert message.index("Injected gateway primary failure") < message.index("Injected gateway cleanup failure"), message
        print("CAST_GATEWAY_ROLLBACK_OK", "namespace fallback" if cleanup_failure else "primary failure", flush=True)
    cmds.namespace(setNamespace=":")
    for path in (mixed, instance, empty):
        assert_rejected(runtime, path)
        before = snapshot()
        rejected = core.handle_external_cast_drop(DropData(path), True)
        assert rejected == core.OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
        assert_preserved(before, snapshot())

    result = core.attach_gun(str(hands), str(weapon), core.AttachOptions(force_new_scene=True))
    assert max(abs(value) for value in cmds.getAttr(result.source_node + ".translate")[0]) < 1e-8
    assert cmds.getAttr(result.target_node + ".translate")[0] == (5, 6, 7)
    report = runtime().import_cast_file(str(clip))
    assert isinstance(report, dict)
    assert_single_routed(result)
    model_import(runtime, weapon)
    assert_single_routed(result)
    before_drop = snapshot()
    namespace_count = len(cmds.namespaceInfo(":", listOnlyNamespaces=True, recurse=True) or [])
    accepted = core.handle_external_cast_drop(DropData(weapon), True)
    assert accepted == core.OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndAccept
    after_drop = snapshot()
    assert set(before_drop["nodes"]).issubset(after_drop["nodes"])
    assert before_drop["keys"] == after_drop["keys"]
    assert len(cmds.namespaceInfo(":", listOnlyNamespaces=True, recurse=True) or []) > namespace_count
    assert_single_routed(result)

    before = snapshot()
    with patch.dict(namespace, {"import_cast_file": lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("An unsupported external drop entered the CAST gateway"))}):
        for data, do_drop in ((DropData(weapon), False),
                              (DropData(folder / "unrelated.txt"), True)):
            status = core.handle_external_cast_drop(data, do_drop)
            assert status == core.OpenMayaUI.MExternalDropCallback.kMayaDefault
        status = core.handle_external_cast_drop(DropData(hands, weapon), True)
        assert status == core.OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
    assert_preserved(before, snapshot())

    cmds.namespace(addNamespace="ambiguous")
    other_target = cmds.createNode("joint", name="ambiguous:tag_weapon")
    cmds.createNode("joint", name="ambiguous:j_gun", parent=other_target)
    assert_rejected(runtime, clip)
    before = snapshot()
    rejected = core.handle_external_cast_drop(DropData(clip), True)
    assert rejected == core.OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
    assert_preserved(before, snapshot())

    dual = core.attach_dual_wield(str(hands), str(weapon), str(left), str(right),
                                 core.DualWieldOptions(force_new_scene=True))
    for path in (left, right):
        report = runtime().import_cast_file(str(path))
        assert isinstance(report, dict)
    core.validate_dual_wield()
    for frame in range(4):
        cmds.currentTime(frame)
        for source in (dual.source_node, dual.right_source_node):
            assert max(abs(value) for value in cmds.getAttr(source + ".translate")[0]) < 1e-8
    assert abs(cmds.getAttr("akimbo_l_j_slide.tz", time=3) - 4) < 1e-6
    assert abs(cmds.getAttr("akimbo_r_j_slide.tz", time=3) - 4) < 1e-6
    for path in (mixed, instance):
        assert_rejected(runtime, path)
    assert_private_only(runtime())
    print("CAST_IMPORT_GATEWAY_OK: isolated model namespaces; single/dual safe animation; unsupported imports reject without mutation; no external CAST", flush=True)


def run_color_autoload(namespace, folder):
    runtime = namespace["_core_runtime"]
    core = runtime()
    assert not core._is_plugin_loaded("lookdevKit")
    assert "colorConstant" not in cmds.allNodeTypes()
    hands = folder / "color-autoload.cast"
    make_model(core, hands, True)
    offset_model(core, hands, {})
    cmds.file(new=True, force=True)
    model_import(runtime, hands)
    assert core._is_plugin_loaded("lookdevKit")
    assert "colorConstant" in cmds.allNodeTypes()
    assert_private_only(runtime())
    print("CAST_GATEWAY_COLOR_AUTOLOAD_OK: Maya bundled lookdevKit loaded on demand; no external CAST", flush=True)


def namespace_probe(core, model):
    """Characterize the shipped translator without changing any runtime code."""
    results = []
    for active, relative, direct in ((False, False, False), (True, False, False),
                                     (True, True, False), (True, False, True),
                                     (True, True, True)):
        cmds.file(new=True, force=True)
        cmds.namespace(setNamespace=":")
        cmds.namespace(relativeNames=False)
        before_nodes = set(cmds.ls(long=True) or [])
        cmds.namespace(relativeNames=relative)
        if active:
            cmds.namespace(addNamespace="probe")
            cmds.namespace(setNamespace=":probe")
        error = ""
        try:
            if direct:
                serializer = core._cast_backend().serializer
                document = serializer.Cast.load(str(model))
                for root in document.Roots():
                    for child in root.childNodes:
                        if isinstance(child, serializer.Model):
                            core._castplugin_module().importModelNode(child, str(model))
                report = {"requested_namespace": "probe"}
            else:
                report = core.import_cast(str(model), "probe")
        except RuntimeError as exception:
            error = str(exception)
            report = {"requested_namespace": "probe"}
        active_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        relative_names = bool(cmds.namespace(query=True, relativeNames=True))
        cmds.namespace(relativeNames=False)
        groups = {}
        for node in sorted(set(cmds.ls(long=True) or []) - before_nodes):
            groups.setdefault(cmds.nodeType(node), []).append(node)
        results.append({
            "active_namespace": active_namespace,
            "relative_names": relative_names,
            "direct": direct,
            "error": error,
            "requested_namespace": report["requested_namespace"],
            "namespaces": cmds.namespaceInfo(listOnlyNamespaces=True) or [],
            "nodes_by_type": groups,
        })
        cmds.namespace(setNamespace=":")
        cmds.namespace(relativeNames=False)
    print("CAST_NAMESPACE_PROBE", json.dumps(results, sort_keys=True), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-namespace", action="store_true")
    parser.add_argument("--color-autoload", action="store_true")
    parser.add_argument("--plugin", type=Path, default=ROOT / "plug-ins/viewmodel_weapon_toolkit.py")
    arguments = parser.parse_args()
    plugin = arguments.plugin.resolve()
    cmds.loadPlugin(str(plugin), quiet=True)
    namespace = loaded_plugin_globals(plugin)
    core = namespace["_core_runtime"]()
    with tempfile.TemporaryDirectory(prefix="cod_cast_gateway_") as temporary:
        folder = Path(temporary)
        if arguments.probe_namespace:
            hands = folder / "hands.cast"
            make_model(core, hands, True)
            namespace_probe(core, hands)
            return
        if arguments.color_autoload:
            run_color_autoload(namespace, folder)
            return
        run_gateway(namespace, folder)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
