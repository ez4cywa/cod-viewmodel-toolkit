"""Mayapy: plain CAST names and independent duplicate skeleton/skin graphs.

Fixtures live in a temporary directory. Optional --model inputs are read-only;
only --report writes persistent QA evidence. No scene or model is exported.
"""

import argparse
from array import array
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

import maya.cmds as cmds
import maya.standalone
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_cast_import_gateway import material_graph, shader_links
from verify_empty_material_host import make_fixture, file_digest
from verify_maya_drop_module_path import loaded_plugin_globals
from verify_standalone_export_host import assert_preserved, snapshot


def uuid_of(node):
    values = cmds.ls(node, uuid=True) or []
    assert len(values) == 1, (node, values)
    return values[0]


def leaf(node):
    return node.rsplit("|", 1)[-1]


def values_digest(values):
    return hashlib.sha256(array("d", values).tobytes()).hexdigest()


def node_uuid_map():
    return {uuid_of(node): node for node in cmds.ls(long=True) or []}


def assert_plain_report(report):
    assert report["namespace"] == "", (
        "Default CAST import retained a namespace prefix", report["namespace"])
    assert report["nodes"] and all(":" not in leaf(node)
                                   for node in report["nodes"]), report["nodes"]


def namespace_state():
    return (cmds.namespaceInfo(currentNamespace=True, absoluteName=True),
            cmds.namespace(query=True, relativeNames=True),
            tuple(sorted(cmds.namespaceInfo(":", listOnlyNamespaces=True,
                                            recurse=True) or [])))


def ordered_dag_nodes(report):
    """Pair repeated inputs by unchanged DAG sibling order, never name guessing."""
    imported = {uuid_of(node) for node in report["nodes"]}
    result = []
    for root in cmds.ls(assemblies=True, long=True) or []:
        if uuid_of(root) not in imported:
            continue
        result.extend(node for node in [root] + (cmds.listRelatives(
            root, allDescendents=True, fullPath=True) or []) if uuid_of(node) in imported)
    return result


def duplicate_name_map(first, second, source_mesh_names):
    original = ordered_dag_nodes(first)
    duplicate = ordered_dag_nodes(second)
    assert len(original) == len(duplicate), (len(original), len(duplicate))
    result = {}
    for old, new in zip(original, duplicate):
        assert cmds.nodeType(old) == cmds.nodeType(new), (old, new)
        old_leaf, new_leaf = leaf(old), leaf(new)
        if cmds.nodeType(old) != "mesh":
            # Unnamed CAST meshes use Maya's CastMesh<number> allocator; there
            # is no source name to retain. Shapes are likewise internal names.
            unnamed_mesh = (cmds.listRelatives(old, shapes=True, type="mesh")
                            and old_leaf not in source_mesh_names)
            expression = r"CastMesh\d*" if unnamed_mesh else re.escape(old_leaf) + r"\d+"
            assert re.fullmatch(expression, new_leaf), (
                "Duplicate name did not append digits", old, new)
        result[new_leaf] = old_leaf
    return result


def skin_data(report, names=None):
    """Record every vertex weight keyed by bone identity, not influence slot."""
    result = {}
    for name in report["nodes"]:
        if cmds.nodeType(name) != "mesh" or cmds.getAttr(name + ".intermediateObject"):
            continue
        transform = cmds.listRelatives(name, parent=True, fullPath=True)[0]
        key = leaf(transform)
        if names is not None:
            key = names[key]
        clusters = [node for node in cmds.listHistory(name) or []
                    if cmds.nodeType(node) == "skinCluster"]
        assert len(clusters) == 1, (name, clusters)
        selection = om.MSelectionList()
        selection.add(name)
        path = selection.getDagPath(0)
        mesh = om.MFnMesh(path)
        selection = om.MSelectionList()
        selection.add(clusters[0])
        skin = oma.MFnSkinCluster(selection.getDependNode(0))
        component = om.MFnSingleIndexedComponent()
        vertices = component.create(om.MFn.kMeshVertComponent)
        component.setCompleteData(mesh.numVertices)
        weights, count = skin.getWeights(path, vertices)
        counts, indices = mesh.getVertices()
        record = {"weights": {}, "method": cmds.getAttr(clusters[0] + ".skinningMethod"),
                  "vertex_count": mesh.numVertices,
                  "geometry": values_digest(value for point in mesh.getPoints(om.MSpace.kObject)
                                            for value in (point.x, point.y, point.z)),
                  "topology": values_digest(list(counts) + list(indices)),
                  "cluster_uuid": uuid_of(clusters[0]),
                  "mesh_uuid": uuid_of(name),
                  "influence_uuids": [], "parents": {}}
        for index, bone in enumerate(skin.influenceObjects()):
            bone_name = leaf(bone.fullPathName())
            canonical = names[bone_name] if names is not None else bone_name
            record["weights"][canonical] = values_digest(weights[index::count])
            record["influence_uuids"].append(uuid_of(bone.fullPathName()))
            parent = cmds.listRelatives(bone.fullPathName(), parent=True,
                                        fullPath=True) or []
            parent_name = leaf(parent[0]) if parent else ""
            if names is not None and parent_name:
                parent_name = names[parent_name]
            record["parents"][canonical] = parent_name
        assert key not in result, ("Duplicate mesh name in one report", key)
        result[key] = record
    assert result, "CAST import created no skinned mesh"
    return result


def world_points(report):
    result = {}
    for node in report["nodes"]:
        if cmds.nodeType(node) != "mesh" or cmds.getAttr(node + ".intermediateObject"):
            continue
        selection = om.MSelectionList()
        selection.add(node)
        points = om.MFnMesh(selection.getDagPath(0)).getPoints(om.MSpace.kWorld)
        result[uuid_of(node)] = tuple((point.x, point.y, point.z) for point in points)
    return result


def verify_duplicate(core, path):
    cmds.file(new=True, force=True)
    before_digest = file_digest(path)
    first = core.import_cast_file(str(path))
    assert_plain_report(first)
    if path.name == "synthetic.cast":
        assert cmds.objExists("fixture_root") and cmds.objExists("fixture_tip")
        assert cmds.objExists("fixture_mesh_LOD0")
        shapes = [node for node in first["nodes"] if cmds.nodeType(node) == "mesh"
                  and not cmds.getAttr(node + ".intermediateObject")]
        assert len(shapes) == 1
        assert leaf(shapes[0]) == leaf(cmds.listRelatives(
            shapes[0], parent=True, fullPath=True)[0]), (
                "First import renamed a same-named mesh shape", shapes[0])
    first_nodes = {uuid_of(node): node for node in first["nodes"]}
    first_graph, first_shaders = material_graph(), shader_links()
    first_skin = skin_data(first)
    first_points = world_points(first)
    serializer = core._cast_backend().serializer
    document = serializer.Cast.load(str(path))
    source_mesh_names = {mesh.Name() for root in document.Roots()
                         for model in root.ChildrenOfType(serializer.Model)
                         for mesh in model.Meshes() if mesh.Name()}
    cmds.namespace(addNamespace="caller")
    cmds.namespace(setNamespace=":caller")
    cmds.namespace(relativeNames=True)
    state = namespace_state()
    second = core.import_cast_file(str(path))
    assert namespace_state() == state, (state, namespace_state())
    cmds.namespace(relativeNames=False)
    cmds.namespace(setNamespace=":")
    assert_plain_report(second)
    if path.name == "synthetic.cast":
        assert cmds.objExists("fixture_root1") and cmds.objExists("fixture_tip1")
        mesh_transforms = [leaf(cmds.listRelatives(node, parent=True, fullPath=True)[0])
                           for node in second["nodes"] if cmds.nodeType(node) == "mesh"]
        assert any(re.fullmatch(r"fixture_mesh_LOD0\d+", name)
                   for name in mesh_transforms), "Source numeric ending was replaced instead of appended"
        shapes = [node for node in second["nodes"] if cmds.nodeType(node) == "mesh"
                  and not cmds.getAttr(node + ".intermediateObject")]
        assert len(shapes) == 1 and leaf(shapes[0]) == leaf(cmds.listRelatives(
            shapes[0], parent=True, fullPath=True)[0]), (
                "Duplicate shape and transform received different suffixes", shapes)
    actual_nodes = node_uuid_map()
    assert all(actual_nodes.get(key) == value
               for key, value in first_nodes.items()), "First import node identity/name changed"
    actual_graph, actual_shaders = material_graph(), shader_links()
    for node, data in first_graph.items():
        assert actual_graph[node] == data, ("First material utility changed", node)
    for node, data in first_shaders.items():
        assert actual_shaders[node] == data, ("First shader changed", node)
    assert skin_data(first) == first_skin, "Duplicate import changed first skin data"
    second_skin = skin_data(second, duplicate_name_map(first, second, source_mesh_names))
    assert first_skin.keys() == second_skin.keys()
    for name in first_skin:
        a, b = first_skin[name], second_skin[name]
        for field in ("weights", "method", "vertex_count", "parents", "geometry", "topology"):
            assert a[field] == b[field], (name, field, a[field], b[field])
        assert a["cluster_uuid"] != b["cluster_uuid"]
        assert not set(a["influence_uuids"]) & set(b["influence_uuids"])
    first_groups = {uuid_of(node) for node in first["nodes"]
                    if cmds.nodeType(node) in ("shadingEngine", "standardSurface")}
    second_groups = {uuid_of(node) for node in second["nodes"]
                     if cmds.nodeType(node) in ("shadingEngine", "standardSurface")}
    assert not first_groups & second_groups, "Duplicate imports share material nodes"
    second_before = world_points(second)
    roots = [node for node in second["nodes"] if cmds.nodeType(node) == "joint"
             and not (cmds.listRelatives(node, parent=True, type="joint") or [])]
    assert roots, "Duplicate skeleton has no root joint"
    for root in roots:
        cmds.setAttr(root + ".tx", cmds.getAttr(root + ".tx") + 3)
    assert world_points(first) == first_points, "Moving duplicate skeleton moved first model"
    assert world_points(second) != second_before, "Duplicate skeleton did not deform its own model"
    assert file_digest(path) == before_digest
    report = {"path": str(path), "input_sha256": before_digest,
              "mesh_count_per_import": len(first_skin),
              "joint_count_per_import": sum(cmds.nodeType(node) == "joint"
                                             for node in first["nodes"]),
              "vertex_influence_values_compared": sum(data["vertex_count"] * len(data["weights"])
                                                        for data in first_skin.values()),
              "all_vertex_weights_equal": True,
              "skeletons_materials_and_skin_clusters_independent": True,
              "moving_duplicate_preserves_first": True,
              "source_unchanged": True}
    print("CAST_DUPLICATE_NAMES_OK", json.dumps(report, sort_keys=True), flush=True)
    return report


def verify_rename_rollback(core, path):
    cmds.file(new=True, force=True)
    first = core.import_cast_file(str(path))
    assert_plain_report(first)
    cmds.namespace(addNamespace="rollback_caller")
    cmds.namespace(setNamespace=":rollback_caller")
    cmds.namespace(relativeNames=True)
    before = snapshot()
    identities, graph, shaders, state = node_uuid_map(), material_graph(), shader_links(), namespace_state()
    original = cmds.rename
    phase = {"moved": 0}

    def fail_rename(node, name, *args, **kwargs):
        if ":" in leaf(str(node)) and ":" not in str(name).lstrip(":"):
            if phase["moved"] >= 2:
                raise RuntimeError("Injected namespace removal rename failure")
            result = original(node, name, *args, **kwargs)
            phase["moved"] += 1
            return result
        return original(node, name, *args, **kwargs)

    with patch.object(cmds, "rename", side_effect=fail_rename):
        try:
            core.import_cast_file(str(path))
        except RuntimeError as error:
            assert "Injected namespace removal rename failure" in str(error), error
        else:
            raise AssertionError("Namespace-removal rename failure was not exercised")
    assert phase["moved"] == 2, phase
    assert_preserved(before, snapshot())
    assert node_uuid_map() == identities, "Rename rollback deleted/replaced existing nodes"
    assert material_graph() == graph and shader_links() == shaders
    assert namespace_state() == state
    cmds.namespace(relativeNames=False)
    cmds.namespace(setNamespace=":")
    print("CAST_DUPLICATE_RENAME_ROLLBACK_OK", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin", type=Path,
                        default=ROOT / "plug-ins/viewmodel_weapon_toolkit.py")
    parser.add_argument("--model", type=Path, action="append", default=[])
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    plugin = args.plugin.resolve()
    cmds.loadPlugin(str(plugin), quiet=True)
    namespace = loaded_plugin_globals(plugin)
    core = namespace["_core_runtime"]()
    assert Path(core._TOOLKIT_PLUGIN_PATH).resolve() == plugin
    assert not core._is_plugin_loaded("castplugin")
    cmds.loadPlugin("lookdevKit", quiet=True)
    report = {"plugin": str(plugin), "version": core.VERSION, "duplicates": []}
    with tempfile.TemporaryDirectory(prefix="cod_cast_duplicates_") as temporary:
        path = Path(temporary) / "synthetic.cast"
        serializer = core._cast_backend().serializer
        make_fixture(serializer, path, "valid")
        document = serializer.Cast.load(str(path))
        document.Roots()[0].ChildrenOfType(serializer.Model)[0].Meshes()[0].SetName("fixture_mesh_LOD0")
        document.save(str(path))
        report["duplicates"].append(verify_duplicate(core, path))
        verify_rename_rollback(core, path)
        for path in args.model:
            report["duplicates"].append(verify_duplicate(core, path.resolve()))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    print("CAST_DUPLICATE_HOST_OK", core.VERSION, flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
