"""Mayapy regression: a safe animation drop parses a CAST file exactly once.

Use --revision baseline to reproduce the four-read behavior in immutable 3.4.3.
Synthetic inputs are temporary and the actual external-drop callback is used.
"""
import argparse
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import maya.cmds as cmds
import maya.standalone
from benchmark_cast_backend import implementation, load_core, prepare_animation
from verify_batch_animation_export import make_animation
from verify_maya_drop_module_path import accepted_drop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", choices=("baseline", "current"), default="current")
    parser.add_argument("--expected-reads", type=int, default=1)
    args = parser.parse_args()
    with implementation(args.revision) as directory:
        core = load_core(directory)
        backend = core._castplugin_module()
        with tempfile.TemporaryDirectory(prefix="cod_cast_read_session_") as temporary:
            fixture = Path(temporary)
            clip = fixture / "single.cast"
            prepare_animation(core, fixture, 0)
            make_animation(core, clip, 8, [
                ("j_gun", "tx", 0, 8, "absolute"),
                ("j_slide", "tz", 1, 4, "absolute")])
            with patch.object(cmds, "rename", wraps=cmds.rename) as rename, \
                    patch.object(backend.Cast, "load", wraps=backend.Cast.load) as load, \
                    patch.object(cmds, "keyframe", wraps=cmds.keyframe) as keyframe:
                accepted_drop(core, clip)
                first = load.call_count
                time_queries = sum(1 for call in keyframe.call_args_list
                    if call.kwargs.get("query") and call.kwargs.get("timeChange"))
                assert abs(cmds.getAttr("viewhands_j_gun.tx", time=8) - 8) < 1e-6
                assert abs(cmds.getAttr("j_slide.tz", time=8) - 4) < 1e-6
                assert max(abs(v) for v in cmds.getAttr("j_gun.translate", time=8)[0]) < 1e-6
                print("ANIMATION_READ_SESSION", json.dumps({
                    "revision": args.revision, "physical_reads": first,
                    "expected": args.expected_reads, "key_time_queries": time_queries,
                    "routing_correct": True}))
                assert first == args.expected_reads, (
                    "One drop must have one operation-scoped parse", first, args.expected_reads)
                accepted_drop(core, clip)
                assert load.call_count == first * 2, "Parsed document leaked across operations"
                if args.revision == "current":
                    assert rename.call_count == 0, "Safe import must route targets without renaming joints"
                    assert time_queries == 1, "Do not retrieve all key times twice to set the playback range"
            # The next operation must read a changed file rather than a stale
            # document retained by the earlier successful import.
            make_animation(core, clip, 8, [("j_slide", "tz", 1, 7, "absolute")])
            with patch.object(cmds, "rename", wraps=cmds.rename) as rename:
                accepted_drop(core, clip)
                if args.revision == "current":
                    assert rename.call_count == 0
            assert abs(cmds.getAttr("j_slide.tz", time=8) - 7) < 1e-6
            before_options = dict(backend.sceneSettings)
            before_runtime = dict(backend.runtimeSettings)
            before_joints = sorted(cmds.ls(type="joint", long=True))
            with patch.object(backend, "importCurveNode", side_effect=RuntimeError(
                    "injected animation importer failure")) as importer:
                try:
                    core.import_animation_file(str(clip))
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("Importer failure did not propagate")
                assert importer.called
            assert backend.sceneSettings == before_options
            assert backend.runtimeSettings == before_runtime
            assert backend._castReadCache is None
            assert getattr(backend, "_animationState", None) is None
            assert sorted(cmds.ls(type="joint", long=True)) == before_joints
            accepted_drop(core, clip)
            assert abs(cmds.getAttr("j_slide.tz", time=8) - 7) < 1e-6
    print("ANIMATION_READ_SESSION_OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
