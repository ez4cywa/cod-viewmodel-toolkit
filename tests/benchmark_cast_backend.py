"""Mayapy benchmark for the immutable 3.4.3 backend and the working tree.

Each invocation loads exactly one implementation. Run both revisions in separate
processes, then compare their JSON snapshots; startup, fixture creation and
snapshot collection are excluded. Profiling is a separate, untimed pass.
"""
import argparse
import cProfile
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import types
from contextlib import contextmanager

import maya.standalone
import maya.cmds as cmds
if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "5d545521311c3689ba287f3fcd71db6968939dda"
sys.path.insert(0, str(ROOT / "tests"))
from benchmark_cast_import import snapshot
from verify_batch_animation_export import make_animation, make_model
from verify_maya_drop_module_path import loaded_plugin_globals, accepted_drop


@contextmanager
def implementation(revision):
    """Materialize immutable tracked inputs without trusting live backend files."""
    if revision == "current":
        yield ROOT
        return
    with tempfile.TemporaryDirectory(prefix="cod_cast_343_") as temporary:
        directory = Path(temporary)
        paths = subprocess.check_output([
            "git", "ls-tree", "-r", "--name-only", BASELINE,
            "plug-ins", "third_party/cast"], cwd=str(ROOT)).decode().splitlines()
        for relative in paths:
            if Path(relative).suffix not in (".py", ".mel", ".cfg"):
                continue
            destination = directory / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(subprocess.check_output([
                "git", "show", BASELINE + ":" + relative], cwd=str(ROOT)))
        yield directory


def load_core(directory):
    plugin = directory / "plug-ins" / "viewmodel_weapon_toolkit.py"
    # The old backend imports a top-level cast module. Resolve it exclusively
    # from the immutable tree, never the currently installed Maya copy.
    sys.path.insert(0, str(directory / "third_party" / "cast"))
    sys.modules.pop("cast", None)
    sys.modules.pop("castplugin", None)
    cmds.loadPlugin(str(plugin), quiet=True)
    return types.SimpleNamespace(**loaded_plugin_globals(plugin))


@contextmanager
def phase_profile(backend):
    totals = {}
    originals = []
    def wrap(owner, name, phase):
        original = getattr(owner, name)
        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return original(*args, **kwargs)
            finally:
                value = totals.setdefault(phase, {"seconds": 0.0, "calls": 0})
                value["seconds"] += time.perf_counter() - start
                value["calls"] += 1
        originals.append((owner, name, original))
        setattr(owner, name, timed)
    for name, phase in (("importModelNode", "model_inclusive"),
                        ("importMaterialNode", "materials"),
                        ("importSkeletonNode", "skeleton"),
                        ("utilityCreateSkinCluster", "binding"),
                        ("utilitySetSkinWeights", "set_weights"),
                        ("importAnimationNode", "animation_inclusive"),
                        ("utilityGetOrCreateCurve", "curve_lookup")):
        wrap(backend, name, phase)
    wrap(backend.Cast, "load", "parse")
    try:
        yield totals
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, staticmethod(original) if owner is backend.Cast else original)


def make_dense_animation(core, path, bones, frames):
    """Deterministic scalar/quaternion channels, not game data."""
    make_animation(core, path, frames - 1,
                   [("j_slide", "tz", 1, 4, "absolute")])
    document = core._castplugin_module().Cast.load(str(path))
    animation = document.Roots()[0].ChildrenOfType(core._castplugin_module().Animation)[0]
    for index in range(bones):
        for prop in ("tx", "ty", "tz", "rq"):
            curve = animation.CreateCurve()
            curve.SetNodeName("bench_bone_%03d" % index)
            curve.SetKeyPropertyName(prop)
            curve.SetMode("absolute")
            curve.SetKeyFrameBuffer(list(range(frames)))
            if prop == "rq":
                curve.SetVec4KeyValueBuffer([
                    (0.0, math.sin(frame * 0.0005), 0.0,
                     math.cos(frame * 0.0005)) for frame in range(frames)])
            else:
                curve.SetFloatKeyValueBuffer([
                    index * 0.01 + frame * 0.001 for frame in range(frames)])
    document.save(str(path))


def prepare_animation(core, directory, bones):
    hands, weapon = directory / "hands.cast", directory / "weapon.cast"
    if not hands.exists():
        make_model(core, hands, True)
        make_model(core, weapon, False)
    result = core._build_single_attachment(str(hands), str(weapon),
        core.AttachOptions(force_new_scene=True, export_cast=False))
    for index in range(bones):
        joint = cmds.createNode("joint", name="bench_bone_%03d" % index)
        cmds.setAttr(joint + ".jointOrientY", index % 17)
    return result


def animation_snapshot(frames):
    joints = sorted(cmds.ls("bench_bone_*", type="joint", long=True))
    times = sorted(set([0, frames // 2, frames - 1]))
    result = {"matrices": {}, "channels": {}}
    for frame in times:
        cmds.currentTime(frame)
        result["matrices"][str(frame)] = {
            node: cmds.xform(node, query=True, worldSpace=True, matrix=True)
            for node in joints}
    for node in joints:
        for attribute in ("tx", "ty", "tz", "rx", "ry", "rz"):
            plug = node + "." + attribute
            curves = cmds.listConnections(plug, source=True, destination=False, type="animCurve") or []
            assert len(curves) == 1, (plug, curves)
            result["channels"][plug] = {
                "times": cmds.keyframe(curves[0], query=True, timeChange=True),
                "values": cmds.keyframe(curves[0], query=True, valueChange=True),
                "in_tangents": cmds.keyTangent(curves[0], query=True, inTangentType=True),
                "out_tangents": cmds.keyTangent(curves[0], query=True, outTangentType=True),
            }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", choices=("baseline", "current"), required=True)
    parser.add_argument("--models", nargs=2)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--bones", type=int, default=200)
    parser.add_argument("--frames", type=int, default=240)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--skip-animation", action="store_true")
    args = parser.parse_args()
    result = {"revision": BASELINE if args.revision == "baseline" else "current",
              "maya": cmds.about(version=True), "python": sys.version,
              "samples": {}, "profiles": {}, "snapshots": {}}
    with implementation(args.revision) as directory:
        core = load_core(directory)
        backend = core._castplugin_module()
        result["cast_version"] = backend.version
        with tempfile.TemporaryDirectory(prefix="cod_cast_bench_") as temporary:
            fixture = Path(temporary)
            operations = {}
            if args.models:
                def attach():
                    built = core._build_single_attachment(*args.models,
                        core.AttachOptions(force_new_scene=True, export_cast=False))
                    assert built.translation == (0.0, 0.0, 0.0)
                operations["attachment"] = (lambda: cmds.file(new=True, force=True), attach, snapshot)
                for number, model in enumerate(args.models):
                    operations["model_%d" % number] = (
                        lambda: cmds.file(new=True, force=True),
                        lambda model=model: core.import_cast(model, "fixture"), snapshot)
            if not args.skip_animation:
                clip = fixture / "dense.cast"
                make_dense_animation(core, clip, args.bones, args.frames)
                operations["safe_animation_drop"] = (
                    lambda: prepare_animation(core, fixture, args.bones),
                    lambda: accepted_drop(core, clip),
                    lambda: animation_snapshot(args.frames))
            for name, (prepare, operation, capture) in operations.items():
                samples = []
                for iteration in range(args.runs):
                    prepare()
                    start = time.perf_counter()
                    operation()
                    samples.append(time.perf_counter() - start)
                    actual = capture()
                    if iteration:
                        assert actual == result["snapshots"][name], name + " nondeterministic scene"
                    result["snapshots"][name] = actual
                result["samples"][name] = samples
                prepare()
                profiler = cProfile.Profile()
                with phase_profile(backend) as phases:
                    profiler.runcall(operation)
                result["profiles"][name] = phases
                result["profiles"][name]["top_work_functions"] = [
                    {"function": entry.code.co_name, "seconds": entry.totaltime,
                     "own_seconds": entry.inlinetime, "calls": entry.callcount}
                    for entry in sorted(profiler.getstats(), key=lambda item: item.totaltime, reverse=True)
                    if isinstance(entry.code, types.CodeType) and
                    Path(entry.code.co_filename).name in (
                        "viewmodel_weapon_toolkit.py", "castplugin.py", "cod_viewmodel_cast_backend.py")][:20]
    result["medians"] = {name: statistics.median(values) for name, values in result["samples"].items()}
    if args.compare:
        expected = json.loads(args.compare.read_text(encoding="utf-8"))
        assert result["snapshots"] == {name: expected["snapshots"][name]
            for name in result["snapshots"]}, "Scene differs from comparison baseline"
        result["scene_equivalence"] = True
        result["ratios"] = {name: median / expected["medians"][name]
                            for name, median in result["medians"].items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("CAST_BACKEND_BENCHMARK", json.dumps({key: value for key, value in result.items()
        if key not in ("snapshots", "profiles")}))
    print("CAST_BACKEND_PROFILE", json.dumps(result["profiles"]))


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
