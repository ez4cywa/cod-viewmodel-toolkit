"""Maya 2025 regression: synthetic single/dual queues and real animated exports.

Run with mayapy. Fixtures and outputs are generated in a temporary directory;
no game assets are needed. --keep PATH retains generated evidence when requested.
"""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import maya.standalone
import maya.cmds as cmds
if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_reference_pose_compensation import _module_from_path


def make_model(module, path, hands):
    cmds.file(new=True, force=True)
    if hands:
        root = cmds.createNode("joint", name="tag_origin")
        gun = cmds.createNode("joint", name="j_gun", parent=root)
        cmds.createNode("joint", name="tag_weapon", parent=gun)
        for side, x in (("le", -4), ("ri", 4)):
            wrist = cmds.createNode("joint", name="j_wrist_" + side, parent=root)
            cmds.setAttr(wrist + ".tx", x)
            tag = cmds.createNode("joint", name="tag_weapon_" + (
                "left" if side == "le" else "right"), parent=wrist)
            cmds.setAttr(tag + ".tz", 2)
    else:
        root = cmds.createNode("joint", name="j_gun")
        slide = cmds.createNode("joint", name="j_slide", parent=root)
        cmds.setAttr(slide + ".tz", 1)
        cmds.setAttr(slide + ".jointOrientZ", 30)
    mesh = cmds.polyCube(name="hands_mesh" if hands else "gun_mesh")[0]
    cmds.skinCluster(cmds.ls(type="joint"), mesh, toSelectedBones=True)
    with module._temporary_cast_export_settings():
        cmds.file(str(path), force=True, type=module.cast_translator_name(),
                  exportAll=True, options="exportModel=1;exportAnim=0;bakeKeyframes=0")


def make_animation(module, path, end, tracks, fps=30):
    path.parent.mkdir(parents=True, exist_ok=True)
    cast = module._castplugin_module().Cast()
    animation = cast.CreateRoot().CreateAnimation()
    animation.SetFramerate(fps)
    for name, prop, first, last, mode in tracks:
        curve = animation.CreateCurve()
        curve.SetNodeName(name)
        curve.SetKeyPropertyName(prop)
        curve.SetMode(mode)
        frames = [0] if end == 0 else [0, end]
        curve.SetKeyFrameBuffer(frames)
        if prop == "rq":
            curve.SetVec4KeyValueBuffer(
                [first] if end == 0 else [first, last])
        else:
            curve.SetFloatKeyValueBuffer(
                [first] if end == 0 else [first, last])
    cast.save(str(path))


def assert_ok(summary):
    assert not summary["cancelled"], summary
    assert all(item["status"] == "ok" for item in summary["items"]), summary
    for item in summary["items"]:
        assert Path(item["manifest"]).is_file(), item
        assert all(Path(p).stat().st_size > 0 for p in item["outputs"].values()), item


def samples(nodes, end):
    result = {}
    for frame in range(end + 1):
        cmds.currentTime(frame)
        result[frame] = {name: cmds.xform(name, query=True, matrix=True, worldSpace=True)
                         for name in nodes}
        meshes = cmds.ls(type="mesh", long=True, noIntermediate=True)
        result[frame]["mesh_bounds"] = sorted(cmds.exactWorldBoundingBox(mesh) for mesh in meshes)
    return result


def verify_roundtrip(item, nodes, module=None):
    cmds.file(item["outputs"]["scene"], open=True, force=True,
              prompt=False, executeScriptNodes=False)
    assert all(cmds.getAttr(c + ".skinningMethod") == 1 for c in cmds.ls(type="skinCluster"))
    end = item["frame_range"][1]
    expected = samples(nodes, end)
    unit = cmds.currentUnit(query=True, time=True)
    assert cmds.keyframe(nodes, query=True, keyframeCount=True) > 0
    cmds.file(new=True, force=True)
    cmds.currentUnit(time=unit)
    cmds.file(item["outputs"]["fbx"], i=True, type="FBX", ignoreVersion=True)
    assert all(cmds.getAttr(c + ".skinningMethod") == 1 for c in cmds.ls(type="skinCluster"))
    actual = samples(nodes, end)
    for frame in expected:
        for node in nodes:
            assert max(abs(a - b) for a, b in zip(expected[frame][node], actual[frame][node])) < 0.002, (
                "FBX sample mismatch", frame, node, expected[frame][node], actual[frame][node])
        assert len(expected[frame]["mesh_bounds"]) == len(actual[frame]["mesh_bounds"])
        for a, b in zip(expected[frame]["mesh_bounds"], actual[frame]["mesh_bounds"]):
            assert max(abs(x - y) for x, y in zip(a, b)) < 0.002, ("FBX mesh", frame, a, b)
    assert cmds.keyframe(nodes, query=True, keyframeCount=True) > 0
    lines = Path(item["outputs"]["smd"]).read_text(encoding="utf-8").splitlines()
    assert "triangles" not in lines
    assert sum(line.startswith("time ") for line in lines) == end + 1
    import shlex
    import maya.api.OpenMaya as om
    names, parents = {}, {}
    cursor = 2
    while lines[cursor] != "end":
        index, name, parent = shlex.split(lines[cursor])
        names[int(index)], parents[int(index)] = name, int(parent)
        cursor += 1
    matrices = {}
    for line in lines[cursor + 2:-1]:
        if line.startswith("time "):
            frame = int(line.split()[1])
            matrices = {}
            continue
        values = line.split()
        index = int(values[0])
        transform = om.MTransformationMatrix()
        transform.setTranslation(om.MVector(*map(float, values[1:4])), om.MSpace.kTransform)
        transform.setRotation(om.MEulerRotation(*map(float, values[4:7])))
        matrix = transform.asMatrix()
        if parents[index] >= 0:
            matrix *= matrices[parents[index]]
        matrices[index] = matrix
        if names[index] in nodes:
            assert max(abs(a - b) for a, b in zip(
                list(matrix), expected[frame][names[index]])) < 0.002, ("SMD", frame, names[index])
    if module is not None:
        cmds.file(new=True, force=True)
        cmds.currentUnit(time=unit)
        with module._temporary_cast_animation_settings(import_at_time=False):
            cmds.file(item["outputs"]["cast"], i=True, type=module.cast_translator_name(),
                      options=module._cast_animation_import_options(False))
        assert all(cmds.getAttr(c + ".skinningMethod") == 1 for c in cmds.ls(type="skinCluster"))
        actual = samples(nodes, end)
        for frame in expected:
            for node in nodes:
                assert max(abs(a - b) for a, b in zip(
                    expected[frame][node], actual[frame][node])) < 0.002, ("CAST", frame, node)
            assert len(expected[frame]["mesh_bounds"]) == len(actual[frame]["mesh_bounds"])
            for a, b in zip(expected[frame]["mesh_bounds"], actual[frame]["mesh_bounds"]):
                assert max(abs(x - y) for x, y in zip(a, b)) < 0.002, ("CAST mesh", frame, a, b)
    return len(expected)


def run(directory):
    plugin = ROOT / "plug-ins" / "viewmodel_weapon_toolkit.py"
    cmds.loadPlugin(str(plugin), quiet=True)
    module = _module_from_path(plugin)
    assert module._castplugin_module().version == "2.00"
    cast_settings = dict(module._castplugin_module().sceneSettings)
    hands, weapon = directory / "hands.cast", directory / "weapon.cast"
    make_model(module, hands, True)
    make_model(module, weapon, False)
    clip_a, clip_b = directory / "a" / "clip.cast", directory / "b" / "clip.cast"
    make_animation(module, clip_a, 8, [
        ("j_gun", "tx", 0, 8, "absolute"), ("j_slide", "tz", 1, 4, "absolute"),
        ("j_slide", "rq", (0, 0.173648178, 0, 0.984807753),
         (0.5, 0, 0, 0.8660254), "absolute")])
    make_animation(module, clip_b, 3, [("j_gun", "tx", 2, 5, "absolute")], fps=60)
    left, right = directory / "left.cast", directory / "right.cast"
    make_animation(module, left, 3, [
        ("j_gun", "tx", 0, 1, "absolute"),
        ("j_wrist_le", "tx", -4, -8, "absolute"),
        ("tag_weapon_left", "tz", 0, 2, "relative"),
        ("j_slide", "tz", 1, 5, "absolute")])
    make_animation(module, right, 5, [
        ("j_gun", "tx", 0, 2, "absolute"),
        ("j_wrist_ri", "tx", 4, 10, "absolute"),
        ("tag_weapon_right", "tz", 0, 4, "relative"),
        ("j_slide", "tz", 1, 7, "absolute")])
    left2 = directory / "left2.cast"
    make_animation(module, left2, 2, [
        ("j_gun", "tx", 0, 1, "absolute"),
        ("j_wrist_le", "tx", -4, -6, "absolute"),
        ("tag_weapon_left", "tz", 0, 1, "relative"),
        ("j_slide", "tz", 1, 3, "absolute")])

    # Maya expands a zero-duration time slider range. The dual workflow must
    # keep the one-frame animation content at frame 0 while using a legal
    # display range and exporting exactly one sampled frame.
    one_left = directory / "one_left.cast"
    one_right = directory / "one_right.cast"
    make_animation(module, one_left, 0, [
        ("j_wrist_le", "tx", -4, -4, "absolute"),
        ("tag_weapon_left", "tz", 0, 0, "relative"),
        ("j_slide", "tz", 2, 2, "absolute")])
    make_animation(module, one_right, 0, [
        ("tag_origin", "tx", 0, 0, "absolute"),
        ("j_wrist_ri", "tx", 4, 4, "absolute"),
        ("tag_weapon_right", "tz", 0, 0, "relative"),
        ("j_slide", "tz", 3, 3, "absolute")])
    one_frame_options = module.DualWieldOptions(
        output_dir=str(directory / "one_frame"),
        force_new_scene=True,
        export_smd=True,
        export_fbx=True,
        export_animation=True,
        animation_mode="simultaneous",
    )
    one_frame = module.attach_dual_wield(
        str(hands), str(weapon), str(one_left), str(one_right),
        one_frame_options)
    assert one_frame.left_clip_range == (0.0, 0.0)
    assert one_frame.right_clip_range == (0.0, 0.0)
    assert one_frame.frame_range == (0, 0)
    assert tuple(one_frame.dual_verification["content_range"]) == (0.0, 0.0)
    assert tuple(one_frame.dual_verification[
        "scene_animation_range"]) == (0.0, 1.0)
    assert tuple(one_frame.dual_verification["playback_range"]) == (0.0, 1.0)
    assert not one_frame.output_errors, one_frame.output_errors
    assert one_frame.cast_verification["animation"]["frame_range"] == [0, 0]
    assert one_frame.smd_verification["frame_count"] == 1
    assert one_frame.fbx_verification["frame_range"] == [0, 0]

    # Scenes saved before this fix contain the degenerate metadata plus the
    # Maya-coerced range. They must remain openable and replaceable.
    state_node, legacy_state = module._read_dual_state()
    legacy_state["playback_range"] = (0.0, 0.0)
    module._write_dual_state(state_node, legacy_state)
    cmds.playbackOptions(
        animationStartTime=0, animationEndTime=0,
        minTime=0, maxTime=0)
    legacy_validation = module.validate_dual_wield()
    assert tuple(legacy_validation["content_range"]) == (0.0, 0.0)
    assert tuple(legacy_validation["playback_range"]) == (-1.0, 0.0)
    options = module.AttachOptions(
        output_dir=str(directory / "single"), force_new_scene=True,
        export_smd=True, export_fbx=True,
        ma_output_dir=str(directory / "ma"), cast_output_dir=str(directory / "cast"),
        smd_output_dir=str(directory / "smd"), fbx_output_dir=str(directory / "fbx"))
    summary = module.batch_export_animations(str(hands), str(weapon),
                                             [str(clip_a), str(clip_b), str(clip_a)], options)
    assert_ok(summary)
    assert summary["total"] == 2
    assert summary["items"][0]["outputs"]["scene"] != summary["items"][1]["outputs"]["scene"]
    for item, fps, end in zip(summary["items"], (30, 60), (8, 3)):
        assert item["framerate"] == fps and item["frame_range"] == [0, end], item
        verify_roundtrip(item, ["viewhands_j_gun", "j_gun", "j_slide"], module)
    cmds.file(summary["items"][1]["outputs"]["scene"], open=True, force=True)
    assert not cmds.keyframe("j_slide", query=True, keyframeCount=True), "Previous clip leaked"
    assert abs(cmds.getAttr("j_slide.tz") - 1) < 1e-6

    dual_results = []
    for mode in ("simultaneous", "sequential"):
        dual_options = module.DualWieldOptions(
            output_dir=str(directory / mode), force_new_scene=True,
            export_smd=True, export_fbx=True, animation_mode=mode)
        result = module.batch_export_dual_animations(
            str(hands), str(weapon), [(str(left), str(right)), (str(left2), str(right))], dual_options)
        assert_ok(result)
        for item in result["items"]:
            verify_roundtrip(item, ["j_wrist_le", "j_wrist_ri", "akimbo_l_j_slide", "akimbo_r_j_slide"], module)
        dual_results.append(result)

    smd_only = module.AttachOptions(output_dir=str(directory / "only_smd"),
                                   save_scene=False, export_cast=False,
                                   export_smd=True, force_new_scene=True)
    failure_summary = module.batch_export_animations(
        str(hands), str(weapon), [str(directory / "missing.cast"), str(clip_b)], smd_only)
    assert [x["status"] for x in failure_summary["items"]] == ["failed", "ok"]
    assert set(failure_summary["items"][1]["outputs"]) == {"smd"}
    assert not list((directory / "only_smd").glob("*.cast"))
    no_match = directory / "no_match.cast"
    make_animation(module, no_match, 3, [("absent_joint", "tx", 0, 1, "absolute")])
    invalid_summary = module.batch_export_animations(str(hands), str(weapon), [str(no_match)], smd_only)
    assert invalid_summary["items"][0]["status"] == "failed"
    original_smd = module.export_smd_animation
    def fail_smd(path, frame_range):
        Path(path).write_text("partial file", encoding="utf-8")
        raise RuntimeError("Injected SMD write failure")
    module.export_smd_animation = fail_smd
    try:
        partial_options = module.AttachOptions(output_dir=str(directory / "partial"),
                                               export_cast=False, export_smd=True, force_new_scene=True)
        partial = module.batch_export_animations(str(hands), str(weapon), [str(clip_b)], partial_options)
        item = partial["items"][0]
        assert item["status"] == "partial" and set(item["outputs"]) == {"scene"}
        assert "smd" in item["output_errors"]
        assert not list((directory / "partial").glob("*.smd")), "Partial output was published"
        all_failed = module.batch_export_animations(str(hands), str(weapon), [str(clip_b)], smd_only)
        assert all_failed["items"][0]["status"] == "failed"
        assert not all_failed["items"][0]["outputs"]
    finally:
        module.export_smd_animation = original_smd
    cancelled = module.batch_export_animations(
        str(hands), str(weapon), [str(clip_a), str(clip_b)], smd_only,
        progress=lambda index, total, job: index == 0)
    assert cancelled["cancelled"] and cancelled["completed"] == 1
    before = cmds.file(query=True, sceneName=True)
    try:
        module.batch_export_animations(str(hands), str(weapon), [str(clip_a)],
                                       module.AttachOptions(save_scene=False, export_cast=False))
    except RuntimeError:
        pass
    else:
        raise AssertionError("Zero selected formats should fail")
    assert cmds.file(query=True, sceneName=True) == before
    assert module._castplugin_module().sceneSettings == cast_settings
    print("BATCH_ANIMATION_TEST_PASSED " + json.dumps({
        "single_items": summary["total"], "dual_items": sum(x["total"] for x in dual_results),
        "formats": ["ma", "cast", "smd", "fbx"], "failure_continuation": True,
        "cancellation": True, "isolated_clips": True, "roundtrip_fbx_cast_smd": True}))
    cmds.file(new=True, force=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep")
    args = parser.parse_args()
    if args.keep:
        directory = Path(args.keep).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        run(directory)
    else:
        with tempfile.TemporaryDirectory(prefix="vwt_batch_test_") as temporary:
            run(Path(temporary))
    maya.standalone.uninitialize()
