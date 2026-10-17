"""Mayapy: optional empty CAST material references retain model and skin data.

Synthetic CAST fixtures are temporary. Optional real --hands/--weapon inputs
are read-only and are attached in this isolated process with all outputs off.
Only --report writes persistent QA evidence; no model or scene is exported.
"""

import argparse
from array import array
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import time

import maya.cmds as cmds
import maya.standalone
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_maya_drop_module_path import loaded_plugin_globals


def digest(values):
    return hashlib.sha256(array("d", values).tobytes()).hexdigest()


def file_digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def mesh_paths():
    return sorted(cmds.ls(type="mesh", long=True, noIntermediate=True) or [])


def mesh_snapshot(paths=None):
    """Capture geometry and every skin weight, not only sampled vertices."""
    result = {}
    for name in paths if paths is not None else mesh_paths():
        selection = om.MSelectionList()
        selection.add(name)
        path = selection.getDagPath(0)
        mesh = om.MFnMesh(path)
        counts, indices = mesh.getVertices()
        record = {
            "vertex_count": mesh.numVertices,
            "face_count": mesh.numPolygons,
            "points": digest(v for point in mesh.getPoints(om.MSpace.kObject)
                             for v in (point.x, point.y, point.z)),
            "topology": digest(list(counts) + list(indices)),
            "normals": digest(v for normal in mesh.getNormals()
                              for v in (normal.x, normal.y, normal.z)),
            "uv": {},
        }
        for uv in mesh.getUVSetNames():
            u, v = mesh.getUVs(uv)
            uv_counts, uv_indices = mesh.getAssignedUVs(uv)
            record["uv"][uv] = [digest(u), digest(v), digest(uv_counts),
                                  digest(uv_indices)]
        clusters = [node for node in cmds.listHistory(name) or []
                    if cmds.nodeType(node) == "skinCluster"]
        assert len(clusters) == 1, (name, clusters)
        selection = om.MSelectionList()
        selection.add(clusters[0])
        skin = oma.MFnSkinCluster(selection.getDependNode(0))
        component = om.MFnSingleIndexedComponent()
        vertices = component.create(om.MFn.kMeshVertComponent)
        component.setCompleteData(mesh.numVertices)
        weights, influence_count = skin.getWeights(path, vertices)
        record["skin"] = {
            "method": cmds.getAttr(clusters[0] + ".skinningMethod"),
            "weights": {bone.partialPathName().rsplit(":", 1)[-1]:
                        digest(weights[index::influence_count])
                        for index, bone in enumerate(skin.influenceObjects())},
        }
        result[name] = record
    return result


def material_groups(mesh):
    return sorted(cmds.listConnections(mesh, type="shadingEngine") or [])


def make_fixture(serializer, path, mode):
    document = serializer.Cast()
    model = document.CreateRoot().CreateModel()
    model.SetName("fixture_model")
    skeleton = model.CreateSkeleton()
    for index, name in enumerate(("fixture_root", "fixture_tip")):
        bone = skeleton.CreateBone()
        bone.SetName(name)
        bone.SetParentIndex(index - 1)
        bone.SetLocalPosition((index, 0, 0))
        bone.SetLocalRotation((0, 0, 0, 1))
        bone.SetWorldPosition((index, 0, 0))
        bone.SetWorldRotation((0, 0, 0, 1))
        bone.SetScale((1, 1, 1))
    mesh = model.CreateMesh()
    mesh.SetName("fixture_mesh")
    mesh.SetVertexPositionBuffer([(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    mesh.SetVertexNormalBuffer([(0, 0, 1)] * 3)
    mesh.SetFaceBuffer([0, 1, 2])
    mesh.SetUVLayerCount(1)
    mesh.SetVertexUVLayerBuffer(0, [(0, 0), (1, 0), (0, 1)])
    mesh.SetMaximumWeightInfluence(1)
    mesh.SetVertexWeightBoneBuffer([0, 1, 1])
    mesh.SetVertexWeightValueBuffer([1, 1, 1])
    mesh.SetSkinningMethod("quaternion")
    if mode == "empty":
        mesh.CreateProperty("m", "l").values = []
    elif mode == "valid":
        material = model.CreateMaterial()
        material.SetName("fixture_material")
        material.SetType("pbr")
        mesh.SetMaterial(material.Hash())
    else:
        assert mode == "missing"
    document.save(str(path))


def verify_hair_getters(serializer):
    """Exercise the sibling optional getter without creating/rendering hair."""
    for mode in ("missing", "empty", "valid"):
        model = serializer.Model()
        hair = model.CreateHair()
        if mode == "empty":
            hair.CreateProperty("m", "l").values = []
        elif mode == "valid":
            material = model.CreateMaterial()
            material.SetName("hair_material")
            hair.SetMaterial(material.Hash())
        binary = io.BytesIO()
        model.save(binary)
        binary.seek(0)
        reloaded = serializer.CastNode.load(binary)
        result = reloaded.Hairs()[0].Material()
        if mode == "valid":
            assert result is reloaded.Materials()[0]
        else:
            assert result is None


def verify_synthetic(core, folder):
    serializer = core._cast_backend().serializer
    verify_hair_getters(serializer)
    expected = None
    reports = []
    for mode in ("missing", "empty", "valid"):
        cmds.file(new=True, force=True)
        existing = cmds.polyCube(name="existing_mesh")[0]
        shader = cmds.shadingNode("lambert", asShader=True,
                                  name="fixture_material")
        group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True,
                          name="fixture_materialSG")
        cmds.connectAttr(shader + ".outColor", group + ".surfaceShader")
        cmds.setAttr(shader + ".color", 0.9, 0.1, 0.2, type="double3")
        cmds.sets(existing, forceElement=group)
        before_color = cmds.getAttr(shader + ".color")
        before_connections = sorted(cmds.listConnections(
            shader, connections=True, plugs=True) or [])
        existing_shape = cmds.listRelatives(existing, shapes=True,
                                           fullPath=True)[0]
        path = folder / (mode + ".cast")
        make_fixture(serializer, path, mode)
        before_sha = file_digest(path)
        report = core.import_cast_file(str(path))
        assert report["kind"] == "model"
        assert report["namespace"] == ""
        imported = [name for name in mesh_paths() if name != existing_shape]
        assert len(imported) == 1, imported
        mesh = imported[0]
        assert ":" not in mesh.rsplit("|", 1)[-1]
        assert all(":" not in node.rsplit("|", 1)[-1]
                   for node in report["nodes"])
        data = next(iter(mesh_snapshot(imported).values()))
        assert data["vertex_count"] == 3 and data["face_count"] == 1
        assert data["skin"]["method"] == 1
        if expected is None:
            expected = data
        assert data == expected, (mode, "geometry/UV/skin changed")
        groups = material_groups(mesh)
        if mode == "valid":
            assert len(groups) == 1 and ":" not in groups[0], groups
            assert groups[0] != group
        else:
            assert groups == ["initialShadingGroup"], (mode, groups)
        assert cmds.getAttr(shader + ".color") == before_color
        assert sorted(cmds.listConnections(shader, connections=True,
                                           plugs=True) or []) == before_connections
        assert material_groups(existing_shape) == [group]
        assert file_digest(path) == before_sha
        reports.append({"mode": mode, "mesh_count": 1,
                        "material_groups": groups,
                        "geometry_skin_preserved": True})
        print("EMPTY_MATERIAL_SYNTHETIC_OK", mode, flush=True)
    return reports


def inventory(core, path):
    serializer = core._cast_backend().serializer
    document = serializer.Cast.load(str(path))
    result = {"joint_count": 0, "mesh_count": 0, "empty_material_count": 0}
    for root in document.Roots():
        for model in root.ChildrenOfType(serializer.Model):
            result["joint_count"] += len(model.Skeleton().Bones())
            result["mesh_count"] += len(model.Meshes())
            result["empty_material_count"] += sum(
                mesh.properties.get("m") is not None
                and not mesh.properties["m"].values for mesh in model.Meshes())
    return result


def verify_real(core, folder, hands, weapon):
    before_hashes = {str(path): file_digest(path) for path in (hands, weapon)}
    hands_info, weapon_info = [inventory(core, path) for path in (hands, weapon)]
    options = core.AttachOptions(output_dir=str(folder / "disabled-model-output"),
                                 force_new_scene=True, save_scene=False,
                                 export_cast=False, export_fbx=False,
                                 export_smd=False)
    cmds.file(new=True, force=True)
    with core._temporary_cast_import_settings(options):
        hands_import = core.import_cast(str(hands), core.HANDS_NAMESPACE)
        core._rename_viewhands_joint_collisions(hands_import["nodes"],
                                                options.source_joint)
    expected_hands = mesh_snapshot()
    start = time.perf_counter()
    result = core.attach_gun(str(hands), str(weapon), options)
    duration = time.perf_counter() - start
    actual_hands = mesh_snapshot(sorted(expected_hands))
    assert actual_hands == expected_hands, "Attachment changed hand geometry or skin"
    meshes = mesh_paths()
    expected_meshes = hands_info["mesh_count"] + weapon_info["mesh_count"]
    expected_joints = hands_info["joint_count"] + weapon_info["joint_count"]
    joint_count = len(cmds.ls(type="joint") or [])
    assert len(meshes) == expected_meshes, (len(meshes), expected_meshes)
    assert joint_count == expected_joints, (joint_count, expected_joints)
    weapon_meshes = sorted(set(meshes) - set(expected_hands))
    default_count = sum(material_groups(mesh) == ["initialShadingGroup"]
                        for mesh in weapon_meshes)
    assert len(weapon_meshes) == weapon_info["mesh_count"]
    assert default_count >= weapon_info["empty_material_count"]
    parents = cmds.listRelatives(result.source_node, parent=True,
                                 fullPath=True) or []
    assert parents == [result.target_node], (parents, result.target_node)
    translation = cmds.getAttr(result.source_node + ".translate")[0]
    assert max(abs(value) for value in translation) < 1e-8, translation
    assert not Path(options.output_dir).exists()
    for field in ("output_scene", "output_cast", "output_fbx", "output_smd",
                  "output_manifest"):
        assert getattr(result, field) == "", field
    assert not any(result.requested_outputs.values())
    assert not cmds.file(query=True, sceneName=True)
    assert {str(path): file_digest(path) for path in (hands, weapon)} == before_hashes
    report = {
        "input_sha256": before_hashes, "hands": hands_info, "weapon": weapon_info,
        "joint_count": joint_count, "mesh_count": len(meshes),
        "weapon_default_material_count": default_count,
        "source_joint": result.source_node, "parent_joint": parents[0],
        "translation": list(translation), "duration_seconds": duration,
        "hands_geometry_skin_unchanged": True, "sources_unchanged": True,
        "model_outputs_written": False,
    }
    print("EMPTY_MATERIAL_REAL_ATTACH_OK", json.dumps(report, sort_keys=True),
          flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path,
                        default=ROOT / "plug-ins/viewmodel_weapon_toolkit.py")
    parser.add_argument("--hands", type=Path)
    parser.add_argument("--weapon", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if bool(args.hands) != bool(args.weapon):
        parser.error("--hands and --weapon must be supplied together")
    plugin = args.plugin.resolve()
    cmds.loadPlugin(str(plugin), quiet=True)
    namespace = loaded_plugin_globals(plugin)
    core = namespace["_core_runtime"]()
    assert Path(core._TOOLKIT_PLUGIN_PATH).resolve() == plugin
    assert not core._is_plugin_loaded("castplugin")
    namespace.pop("__file__", None)
    cmds.currentUnit(linear="cm")
    report = {"plugin": str(plugin), "version": core.VERSION,
              "backend": core._cast_backend().info()}
    with tempfile.TemporaryDirectory(prefix="cod_empty_material_host_") as temporary:
        folder = Path(temporary)
        report["synthetic"] = verify_synthetic(core, folder)
        if args.hands:
            report["real_attachment"] = verify_real(
                core, folder, args.hands.resolve(), args.weapon.resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False)
                               + "\n", encoding="utf-8")
    print("EMPTY_MATERIAL_HOST_OK", core.VERSION, flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
