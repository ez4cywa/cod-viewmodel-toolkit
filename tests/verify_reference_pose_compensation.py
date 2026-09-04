"""Maya regression test for optional dual-wield reference-pose compensation."""

import os
import pathlib
import sys
import importlib.util
import json
import tempfile

import maya.cmds as cmds

if not hasattr(cmds, "pluginInfo"):
    import maya.standalone
    maya.standalone.initialize(name="python")


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plug-ins" / "viewmodel_weapon_toolkit.py"


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == \
        os.path.normcase(os.path.abspath(str(right)))


def _module_from_path(path):
    for module in tuple(sys.modules.values()):
        module_path = getattr(module, "__file__", "")
        if module_path and _same_path(module_path, path):
            return module
    spec = importlib.util.spec_from_file_location(
        "viewmodel_weapon_toolkit_reference_pose_test", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _inventory(left_position, right_position):
    return {
        "bone_records": [
            {
                "name": "tag_origin",
                "parent_name": None,
                "ancestor_names": [],
                "local_position": [0.0, 0.0, 0.0],
            },
            {
                "name": "j_wrist_le",
                "parent_name": "tag_origin",
                "ancestor_names": ["tag_origin"],
                "local_position": [0.0, 0.0, 0.0],
            },
            {
                "name": "j_wrist_ri",
                "parent_name": "tag_origin",
                "ancestor_names": ["tag_origin"],
                "local_position": [0.0, 0.0, 0.0],
            },
            {
                "name": "tag_weapon_left",
                "parent_name": "j_wrist_le",
                "ancestor_names": ["tag_origin", "j_wrist_le"],
                "local_position": list(left_position),
            },
            {
                "name": "tag_weapon_right",
                "parent_name": "j_wrist_ri",
                "ancestor_names": ["tag_origin", "j_wrist_ri"],
                "local_position": list(right_position),
            },
        ]
    }


def _animation(target, modes, overrides=None):
    return {
        "curve_mode_overrides": list(overrides or []),
        "curve_records": [
            {
                "node": target,
                "property": prop,
                "mode": mode,
                "frames": (0, 10),
                "values": (0.0, 1.0),
            }
            for prop, mode in zip(("tx", "ty", "tz"), modes)
        ]
    }


def _assert_close(actual, expected):
    if abs(float(actual) - float(expected)) > 1e-6:
        raise RuntimeError("Expected %s, got %s" % (expected, actual))


def main():
    cmds.loadPlugin(str(PLUGIN), quiet=True)
    module = _module_from_path(PLUGIN)

    current = _inventory((0.0, 0.0, 0.0), (1.0, 2.0, 3.0))
    reference = _inventory((10.0, -20.0, 30.0), (1.0, 2.0, 3.0))
    compensation = module._build_reference_pose_compensation(
        current,
        reference,
        {
            "left": _animation(
                "tag_weapon_left", ("relative", "additive", "absolute")),
            "right": _animation(
                "tag_weapon_right", ("absolute", "absolute", "absolute")),
        },
        "tag_weapon_left",
        "tag_weapon_right",
        reference_path="reference.cast",
    )

    left = compensation["sides"]["left"]
    if left["translation_offset"] != [10.0, -20.0, 30.0]:
        raise RuntimeError("Reference-pose offset is incorrect: %r" % left)
    if left["attribute_offsets"] != {
            "translateX": 10.0, "translateY": -20.0}:
        raise RuntimeError("Relative/additive axis routing is incorrect: %r" % left)
    if compensation["sides"]["right"]["attribute_offsets"]:
        raise RuntimeError("Absolute animation axes must not be compensated")

    forced_relative = module._build_reference_pose_compensation(
        current,
        reference,
        {
            "left": _animation(
                "tag_weapon_left",
                ("absolute", "absolute", "absolute"),
                [{
                    "node": "j_wrist_le",
                    "mode": "relative",
                    "translation": True,
                }]),
            "right": _animation(
                "tag_weapon_right", ("absolute",) * 3),
        },
        "tag_weapon_left",
        "tag_weapon_right",
    )
    if set(forced_relative["sides"]["left"]["attribute_offsets"]) != {
            "translateX", "translateY", "translateZ"}:
        raise RuntimeError("Relative curve-mode override was not resolved")

    forced_absolute = module._build_reference_pose_compensation(
        current,
        reference,
        {
            "left": _animation(
                "tag_weapon_left",
                ("relative", "relative", "relative"),
                [{
                    "node": "tag_origin",
                    "mode": "absolute",
                    "translation": True,
                }]),
            "right": _animation(
                "tag_weapon_right", ("absolute",) * 3),
        },
        "tag_weapon_left",
        "tag_weapon_right",
    )
    if forced_absolute["sides"]["left"]["attribute_offsets"]:
        raise RuntimeError("Absolute curve-mode override was not resolved")

    cmds.file(new=True, force=True)
    target = cmds.joint(name="tag_weapon_left")
    for time, values in (
            (0.0, (1.0, 2.0, 3.0)),
            (10.0, (4.0, 5.0, 6.0)),
            (20.0, (7.0, 8.0, 9.0))):
        for attribute, value in zip(
                ("translateX", "translateY", "translateZ"), values):
            cmds.setKeyframe(target, attribute=attribute, time=time, value=value)

    report = module._apply_reference_pose_compensation(
        target, left, (0.0, 10.0))
    if report["applied_curve_count"] != 2:
        raise RuntimeError("Expected two compensated curves: %r" % report)
    for time, expected in (
            (0.0, (11.0, -18.0, 3.0)),
            (10.0, (14.0, -15.0, 6.0)),
            (20.0, (7.0, 8.0, 9.0))):
        for attribute, value in zip(
                ("translateX", "translateY", "translateZ"), expected):
            actual = cmds.getAttr(
                target + "." + attribute, time=time)
            _assert_close(actual, value)

    with tempfile.TemporaryDirectory() as directory:
        manifest_path = os.path.join(directory, "dual_manifest.json")
        stale = {
            "reference_pose_path": "stale.cast",
            "reference_pose_compensation": {"enabled": False},
        }
        with open(manifest_path, "w", encoding="utf-8") as stream:
            json.dump(stale, stream)
        state = {
            "output_manifest": manifest_path,
            "left_animation_path": "left.cast",
            "right_animation_path": "right.cast",
            "left_clip_range": [0, 10],
            "right_clip_range": [0, 10],
            "animation_mode": "simultaneous",
            "shared_hands_source": True,
            "reference_pose_path": "reference.cast",
            "reference_pose_compensation": forced_relative,
        }
        module._refresh_persisted_dual_manifest(state, {"valid": True})
        with open(manifest_path, "r", encoding="utf-8") as stream:
            refreshed = json.load(stream)
        if refreshed["reference_pose_path"] != "reference.cast":
            raise RuntimeError("Persisted reference path was not refreshed")
        if not refreshed["reference_pose_compensation"]["enabled"]:
            raise RuntimeError("Persisted compensation was not refreshed")

    cmds.file(new=True, force=True)
    cmds.unloadPlugin("viewmodel_weapon_toolkit", force=True)
    print("REFERENCE_POSE_COMPENSATION_VERIFICATION_OK")


if __name__ == "__main__":
    main()
