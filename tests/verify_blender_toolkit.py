"""Run with Blender --background --factory-startup --python-exit-code 1."""

import json
from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import math
from unittest.mock import patch

import bpy
from mathutils import Euler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
sys.path.insert(0, str(ROOT / "tests"))
from cod_viewmodel_toolkit import core
from cod_viewmodel_toolkit.backend import backend
from cod_viewmodel_toolkit import exporting
from blender_fixtures import model, animation


def samples(rig, end=3):
    result = []
    for frame in range(end + 1):
        bpy.context.scene.frame_set(frame)
        row = {bone.name: list(sum((list(axis) for axis in rig.matrix_world @ bone.matrix), []))
               for bone in rig.pose.bones}
        graph = bpy.context.evaluated_depsgraph_get()
        row["meshes"] = []
        for obj in exporting.assembly_objects(rig)[1:]:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            try:
                row["meshes"].append(sorted(tuple(round(x, 5) for x in obj.matrix_world @ vertex.co)
                                            for vertex in mesh.vertices))
            finally:
                evaluated.to_mesh_clear()
        row["meshes"].sort()
        result.append(row)
    return result


def compare(expected, actual, tolerance=0.001):
    assert len(expected) == len(actual)
    for frame, (first, second) in enumerate(zip(expected, actual)):
        for name in first:
            if name == "meshes":
                assert len(first[name]) == len(second[name])
                for left, right in zip(first[name], second[name]):
                    assert len(left) == len(right)
                    assert max(abs(a - b) for v, w in zip(left, right) for a, b in zip(v, w)) < tolerance, (frame, name, left, right)
            else:
                assert max(abs(a - b) for a, b in zip(first[name], second[name])) < tolerance, (frame, name, first[name], second[name])


def main():
    from cod_viewmodel_toolkit.fbx import stable_xyz, stable_fbx_rotation
    from io_scene_fbx.fbx_utils import ObjectWrapper
    for pitch in (-90, -89.99999, -89.99, 0, 89.99, 89.99999, 90):
        for roll, yaw in ((0, 0), (34, 78), (-120, 160)):
            source = Euler(tuple(math.radians(v) for v in (roll, pitch, yaw)), "XYZ").to_quaternion()
            result = stable_xyz(source).to_matrix()
            assert max(abs(a-b) for v,w in zip(source.to_matrix(), result) for a,b in zip(v,w)) < 2e-6
    original = ObjectWrapper.fbx_object_tx
    try:
        with stable_fbx_rotation():
            assert ObjectWrapper.fbx_object_tx is not original
            raise RuntimeError("intentional export failure")
    except RuntimeError:
        pass
    assert ObjectWrapper.fbx_object_tx is original
    print("BLENDER_FBX_NUMERICS_OK")
    cast = backend().cast
    with tempfile.TemporaryDirectory(prefix="cod_blender_test_") as temporary:
        folder = Path(temporary)
        hands, weapon = folder / "hands.cast", folder / "weapon.cast"
        left, right = folder / "left.cast", folder / "right.cast"
        model(cast, hands)
        model(cast, weapon, hands=False)
        animation(cast, left)
        animation(cast, right, side="right", amount=6)
        sentinel = bpy.data.objects.get("Cube")
        single = core.build(hands, weapon, left=str(left))
        assert core.verify(single)["valid"]
        assert bpy.data.objects.get("Cube") == sentinel
        bpy.context.scene.frame_set(3)
        assert abs(single.pose.bones["weapon__j_slide"].matrix.translation.z - 6) < 1e-4, tuple(single.pose.bones["weapon__j_slide"].matrix.translation)
        print("BLENDER_SINGLE_OK")
        dual = core.build(hands, weapon, core.BuildOptions(dual=True), str(left), str(right))
        assert core.verify(dual)["valid"]
        bpy.context.scene.frame_set(3)
        assert abs(dual.pose.bones["j_wrist_le"].matrix.translation.x + 7) < 1e-4
        assert abs(dual.pose.bones["j_wrist_ri"].matrix.translation.x - 10) < 1e-4
        assert abs(dual.pose.bones["akimbo_l__j_slide"].matrix.translation.z - 6) < 1e-4
        assert abs(dual.pose.bones["akimbo_r__j_slide"].matrix.translation.z - 9) < 1e-4
        print("BLENDER_DUAL_OK")
        settings = exporting.ExportOptions(directory=str(folder / "exports"), fbx=True, smd=True)
        expected = samples(dual)
        with redirect_stdout(io.StringIO()):
            exported = exporting.export(dual, settings, "dual")
        assert all(Path(path).stat().st_size for path in exported["outputs"].values())
        assert "triangles" not in Path(exported["outputs"]["smd"]).read_text()
        print("BLENDER_FOUR_EXPORTS_OK")
        batch = exporting.Batch(str(hands), str(weapon), [(str(left), ""), ("missing.cast", ""), (str(right), "")],
                                core.BuildOptions(), settings)
        objects_before = set(bpy.data.objects)
        with redirect_stdout(io.StringIO()):
            while not batch.done:
                batch.step()
        assert [item["status"] for item in batch.items] == ["ok", "failed", "ok"], batch.items
        assert set(bpy.data.objects) == objects_before
        assert Path(batch.finish()).is_file()
        print("BLENDER_BATCH_OK")
        sequential = core.build(hands, weapon, core.BuildOptions(dual=True, animation_mode="sequential"), str(left), str(right))
        assert bpy.context.scene.frame_end == 7
        bpy.context.scene.frame_set(7)
        assert abs(sequential.pose.bones["j_wrist_ri"].matrix.translation.x - 10) < 1e-4
        replacement = folder / "replacement.cast"
        animation(cast, replacement, amount=9)
        core.apply_animations(dual, str(replacement), str(right))
        replaced = samples(dual)
        for old, new in zip(expected, replaced):
            for name in ("j_wrist_ri", "tag_weapon_right", "akimbo_r__j_slide"):
                assert old[name] == new[name], name
        print("BLENDER_REPLACEMENT_SEQUENTIAL_OK")
        pools = (bpy.data.objects, bpy.data.collections, bpy.data.actions,
                 bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images)
        snapshots = [set(pool) for pool in pools]
        with patch.object(core, "_attach", side_effect=RuntimeError("injected attachment failure")):
            try:
                core.build(hands, weapon)
                raise AssertionError("Expected rollback")
            except RuntimeError as error:
                assert "injected" in str(error)
        assert [set(pool) for pool in pools] == snapshots
        old_action = dual.animation_data.action
        from cod_viewmodel_toolkit import animation as composition
        with patch.object(composition, "_write_action", side_effect=RuntimeError("injected action failure")):
            try:
                core.apply_animations(dual, str(left), str(right))
                raise AssertionError("Expected animation rollback")
            except RuntimeError:
                pass
        assert dual.animation_data.action == old_action
        compare(replaced, samples(dual))
        stopped = exporting.Batch(str(hands), str(weapon), [(str(left), "")], core.BuildOptions(), settings)
        stopped.cancelled = True
        assert stopped.done and stopped.step() is None
        assert json.loads(Path(stopped.finish()).read_text())["completed"] == 0
        static = core.build(hands, weapon)
        static_settings = exporting.ExportOptions(directory=str(folder / "static"),
            blend=False, cast=False, smd=True, folders={"smd": str(folder / "smd")})
        static_export = exporting.export(static, static_settings, "static")
        assert "triangles" in Path(static_export["outputs"]["smd"]).read_text()
        assert Path(static_export["outputs"]["smd"]).parent == folder / "smd"
        zero = folder / "zero.cast"
        animation(cast, zero, end=0)
        core.apply_animations(static, str(zero))
        assert bpy.context.scene.frame_start == bpy.context.scene.frame_end == 0
        reference = folder / "reference.cast"
        model(cast, reference, reference_offset=5)
        document = cast.Cast.load(str(left))
        clip = next(node for node in document.Roots()[0].childNodes if isinstance(node, cast.Animation))
        curve = clip.CreateCurve()
        curve.SetNodeName("tag_weapon_left")
        curve.SetKeyPropertyName("tz")
        curve.SetKeyFrameBuffer([0, 3])
        curve.SetFloatKeyValueBuffer([0, 2])
        curve.SetMode("relative")
        relative = folder / "relative.cast"
        document.save(str(relative))
        plain = core.build(hands, weapon, core.BuildOptions(dual=True), str(relative), str(right))
        compensated = core.build(hands, weapon, core.BuildOptions(dual=True, reference_pose=str(reference)), str(relative), str(right))
        bpy.context.scene.frame_set(3)
        assert abs(compensated.pose.bones["tag_weapon_left"].matrix.translation.z -
                   plain.pose.bones["tag_weapon_left"].matrix.translation.z - 5) < 1e-4
        print("BLENDER_ROLLBACK_CANCEL_STATIC_REFERENCE_ZERO_OK")
        import cod_viewmodel_toolkit
        cod_viewmodel_toolkit.register()
        props = bpy.context.scene.cod_vwt
        props.hands, props.weapon, props.left = str(hands), str(weapon), str(left)
        assert bpy.ops.cod_vwt.preflight() == {"FINISHED"}
        assert bpy.ops.cod_vwt.queue(action="ADD") == {"FINISHED"}
        assert len(props.jobs) == 1
        assert bpy.ops.cod_vwt.queue(action="REMOVE") == {"FINISHED"}
        assert not props.jobs
        cod_viewmodel_toolkit.unregister()
        print("BLENDER_UI_OPERATORS_OK")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        with redirect_stdout(io.StringIO()):
            bpy.ops.import_scene.fbx(filepath=exported["outputs"]["fbx"], use_anim=True,
                                     automatic_bone_orientation=False, anim_offset=0.0)
        imported = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
        compare(expected, samples(imported))
        print("BLENDER_FBX_ROUNDTRIP_OK")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        from cod_viewmodel_toolkit.backend import options, select
        backend().importer.load(options(), bpy.context, exported["outputs"]["cast"])
        imported = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
        compare(expected, samples(imported))
        print("BLENDER_CAST_ROUNDTRIP_OK")
        bpy.ops.wm.open_mainfile(filepath=exported["outputs"]["blend"])
        assert len(bpy.context.scene.objects) == 4, list(bpy.context.scene.objects)
        imported = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
        compare(expected, samples(imported))
        print("BLENDER_BLEND_ROUNDTRIP_OK")
    print("BLENDER_TOOLKIT_OK", bpy.app.version_string)


if __name__ == "__main__":
    main()
