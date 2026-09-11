"""Verify user-supplied CoD CAST assets without modifying the inputs.

blender -b --factory-startup --python-exit-code 1 --python this.py --
    HANDS.cast WEAPON.cast ANIMATION.cast OUTPUT_DIRECTORY
"""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
from cod_viewmodel_toolkit import core, exporting
from cod_viewmodel_toolkit.backend import backend, options


def snapshot(rig, frames):
    result = {}
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        result[frame] = {
            bone.name: [value for row in rig.matrix_world @ bone.matrix for value in row]
            for bone in rig.pose.bones}
        graph = bpy.context.evaluated_depsgraph_get()
        bounds = []
        for mesh in exporting.assembly_objects(rig)[1:]:
            evaluated = mesh.evaluated_get(graph)
            points = [mesh.matrix_world @ vertex.co for vertex in evaluated.data.vertices]
            bounds.append([min(point[axis] for point in points) for axis in range(3)] +
                          [max(point[axis] for point in points) for axis in range(3)])
        result[frame]["mesh_bounds"] = sorted(bounds)
    return result


def differences(expected, actual):
    bone_error, mesh_error = 0.0, 0.0
    translation_error, worst = 0.0, None
    for frame in expected:
        for name, original in expected[frame].items():
            if name == "mesh_bounds":
                assert len(original) == len(actual[frame][name])
                mesh_error = max(mesh_error, max(abs(a - b)
                                 for left, right in zip(original, actual[frame][name])
                                 for a, b in zip(left, right)))
            else:
                error = max(abs(a - b) for a, b in zip(original, actual[frame][name]))
                if error > bone_error:
                    bone_error = error
                    worst = {"bone": name, "frame": frame, "expected": original, "actual": actual[frame][name]}
                translation_error = max(translation_error, max(abs(original[i] - actual[frame][name][i]) for i in (3, 7, 11)))
    return {"bone_max_error": bone_error, "bone_translation_error": translation_error,
            "mesh_bounds_max_error": mesh_error, "worst": worst}


def main():
    hands, weapon, animation, output = sys.argv[sys.argv.index("--") + 1:]
    input_hashes = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                    for path in (hands, weapon, animation)}
    preflight = core.preflight(hands, weapon, left=animation)
    rig = core.build(hands, weapon, left=animation)
    end = bpy.context.scene.frame_end
    frames = sorted(set((0, end // 2, end)))
    expected = snapshot(rig, frames)
    verification = core.verify(rig)
    with redirect_stdout(io.StringIO()):
        result = exporting.export(rig, exporting.ExportOptions(directory=output, fbx=True, smd=True),
                                  "cod_real_asset")
    reports = {}
    for extension in ("fbx", "cast", "blend"):
        path = result["outputs"][extension]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        with redirect_stdout(io.StringIO()):
            if extension == "fbx":
                bpy.ops.import_scene.fbx(filepath=path, use_anim=True, anim_offset=0.0,
                                         automatic_bone_orientation=False)
            elif extension == "cast":
                backend().importer.load(options(), bpy.context, path)
            else:
                bpy.ops.wm.open_mainfile(filepath=path)
        imported = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
        reports[extension] = differences(expected, snapshot(imported, frames))
        if extension == "fbx":
            for obj in exporting.assembly_objects(imported):
                for modifier in obj.modifiers:
                    if modifier.type == "ARMATURE":
                        modifier.use_deform_preserve_volume = True
            reports["fbx_dqs"] = differences(expected, snapshot(imported, frames))
    assert input_hashes == {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                            for path in input_hashes}
    summary = {"blender": bpy.app.version_string, "hands_bones": len(preflight["hands"]["bones"]),
               "weapon_bones": len(preflight["weapon"]["bones"]),
               "frames": end + 1, "sampled_frames": frames,
               "verification": verification, "roundtrip": reports,
               "manifest": result["manifest"], "inputs_unchanged": True}
    Path(output, "real_asset_verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("BLENDER_REAL_ASSET_RESULT", json.dumps(summary))
    for extension, values in reports.items():
        assert values["bone_max_error"] < 0.005, (extension, values)
        if extension != "fbx":
            assert values["mesh_bounds_max_error"] < 0.01, (extension, values)


if __name__ == "__main__":
    main()
