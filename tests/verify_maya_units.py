"""Maya metric output copies, native scene units and animation round trips."""

from dataclasses import replace
from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile

import maya.cmds as cmds
if not hasattr(cmds, "pluginInfo"):
    import maya.standalone
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_reference_pose_compensation import _module_from_path
from verify_batch_animation_export import make_model, make_animation, samples


def compare_scaled(before, after, factor, tolerance=0.0002, matrix_factor=None):
    matrix_factor = factor if matrix_factor is None else matrix_factor
    for frame in before:
        for name, values in before[frame].items():
            if name == "mesh_bounds":
                expected = [[x * factor for x in bound] for bound in values]
                assert len(expected) == len(after[frame][name])
                for left, right in zip(expected, after[frame][name]):
                    assert max(abs(a-b) for a,b in zip(left, right)) < tolerance, (frame, name, left, right)
            else:
                expected = list(values)
                for index in (12, 13, 14):
                    expected[index] *= matrix_factor
                assert max(abs(a-b) for a,b in zip(expected, after[frame][name])) < tolerance, (frame, name, expected, after[frame][name])


def main():
    plugin = ROOT / "plug-ins/viewmodel_weapon_toolkit.py"
    cmds.loadPlugin(str(plugin), quiet=True)
    core = _module_from_path(plugin)
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    with nullcontext(keep) if keep else tempfile.TemporaryDirectory(prefix="cod_metric_maya_") as temporary:
        folder = Path(temporary)
        folder.mkdir(parents=True, exist_ok=True)
        hands, weapon, clip = [folder / (name + ".cast") for name in ("hands", "weapon", "clip")]
        make_model(core, hands, True)
        make_model(core, weapon, False)
        make_animation(core, clip, 3, [
            ("j_gun", "tx", 0, 10, "absolute"),
            ("j_slide", "tz", 1, 4, "absolute"),
            ("j_slide", "rq", (0, 0, 0, 1), (0, 0, 0.3826834, 0.9238795), "absolute")])
        settings = core.AttachOptions(output_dir=str(folder / "out"), force_new_scene=True,
            export_fbx=True, export_smd=True, export_animation=True, output_unit="m")
        result = core._build_single_attachment(str(hands), str(weapon), settings)
        result.animated_outputs = True
        result.animation_path = str(clip)
        core.import_animation_file(str(clip))
        result.frame_range = (0, 3)
        cmds.playbackOptions(animationStartTime=0, animationEndTime=3, minTime=0, maxTime=3)
        nodes = [core._short_name(n) for n in cmds.ls(type="joint")]
        before = samples(nodes, 3)
        cmds.currentUnit(linear="ft")
        live_before = samples(nodes, 3)
        cmds.select(nodes[0])
        cmds.file(rename="untitled_metric_source.ma")
        before_name, before_selection = cmds.file(query=True, sceneName=True), cmds.ls(selection=True)
        before_nodes, before_curves = set(cmds.ls()), set(cmds.ls(type="animCurve"))
        core._write_result_outputs(result, settings)
        assert not result.output_errors, result.output_errors
        assert result.unit_conversion["factor"] == 0.3048
        assert cmds.currentUnit(query=True, linear=True) == "ft"
        assert cmds.file(query=True, sceneName=True) == before_name
        assert cmds.ls(selection=True) == before_selection
        assert set(cmds.ls()) == before_nodes and set(cmds.ls(type="animCurve")) == before_curves
        compare_scaled(live_before, samples(nodes, 3), 1.0)
        first_scene = result.output_scene
        core._write_result_outputs(result, settings)
        assert result.output_scene != first_scene
        compare_scaled(live_before, samples(nodes, 3), 1.0)
        cmds.file(result.output_scene, open=True, force=True, prompt=False, executeScriptNodes=False)
        assert cmds.currentUnit(query=True, linear=True) == "m"
        assert core._units_module().scene_is_metric()
        after = samples(nodes, 3)
        compare_scaled(before, after, 0.3048, matrix_factor=30.48)
        assert abs(cmds.getAttr("viewhands_j_gun.tx", time=3) - 3.048) < 1e-6
        core.import_animation_file(str(clip))
        compare_scaled(before, samples(nodes, 3), 0.3048, matrix_factor=30.48)
        core._write_result_outputs(result, settings)
        assert not result.output_errors and result.unit_conversion["already_metric"]
        assert result.unit_conversion["factor"] == 1.0
        cmds.file(result.output_scene, open=True, force=True, prompt=False, executeScriptNodes=False)
        compare_scaled(before, samples(nodes, 3), 0.3048, matrix_factor=30.48)
        cmds.file(new=True, force=True)
        cmds.currentUnit(linear="m", time="ntsc")
        core._ensure_fbx_exporter()
        cmds.file(result.output_fbx, i=True, type="FBX", ignoreVersion=True)
        compare_scaled(before, samples(nodes, 3), 0.3048, tolerance=0.002, matrix_factor=30.48)
        document = core._castplugin_module().Cast.load(result.output_cast)
        serializer = sys.modules[core._castplugin_module().Cast.__module__]
        animations = [child for root in document.Roots() for child in root.childNodes if isinstance(child, serializer.Animation)]
        curve = next(curve for curve in animations[0].Curves() if curve.NodeName() == "viewhands_j_gun" and curve.KeyPropertyName() == "tx")
        assert abs(curve.KeyValueBuffer()[-1] - 3.048) < 1e-6
        static = core.attach_gun(str(hands), str(weapon), replace(settings,
            export_animation=False, output_dir=str(folder / "static")))
        assert Path(static.output_smd).read_text().count("triangles") == 1
        assert static.unit_conversion["factor"] == 0.3048
        cmds.file(static.output_scene, open=True, force=True, prompt=False, executeScriptNodes=False)
        assert abs(cmds.getAttr("j_wrist_le.tx") + 1.2192) < 1e-6
        dual_clip = folder / "dual_clip.cast"
        make_animation(core, dual_clip, 3, [
            ("j_gun", "tx", 0, 2, "absolute"),
            ("j_wrist_le", "tx", -4, -8, "absolute"),
            ("j_wrist_ri", "tx", 4, 8, "absolute"),
            ("j_slide", "tz", 1, 4, "absolute")])
        dual = core.attach_dual_wield(str(hands), str(weapon), str(dual_clip), str(dual_clip),
            core.DualWieldOptions(output_dir=str(folder / "dual"), force_new_scene=True,
                export_animation=True, export_fbx=True, export_smd=True, output_unit="m"))
        assert not dual.output_errors, dual.output_errors
        dual_nodes = [core._short_name(n) for n in cmds.ls(type="joint")]
        dual_before = samples(dual_nodes, 3)
        cmds.file(dual.output_scene, open=True, force=True, prompt=False, executeScriptNodes=False)
        compare_scaled(dual_before, samples(dual_nodes, 3), 0.3048, matrix_factor=30.48)
        print("MAYA_METRIC_EXPORT_OK: 10ft=3.048m; source preserved; repeated exports; MA/FBX and CAST animation")


if __name__ == "__main__":
    main()
