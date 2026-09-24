"""Mayapy: compare CAST import to the immutable 3.4.2 baseline in fresh scenes.

Pass model paths after --models. Timings exclude snapshots and Maya startup.
"""
import argparse
import hashlib
import json
import statistics
import struct
import subprocess
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

import maya.standalone
import maya.cmds as cmds
if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "e49fd4c76ff221ff175bec4980ff33b21b3fd907"
sys.path.insert(0, str(ROOT / "plug-ins"))
import viewmodel_weapon_toolkit as core


def baseline_module(relative, name):
    module = types.ModuleType(name)
    module.__file__ = str(ROOT / relative)
    sys.modules[name] = module
    source = subprocess.check_output(["git", "show", BASELINE + ":" + relative], cwd=str(ROOT))
    exec(compile(source, name + ".py", "exec"), module.__dict__)
    return module


def digest(values):
    values = list(values)
    return hashlib.sha256(struct.pack("<%dd" % len(values), *values)).hexdigest()


def snapshot():
    result = {}
    for name in cmds.ls(type="mesh", long=True, noIntermediate=True):
        selection = om.MSelectionList()
        selection.add(name)
        path = selection.getDagPath(0)
        mesh = om.MFnMesh(path)
        counts, indices = mesh.getVertices()
        record = {
            "points": digest(v for p in mesh.getPoints(om.MSpace.kWorld) for v in p),
            "normals": digest(v for p in mesh.getNormals() for v in p),
            "normal_ids": [list(a) for a in mesh.getNormalIds()],
            "topology": digest(list(counts) + list(indices)),
            "uv": {}, "colors": {},
            "materials": sorted(cmds.listConnections(name, type="shadingEngine") or []),
        }
        for uv in mesh.getUVSetNames():
            u, v = mesh.getUVs(uv)
            counts, indices = mesh.getAssignedUVs(uv)
            record["uv"][uv] = [digest(u), digest(v), digest(counts), digest(indices)]
        for color in mesh.getColorSetNames():
            record["colors"][color] = digest(v for c in mesh.getVertexColors(color) for v in c)
        result[name] = record
    for name in cmds.ls(type="skinCluster"):
        selection = om.MSelectionList()
        selection.add(name)
        skin = oma.MFnSkinCluster(selection.getDependNode(0))
        shape = skin.getPathAtIndex(0)
        component = om.MFnSingleIndexedComponent()
        vertices = component.create(om.MFn.kMeshVertComponent)
        component.setCompleteData(om.MFnMesh(shape).numVertices)
        weights, count = skin.getWeights(shape, vertices)
        result[name] = {
            "method": cmds.getAttr(name + ".skinningMethod"),
            "weights": {bone.fullPathName(): digest(weights[i::count])
                        for i, bone in enumerate(skin.influenceObjects())},
        }
    for name in cmds.ls(type="joint", long=True):
        result[name] = cmds.xform(name, query=True, worldSpace=True, matrix=True)
    for name in cmds.ls(type="file"):
        result[name] = [cmds.getAttr(name + ".fileTextureName"),
                        cmds.getAttr(name + ".colorSpace")]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-ratio", type=float)
    parser.add_argument("--attachment", action="store_true",
                        help="Measure the complete hands/weapon build including preflight")
    args = parser.parse_args()
    cmds.loadPlugin(core.__file__, quiet=True)
    backend = core._castplugin_module()
    baseline = baseline_module("third_party/cast/castplugin.py", "cast_342_baseline")
    baseline.__file__ = backend.__file__
    baseline.sceneSettings = backend.sceneSettings
    old_core = baseline_module("plug-ins/viewmodel_weapon_toolkit.py", "toolkit_342_baseline")
    if args.attachment:
        assert len(args.models) == 2, "Provide hands then weapon"
    timings = {"baseline": [], "current": []}
    expected = {}
    for iteration in range(args.runs):
        # Alternate order to reduce filesystem/cache ordering bias.
        order = ("baseline", "current") if iteration % 2 == 0 else ("current", "baseline")
        for mode in order:
            elapsed = 0.0
            for path in (["attachment"] if args.attachment else args.models):
                cmds.file(new=True, force=True)
                importer = baseline.importModelNode if mode == "baseline" else backend.importModelNode
                with patch.object(backend, "importModelNode", importer):
                    start = time.perf_counter()
                    if args.attachment:
                        builder = old_core if mode == "baseline" else core
                        result = builder._build_single_attachment(*args.models,
                            builder.AttachOptions(force_new_scene=True, export_cast=False))
                        assert result.translation == (0.0, 0.0, 0.0)
                    else:
                        core.import_cast(path, "fixture")
                    elapsed += time.perf_counter() - start
                actual = snapshot()
                if path not in expected:
                    expected[path] = actual
                assert actual == expected[path], "Scene differs from baseline: " + path
            timings[mode].append(elapsed)
    medians = {key: statistics.median(values) for key, values in timings.items()}
    ratio = medians["current"] / medians["baseline"]
    print("CAST_IMPORT_BENCHMARK", json.dumps({"samples": timings, "medians": medians,
                                            "ratio": ratio, "scene_equivalence": True}))
    if args.max_ratio is not None:
        assert ratio <= args.max_ratio, (ratio, args.max_ratio)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
