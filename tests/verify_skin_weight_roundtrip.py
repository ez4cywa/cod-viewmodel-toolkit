"""Mayapy: CAST round trips preserve per-vertex influence identity and skinning.

Synthetic fixtures and exported CAST files live in a temporary directory.
Optional input CAST paths are read-only. Run in an isolated MAYA_APP_DIR.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import maya.cmds as cmds
import maya.standalone
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_maya_drop_module_path import loaded_plugin_globals

core = None


def close(a, b, message):
    assert len(a) == len(b), (message, len(a), len(b))
    assert max([abs(x - y) for x, y in zip(a, b)] or [0]) < 2e-6, message


def identity(position):
    return tuple(round(value, 5) for value in position)


def maya_snapshot(by_name=False):
    result = {}
    for shape in cmds.ls(type="mesh", long=True, noIntermediate=True) or []:
        selection = om.MSelectionList()
        selection.add(shape)
        path = selection.getDagPath(0)
        mesh = om.MFnMesh(path)
        clusters = cmds.ls(cmds.listHistory(shape), type="skinCluster") or []
        assert len(clusters) == 1, (shape, clusters)
        selection = om.MSelectionList()
        selection.add(clusters[0])
        skin = oma.MFnSkinCluster(selection.getDependNode(0))
        component = om.MFnSingleIndexedComponent()
        vertices = component.create(om.MFn.kMeshVertComponent)
        component.setCompleteData(mesh.numVertices)
        weights, count = skin.getWeights(path, vertices)
        by_bone = {}
        logical = []
        for index, bone in enumerate(skin.influenceObjects()):
            position = om.MFnTransform(bone).translation(om.MSpace.kWorld)
            key = bone.fullPathName().rsplit("|", 1)[-1] if by_name else identity(position)
            assert key not in by_bone, ("Fixture needs distinct bind positions", key)
            by_bone[key] = tuple(weights[index::count])
            logical.append(skin.indexForInfluenceObject(bone))
        counts, triangles = mesh.getTriangles()
        mesh_name = shape if by_name else mesh.name().rsplit(":", 1)[-1]
        assert mesh_name not in result, ("Mesh snapshot key collision", mesh_name)
        result[mesh_name] = {
            "mesh_name": mesh.name(),
            "positions": tuple(v for point in mesh.getPoints(om.MSpace.kWorld)
                               for v in (point.x, point.y, point.z)),
            "faces": tuple(triangles),
            "weights": by_bone,
            "method": cmds.getAttr(clusters[0] + ".skinningMethod"),
            "logical_indices": logical,
        }
    return result


def cast_snapshot(backend, path, by_name=False):
    document = backend.Cast.load(str(path))
    result = {}
    for root in document.Roots():
        for model in (node for node in root.childNodes if isinstance(node, backend.Model)):
            skeleton = model.Skeleton()
            bones = skeleton.Bones() if skeleton else []
            for mesh in model.Meshes():
                by_bone = {}
                slots = mesh.MaximumWeightInfluence()
                indices = mesh.VertexWeightBoneBuffer() or []
                values = mesh.VertexWeightValueBuffer() or []
                for vertex in range(mesh.VertexCount()):
                    for slot in range(slots):
                        offset = vertex * slots + slot
                        if values[offset] > 1e-8:
                            bone = bones[indices[offset]]
                            key = bone.Name() if by_name else identity(bone.WorldPosition())
                            by_bone.setdefault(key, [0.0] * mesh.VertexCount())[vertex] += values[offset]
                mesh_name = (mesh.Name() or ("unnamed_%d" % len(result))).rsplit(":", 1)[-1]
                if mesh_name in result:
                    mesh_name += "_%d" % len(result)
                result[mesh_name] = {
                    "mesh_name": mesh.Name(),
                    "positions": tuple(mesh.VertexPositionBuffer()),
                    "faces": tuple(mesh.FaceBuffer()),
                    "weights": by_bone,
                    "method": 1 if mesh.SkinningMethod() == "quaternion" else 0,
                }
    return result


def compare(expected, actual, label, match_mesh_data=False):
    if match_mesh_data:
        # Upstream deliberately omits generated CastShape names. Match the
        # complete mesh multiset instead of interpreting omitted names as loss.
        assert len(expected) == len(actual), (label, "mesh count", len(expected), len(actual), list(actual))
        remaining = dict(actual)
        for name, before in expected.items():
            errors = []
            candidates = sorted(remaining.items(), key=lambda item: (
                len(item[1]["positions"]) != len(before["positions"]),
                item[1]["faces"] != before["faces"]))
            for candidate, after in candidates:
                try:
                    compare({name: before}, {name: after}, label)
                except AssertionError as error:
                    errors.append(str(error))
                    continue
                del remaining[candidate]
                break
            else:
                raise AssertionError((label, name, "no unchanged mesh", errors[:2]))
        return
    assert set(expected) == set(actual), (label, "meshes", set(expected), set(actual))
    for name, before in expected.items():
        after = actual[name]
        if before.get("mesh_name") is not None:
            assert before["mesh_name"] == after.get("mesh_name"), (
                label, name, "mesh name", before["mesh_name"], after.get("mesh_name"))
        close(before["positions"], after["positions"], (label, name, "positions"))
        assert before["faces"] == after["faces"], (label, name, "topology")
        expected_bones = {bone for bone, values in before["weights"].items() if max(values) > 1e-8}
        actual_bones = {bone for bone, values in after["weights"].items() if max(values) > 1e-8}
        assert expected_bones == actual_bones, (label, name, "influence identity", expected_bones, actual_bones)
        for bone in expected_bones:
            close(before["weights"][bone], after["weights"][bone], (label, name, bone, "weights"))
        assert before["method"] == after["method"], (label, name, "skinning method", before["method"], after["method"])


def create_fixture(duplicate_names=False, method=0):
    cmds.file(new=True, force=True)
    first = cmds.createNode("joint", name="root_first")
    a = cmds.createNode("joint", name="duplicate_joint" if duplicate_names else "weight_a", parent=first)
    removed = cmds.createNode("joint", name="removed_influence", parent=first)
    second = cmds.createNode("joint", name="root_second")
    b = cmds.createNode("joint", name="duplicate_joint" if duplicate_names else "weight_b", parent=second)
    c = cmds.createNode("joint", name="weight_c", parent=second)
    a = cmds.ls(first + "|" + a.rsplit("|", 1)[-1], long=True)[0]
    b = cmds.ls(second + "|" + b.rsplit("|", 1)[-1], long=True)[0]
    c = cmds.rename(c, "weight_c_renamed")
    bones = [a, removed, b, c]
    for index, bone in enumerate([first, a, removed, second, b, c]):
        cmds.xform(bone, worldSpace=True, translation=(index * 2, 0, 0))
    for mesh_index in range(2):
        mesh = om.MFnMesh()
        shape = mesh.create([om.MPoint(0, mesh_index * 3, 0), om.MPoint(1, mesh_index * 3, 0),
                             om.MPoint(1, mesh_index * 3 + 1, 0), om.MPoint(0, mesh_index * 3 + 1, 0)],
                            [3, 3], [0, 1, 2, 0, 2, 3])
        transform = cmds.listRelatives(mesh.fullPathName(), parent=True, fullPath=True)[0]
        transform = cmds.rename(transform, "weighted_mesh_%d" % mesh_index)
        shape_name = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        cmds.rename(shape_name, "weighted_shape_%d" % mesh_index)
        cluster = cmds.skinCluster(bones, transform, toSelectedBones=True, normalizeWeights=0)[0]
        cmds.skinCluster(cluster, edit=True, removeInfluence=removed)
        # Re-add at a different slot, then remove it to retain a real logical gap.
        cmds.skinCluster(cluster, edit=True, addInfluence=removed, weight=0)
        cmds.skinCluster(cluster, edit=True, removeInfluence=removed)
        for vertex, weights in enumerate(((0.2, 0.7, 0.1), (0.6, 0.15, 0.25),
                                          (0.1, 0.3, 0.6), (0.35, 0.45, 0.2))):
            cmds.skinPercent(cluster, "%s.vtx[%d]" % (transform, vertex),
                             transformValue=list(zip([a, b, c], weights)), normalize=False)
        cmds.setAttr(cluster + ".skinningMethod", method)
    if duplicate_names:
        # Maya's bind command may uniquify influences; restore DAG leaf-name
        # collisions after binding to exercise the exporter, not the binder.
        cmds.rename(a, "duplicate_joint")
        cmds.rename(b, "duplicate_joint")
        assert len(cmds.ls("duplicate_joint", long=True)) == 2
        # Do not steal the original name of an unrelated numbered bone.
        reserved = cmds.createNode("joint", name="duplicate_joint1")
        cmds.xform(reserved, worldSpace=True, translation=(20, 0, 0))
    snapshot = maya_snapshot()
    assert all(record["logical_indices"] != list(range(3)) for record in snapshot.values()), snapshot
    return snapshot


def export(path):
    with core._temporary_cast_export_settings():
        cmds.file(str(path), force=True, type=core.cast_translator_name(), exportAll=True)


def verify_rejection(backend, folder, mode):
    create_fixture(duplicate_names=mode == "animation_duplicate")
    selected = False
    animation = False
    if mode == "missing":
        cmds.select("root_first", "weighted_mesh_0", replace=True)
        selected = True
        expected_message = "missing from exported skeleton"
    elif mode == "transform":
        influence = cmds.createNode("transform", name="transform_influence")
        cluster = (cmds.ls(type="skinCluster") or [])[0]
        cmds.skinCluster(cluster, edit=True, addInfluence=influence, weight=0)
        cmds.skinPercent(cluster, "weighted_mesh_0.vtx[0]", transformValue=[(influence, 0.25)], normalize=False)
        expected_message = "Non-joint"
    elif mode == "blended":
        assert mode == "blended"
        for cluster in cmds.ls(type="skinCluster"):
            cmds.setAttr(cluster + ".skinningMethod", 2)
        expected_message = "blended"
    else:
        assert mode == "animation_duplicate"
        animation = True
        cmds.setKeyframe("|root_first|duplicate_joint", attribute="ty", time=1, value=0)
        cmds.setKeyframe("|root_first|duplicate_joint", attribute="ty", time=2, value=1)
        expected_message = "duplicate bone names"
    path = folder / ("rejected_" + mode + ".cast")
    try:
        with core._temporary_cast_export_settings(animation=animation):
            backend.exportCast(str(path), selected)
    except RuntimeError as error:
        assert expected_message.lower() in str(error).lower(), (mode, str(error))
    else:
        raise AssertionError("Unsafe CAST export was not rejected: " + mode)
    assert not path.exists(), "Failed export wrote a corrupt CAST"
    print("CAST_UNSAFE_SKIN_EXPORT_REJECTED", mode)


def verify_real(backend, folder, path):
    path = Path(path)
    before_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    original = cast_snapshot(backend, path, by_name=True)
    cmds.file(new=True, force=True)
    core.import_cast_file(str(path))
    before = maya_snapshot(by_name=True)
    comparison_errors = []
    phases = {}

    def record(label, snapshot):
        try:
            compare(original, snapshot, path.name + " " + label, match_mesh_data=True)
            phases[label] = "passed"
        except AssertionError as error:
            comparison_errors.append(str(error))
            phases[label] = str(error)

    def bone_names(snapshot):
        return sorted({name for mesh in snapshot.values() for name in mesh["weights"]})

    names = {"original_cast": bone_names(original), "first_import": bone_names(before)}
    record("original CAST import", before)
    first = folder / (path.stem + "_first.cast")
    second = folder / (path.stem + "_second.cast")
    export(first)
    exported = cast_snapshot(backend, first, by_name=True)
    names["first_export"] = bone_names(exported)
    record("first export", exported)
    cmds.file(new=True, force=True)
    core.import_cast_file(str(first))
    imported = maya_snapshot(by_name=True)
    names["second_import"] = bone_names(imported)
    record("second import", imported)
    export(second)
    exported = cast_snapshot(backend, second, by_name=True)
    names["second_export"] = bone_names(exported)
    record("second export", exported)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_sha
    print("CAST_REAL_SKIN_ROUNDTRIP_" + ("FAILED" if comparison_errors else "OK"),
          path.name, len(before), "meshes", before_sha)
    return {"path": str(path.resolve()), "sha256": before_sha,
            "mesh_count": len(before), "source_unchanged": True,
            "import_route": "default import_cast_file gateway",
            "bone_names_compared_verbatim": True,
            "phases": phases, "comparison_errors": comparison_errors,
            "weighted_bone_names": names,
            "original_mesh_names": [mesh["mesh_name"] for mesh in original.values()],
            "first_import_mesh_names": [mesh["mesh_name"] for mesh in before.values()],
            "full_vertex_weights_positions_topology_method": "failed" if comparison_errors else "passed"}


def main():
    global core
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("sparse", "duplicate", "dqs", "all", "guards", "real"), default="all")
    parser.add_argument("--plugin", type=Path, default=ROOT / "plug-ins/viewmodel_weapon_toolkit.py")
    parser.add_argument("--report", type=Path)
    parser.add_argument("inputs", nargs="*")
    args = parser.parse_args()
    plugin = args.plugin.resolve()
    cmds.loadPlugin(str(plugin), quiet=True)
    namespace = loaded_plugin_globals(plugin)
    core = namespace["_core_runtime"]()
    assert Path(core._TOOLKIT_PLUGIN_PATH).resolve() == plugin
    backend = core._castplugin_module()
    failures = []
    report = {"plugin": str(plugin), "version": core.VERSION,
              "backend": core._cast_backend().info(), "synthetic": [],
              "guards": [], "real": []}
    with tempfile.TemporaryDirectory(prefix="cast_skin_roundtrip_") as temporary:
        folder = Path(temporary)
        cases = [("sparse", False, 0), ("duplicate", True, 0), ("dqs", False, 1)]
        for name, duplicate, method in cases:
            if args.case not in ("all", name):
                continue
            try:
                before = create_fixture(duplicate, method)
                first = folder / (name + "_first.cast")
                second = folder / (name + "_second.cast")
                original_joint_paths = sorted(cmds.ls(type="joint", long=True))
                export(first)
                assert sorted(cmds.ls(type="joint", long=True)) == original_joint_paths, "CAST export renamed scene joints"
                model = next(node for node in backend.Cast.load(str(first)).Roots()[0].childNodes
                             if isinstance(node, backend.Model))
                bone_names = [bone.Name() for bone in model.Skeleton().Bones()]
                assert len(bone_names) == len(original_joint_paths), "CAST export lost a skeleton bone"
                assert len(set(bone_names)) == len(bone_names), "Duplicate exported bone names"
                if duplicate:
                    assert {"duplicate_joint", "duplicate_joint1", "duplicate_joint2"}.issubset(bone_names)
                compare(before, cast_snapshot(backend, first), name + " export")
                cmds.file(new=True, force=True)
                core.import_cast(str(first), "fixture")
                compare(before, maya_snapshot(), name + " import")
                export(second)
                compare(before, cast_snapshot(backend, second), name + " re-export")
                print("CAST_SKIN_ROUNDTRIP_OK", name)
                report["synthetic"].append({"case": name, "result": "passed", "mesh_count": len(before)})
            except Exception as error:
                failures.append((name, str(error)))
                print("CAST_SKIN_ROUNDTRIP_FAILED", name, repr(error))
        if args.case in ("all", "guards"):
            for mode in ("missing", "transform", "blended", "animation_duplicate"):
                try:
                    verify_rejection(backend, folder, mode)
                    report["guards"].append({"case": mode, "result": "passed"})
                except Exception as error:
                    failures.append((mode, str(error)))
                    print("CAST_SKIN_GUARD_FAILED", mode, repr(error))
        for path in args.inputs:
            try:
                result = verify_real(backend, folder, path)
                report["real"].append(result)
                if result["comparison_errors"]:
                    failures.append((str(path), result["comparison_errors"]))
            except Exception as error:
                failures.append((str(path), str(error)))
                print("CAST_REAL_SKIN_ROUNDTRIP_FAILED", path, repr(error))
    report["failures"] = failures
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert not failures, json.dumps(failures)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
