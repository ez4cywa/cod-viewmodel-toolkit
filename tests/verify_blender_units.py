"""Metric scene copies, all format units, preservation and idempotence."""

from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "blender"))
sys.path.insert(0, str(ROOT / "tests"))
from cod_viewmodel_toolkit import core, exporting
from cod_viewmodel_toolkit.backend import backend, options
from blender_fixtures import model, animation
from verify_blender_toolkit import samples, compare


def scaled_samples(rows, factor, basis_factor=1.0):
    result = copy.deepcopy(rows)
    for row in result:
        for name, values in row.items():
            if name == "meshes":
                row[name] = [[tuple(v * factor for v in point) for point in mesh] for mesh in values]
            else:
                for index in (3, 7, 11):
                    values[index] *= factor
                for index in (0, 1, 2, 4, 5, 6, 8, 9, 10):
                    values[index] *= basis_factor
    return result


def fbx_unit(path):
    from io_scene_fbx import parse_fbx
    root, _ = parse_fbx.parse(path)
    settings = next(node for node in root.elems if node.id == b"GlobalSettings")
    properties = next(node for node in settings.elems if node.id == b"Properties70")
    return next(node.props[-1] for node in properties.elems if node.props[0] == b"UnitScaleFactor")


def main():
    with tempfile.TemporaryDirectory(prefix="cod_metric_blender_") as temporary:
        folder = Path(temporary)
        hands, weapon, clip = [folder / (name + ".cast") for name in ("hands", "weapon", "clip")]
        model(backend().cast, hands)
        model(backend().cast, weapon, hands=False)
        animation(backend().cast, clip, amount=10)
        rig = core.build(hands, weapon, left=str(clip))
        bpy.context.scene.unit_settings.system = "IMPERIAL"
        bpy.context.scene.unit_settings.scale_length = 0.3048
        before = samples(rig)
        objects, actions = set(bpy.data.objects), set(bpy.data.actions)
        action, state = rig.animation_data.action, rig[core.STATE_KEY]
        settings = exporting.ExportOptions(directory=str(folder / "out"), fbx=True, smd=True, output_unit="m")
        with redirect_stdout(io.StringIO()):
            first = exporting.export(rig, settings, "metric")
            second = exporting.export(rig, settings, "metric")
        compare(before, samples(rig))
        assert set(bpy.data.objects) == objects and set(bpy.data.actions) == actions
        assert rig.animation_data.action == action and rig[core.STATE_KEY] == state
        assert bpy.context.scene.unit_settings.system == "IMPERIAL"
        assert abs(bpy.context.scene.unit_settings.scale_length - 0.3048) < 1e-7
        assert first["unit_conversion"]["factor"] == 0.3048
        assert first["outputs"]["blend"] != second["outputs"]["blend"]
        assert fbx_unit(first["outputs"]["fbx"]) == 100.0
        expected = scaled_samples(before, 0.3048)
        world_expected = scaled_samples(before, 0.3048, basis_factor=0.3048)
        for kind in ("fbx", "cast", "blend"):
            bpy.ops.wm.read_factory_settings(use_empty=True)
            with redirect_stdout(io.StringIO()):
                if kind == "fbx":
                    bpy.ops.import_scene.fbx(filepath=first["outputs"][kind], anim_offset=0.0)
                elif kind == "cast":
                    backend().importer.load(options(), bpy.context, first["outputs"][kind])
                else:
                    bpy.ops.wm.open_mainfile(filepath=first["outputs"][kind])
            imported = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
            for obj in bpy.context.scene.objects:
                for modifier in obj.modifiers:
                    if modifier.type == "ARMATURE":
                        modifier.use_deform_preserve_volume = True
            compare(expected if kind == "cast" else world_expected, samples(imported), tolerance=0.0002)
        assert bpy.context.scene.unit_settings.system == "METRIC"
        assert bpy.context.scene.unit_settings.length_unit == "METERS"
        assert bpy.context.scene.unit_settings.scale_length == 1.0
        # Reapplying a source clip and exporting a reopened metric scene are safe.
        core.apply_animations(imported, str(clip))
        compare(world_expected, samples(imported), tolerance=0.0002)
        with redirect_stdout(io.StringIO()):
            third = exporting.export(imported, settings, "already_metric")
        assert third["unit_conversion"]["already_metric"] and third["unit_conversion"]["factor"] == 1.0
        bpy.ops.wm.open_mainfile(filepath=third["outputs"]["blend"])
        imported = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
        compare(world_expected, samples(imported), tolerance=0.0002)
        bpy.ops.wm.read_factory_settings(use_empty=True)
        dual = core.build(hands, weapon, core.BuildOptions(dual=True), left=str(clip), right=str(clip))
        baseline = samples(dual)
        with redirect_stdout(io.StringIO()):
            dual_result = exporting.export(dual, settings, "dual_metric")
        assert not dual_result.get("errors"), dual_result
        compare(baseline, samples(dual))
        objects, actions, scene = set(bpy.data.objects), set(bpy.data.actions), bpy.context.scene
        constraint = dual.constraints.new("COPY_LOCATION")
        try:
            exporting.export(dual, settings, "unsupported")
        except ValueError as exc:
            assert "constraints" in str(exc)
        else:
            raise AssertionError("Unbaked constraints must reject metric export")
        assert bpy.context.scene == scene
        assert set(bpy.data.objects) == objects and set(bpy.data.actions) == actions
        dual.constraints.remove(constraint)
        print("BLENDER_METRIC_EXPORT_OK: source preserved; repeat safe; BLEND/CAST/FBX roundtrip; FBX unit=m")


if __name__ == "__main__":
    main()
