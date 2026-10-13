"""Mayapy: standalone exports preserve the live registered Maya implementation.

Optional --plugin PATH verifies a real English, Chinese or legacy installation.
Only synthetic fixtures are used; --keep PATH retains evidence on request.
"""

import argparse
from contextlib import nullcontext
from pathlib import Path
import shlex
import sys
import tempfile

import maya.cmds as cmds
import maya.standalone
import maya.api.OpenMaya as om

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_batch_animation_export import make_animation, make_model
from verify_maya_drop_module_path import loaded_plugin_globals


def world_poses():
    result = {}
    for frame in range(4):
        cmds.currentTime(frame, edit=True)
        result[frame] = {}
        for node in cmds.ls(type="joint", long=True) or []:
            selection = om.MSelectionList()
            selection.add(node)
            result[frame][node] = tuple(selection.getDagPath(0).inclusiveMatrix())
    return result


def snapshot():
    """Read scene invariants, restoring the evaluation time after pose sampling."""
    frame = cmds.currentTime(query=True)
    modified = cmds.file(query=True, modified=True)
    try:
        poses = world_poses()
    finally:
        cmds.currentTime(frame, edit=True)
        cmds.file(modified=modified)
    curves = {}
    for curve in cmds.ls(type="animCurve") or []:
        curves[curve] = {
            "times": cmds.keyframe(curve, query=True, timeChange=True) or [],
            "values": cmds.keyframe(curve, query=True, valueChange=True) or [],
            "breakdown": cmds.keyframe(curve, query=True, breakdown=True) or [],
            "tangents": {name: cmds.keyTangent(curve, query=True, **{name: True}) or []
                         for name in ("inTangentType", "outTangentType", "inAngle", "outAngle",
                                      "inWeight", "outWeight", "lock", "weightLock")},
        }
    return {
        "scene": cmds.file(query=True, sceneName=True),
        "modified": modified, "frame": frame,
        "selection": cmds.ls(selection=True, long=True) or [],
        "nodes": sorted(cmds.ls(long=True) or []),
        "units": {name: cmds.currentUnit(query=True, **{name: True})
                  for name in ("linear", "angle", "time")},
        "up_axis": cmds.upAxis(query=True, axis=True),
        "playback": {name: cmds.playbackOptions(query=True, **{name: True})
                     for name in ("animationStartTime", "animationEndTime", "minTime", "maxTime")},
        "skin_methods": {node: cmds.getAttr(node + ".skinningMethod")
                         for node in cmds.ls(type="skinCluster") or []},
        "keys": curves, "poses": poses,
    }


def assert_preserved(before, after):
    for name in before:
        if name == "poses":
            assert before[name].keys() == after[name].keys()
            for frame, nodes in before[name].items():
                assert nodes.keys() == after[name][frame].keys()
                for node, matrix in nodes.items():
                    assert max(abs(a - b) for a, b in zip(matrix, after[name][frame][node])) < 1e-8, (frame, node)
        else:
            assert before[name] == after[name], (name, before[name], after[name])


def smd_data(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    assert lines[:2] == ["version 1", "nodes"]
    names, frames = {}, {}
    cursor = 2
    while lines[cursor] != "end":
        index, name, _ = shlex.split(lines[cursor])
        names[int(index)] = name
        cursor += 1
    assert lines[cursor + 1] == "skeleton"
    for line in lines[cursor + 2:]:
        if line == "end":
            break
        if line.startswith("time "):
            frame = int(line.split()[1])
            frames[frame] = {}
        else:
            values = line.split()
            frames[frame][names[int(values[0])]] = tuple(float(value) for value in values[1:])
    return lines, frames


def export_case(runtime, exports, folder, name, file_format, animated=False,
                output_unit="original", collision=False):
    destination = folder / name
    destination.mkdir()
    target = destination / (name + "." + file_format)
    sentinel = b"pre-existing destination must remain unchanged"
    if collision:
        target.write_bytes(sentinel)
    before = snapshot()
    print("STANDALONE_EXPORT_START", name, flush=True)
    report = exports.export_file(runtime(), str(target), file_format,
                                 animated=animated, frame_range=(0, 3) if animated else None,
                                 output_unit=output_unit)
    assert_preserved(before, snapshot())
    actual = Path(report["path"])
    expected = {actual.name}
    if collision:
        assert target.read_bytes() == sentinel
        assert actual.name == target.stem + "_v001" + target.suffix
        expected.add(target.name)
    else:
        assert actual == target
    assert {item.name for item in destination.iterdir()} == expected, list(destination.iterdir())
    assert report["format"] == file_format and report["animation_included"] is animated
    assert report["source_scene_preserved"] is True
    assert actual.stat().st_size > 0
    if animated:
        assert report.get("frame_range", report.get("source_frame_range")) == [0, 3]
    if file_format == "fbx":
        runtime().verify_exported_fbx(str(actual))
    print("STANDALONE_EXPORT_OK", name, actual.name, flush=True)
    return report, before


def verify_fbx_roundtrip(runtime, report, expected, metric=False, static=False):
    cmds.file(new=True, force=True)
    cmds.currentUnit(linear="m" if metric else "cm", time="ntsc")
    cmds.upAxis(axis=expected["up_axis"], rotateView=False)
    runtime()._ensure_fbx_exporter()
    cmds.file(report["path"], i=True, type="FBX", ignoreVersion=True)
    actual = world_poses()
    by_name = {node.rsplit("|", 1)[-1]: node for node in actual[0]}
    factor = 30.48 if metric else 1.0
    for frame, nodes in expected["poses"].items():
        if static and frame != 0:
            continue
        for node, matrix in nodes.items():
            name = node.rsplit("|", 1)[-1]
            values = list(matrix)
            for index in (12, 13, 14):
                values[index] *= factor
            assert max(abs(a - b) for a, b in zip(values, actual[frame][by_name[name]])) < 0.002, (
                "FBX roundtrip", metric, frame, name, values, actual[frame][by_name[name]])
    if static:
        assert not (cmds.ls(type="animCurve") or [])
    else:
        times = cmds.keyframe("viewhands_j_gun", query=True, timeChange=True) or []
        assert min(times) <= 0 and max(times) >= 3
        assert all(cmds.getAttr(node + ".skinningMethod") == 1
                   for node in cmds.ls(type="skinCluster") or [])
        if metric:
            assert abs(cmds.getAttr("viewhands_j_gun.tx", time=3) - 3.048) < 1e-6


def run(plugin, folder):
    cmds.loadPlugin(str(plugin), quiet=True)
    namespace = loaded_plugin_globals(plugin)
    runtime = namespace["_core_runtime"]
    assert Path(runtime()._TOOLKIT_PLUGIN_PATH).resolve() == plugin.resolve()
    # Maya's nameless registered globals must locate adjacent helpers reliably.
    namespace.pop("__file__", None)
    exports = runtime()._exports_module()
    assert Path(exports.__file__).resolve() == plugin.parent / "cod_viewmodel_exports.py"
    assert exports.FORMATS == ("fbx", "smd")
    core = runtime()
    cmds.currentUnit(linear="cm")
    hands, weapon, clip = [folder / (name + ".cast") for name in ("hands", "weapon", "clip")]
    make_model(core, hands, True)
    make_model(core, weapon, False)
    make_animation(core, clip, 3, [
        ("j_gun", "tx", 0, 10, "absolute"),
        ("j_slide", "tz", 1, 4, "absolute"),
        ("j_slide", "rq", (0, 0, 0, 1), (0, 0, 0.3826834, 0.9238795), "absolute"),
    ])
    ignored = folder / "disabled-builder-output"
    result = core.attach_gun(str(hands), str(weapon), core.AttachOptions(
        output_dir=str(ignored), force_new_scene=True))
    assert not ignored.exists() and not result.output_manifest
    cmds.setAttr("j_wrist_ri.tx", 10)
    cmds.playbackOptions(animationStartTime=0, animationEndTime=3, minTime=0, maxTime=3)
    cmds.currentTime(2)
    cmds.currentUnit(linear="ft")
    cmds.select(result.source_node, replace=True)
    cmds.file(rename=str(folder / "live-source.ma"))
    cmds.file(modified=True)
    static_fbx, static_snapshot = export_case(runtime, exports, folder, "static_fbx", "fbx", collision=True)
    static_smd, _ = export_case(runtime, exports, folder, "static_smd", "smd")
    static_metric, _ = export_case(runtime, exports, folder, "static_smd_m", "smd", output_unit="m")
    for report in (static_smd, static_metric):
        lines, frames = smd_data(report["path"])
        assert "triangles" in lines and set(frames) == {0}
    _, metric_frames = smd_data(static_metric["path"])
    assert abs(metric_frames[0]["j_wrist_ri"][0] - 3.048) < 1e-6
    cmds.currentUnit(linear="cm")
    core.import_animation_file(str(clip))
    cmds.currentUnit(linear="ft")
    cmds.currentTime(2)
    cmds.select("j_slide", replace=True)
    cmds.file(modified=True)
    animated_fbx, animated_snapshot = export_case(runtime, exports, folder, "animated_fbx", "fbx", animated=True)
    animated_smd, _ = export_case(runtime, exports, folder, "animated_smd", "smd", animated=True)
    animated_metric, _ = export_case(runtime, exports, folder, "animated_fbx_m", "fbx", animated=True, output_unit="m")
    lines, frames = smd_data(animated_smd["path"])
    assert "triangles" not in lines and set(frames) == {0, 1, 2, 3}
    assert abs(frames[3]["viewhands_j_gun"][0] - 10) < 1e-6
    verify_fbx_roundtrip(runtime, static_fbx, static_snapshot, static=True)
    verify_fbx_roundtrip(runtime, animated_fbx, animated_snapshot)
    verify_fbx_roundtrip(runtime, animated_metric, animated_snapshot, metric=True)

    cmds.file(new=True, force=True)
    cmds.currentUnit(linear="cm")
    cube = cmds.polyCube(name="ordinary_scene_cube")[0]
    cmds.select(cube, replace=True)
    cmds.file(rename=str(folder / "ordinary-scene.ma"))
    exports_before = snapshot()
    rejected = folder / "invalid-static-smd" / "static.smd"
    try:
        exports.export_file(runtime(), str(rejected), "smd")
    except RuntimeError as error:
        assert "attachment" in str(error).lower(), str(error)
    else:
        raise AssertionError("Static SMD without a toolkit attachment was accepted")
    assert not rejected.parent.exists()
    assert_preserved(exports_before, snapshot())
    export_case(runtime, exports, folder, "ordinary_fbx", "fbx")
    cmds.file(new=True, force=True)
    bone = cmds.createNode("joint", name="ordinary_bone")
    cmds.setKeyframe(bone, attribute="translateX", time=0, value=0)
    cmds.setKeyframe(bone, attribute="translateX", time=3, value=10)
    cmds.select(bone, replace=True)
    plain_smd, _ = export_case(runtime, exports, folder, "ordinary_animation_smd", "smd", animated=True)
    lines, frames = smd_data(plain_smd["path"])
    assert "triangles" not in lines and set(frames) == {0, 1, 2, 3}
    assert abs(frames[3]["ordinary_bone"][0] - 10) < 1e-6
    print("STANDALONE_EXPORT_HOST_OK: 8 isolated exports; all live scene invariants preserved; 10ft=3.048m", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin", type=Path, default=ROOT / "plug-ins/viewmodel_weapon_toolkit.py")
    parser.add_argument("--keep", type=Path)
    arguments = parser.parse_args()
    context = nullcontext(str(arguments.keep)) if arguments.keep else tempfile.TemporaryDirectory(prefix="cod_standalone_host_")
    with context as directory:
        folder = Path(directory).resolve()
        folder.mkdir(parents=True, exist_ok=True)
        run(arguments.plugin.resolve(), folder)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
