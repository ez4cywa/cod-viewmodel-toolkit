"""Exercise CAST 2.00 names through real model import and animation routing."""

from pathlib import Path
import sys
import tempfile

import maya.cmds as cmds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_batch_animation_export import make_model, make_animation, assert_ok
from verify_reference_pose_compensation import _module_from_path


def main():
    plugin = ROOT / "plug-ins" / "viewmodel_weapon_toolkit.py"
    cmds.loadPlugin(str(plugin), quiet=True)
    module = _module_from_path(plugin)
    cast_module = module._castplugin_module()
    assert cast_module.version == "2.00"
    with tempfile.TemporaryDirectory(prefix="vwt_cast200_") as directory:
        directory = Path(directory)
        hands, weapon = directory / "hands.cast", directory / "weapon.cast"
        make_model(module, hands, True)
        make_model(module, weapon, False)
        for raw_name, imported_name in (
                ("9 slide", "_9_slide"), ("if", "_if"),
                ("j-slide", "j_slide"), (" slide ", "slide")):
            model_file = cast_module.Cast.load(str(weapon))
            skeleton = model_file.Roots()[0].ChildrenOfType(
                cast_module.Model)[0].Skeleton()
            skeleton.Bones()[1].SetName(raw_name)
            model_file.save(str(weapon))
            assert cast_module.utilitySanitize(raw_name) == imported_name
            inventory = module._cast_bone_inventory(str(weapon))
            assert imported_name in inventory["bone_names"]
            left, right = directory / "left.cast", directory / "right.cast"
            make_animation(module, left, 2, [
                ("j_wrist_le", "tx", -4, -5, "absolute"),
                (raw_name, "tz", 1, 4, "absolute")])
            make_animation(module, right, 2, [
                ("j_gun", "tx", 0, 1, "absolute"),
                ("j_wrist_ri", "tx", 4, 5, "absolute"),
                (raw_name, "tz", 1, 6, "absolute")])
            options = module.DualWieldOptions(
                output_dir=str(directory / imported_name),
                export_cast=False, force_new_scene=True)
            result = module.attach_dual_wield(
                str(hands), str(weapon), str(left), str(right), options)
            assert result.dual_verification["left"]["curve_range"] == (0.0, 2.0)
            cmds.currentTime(2)
            assert abs(cmds.getAttr("akimbo_l_" + imported_name + ".tz") - 4) < 1e-5
            assert abs(cmds.getAttr("akimbo_r_" + imported_name + ".tz") - 6) < 1e-5
            single = module.batch_export_animations(
                str(hands), str(weapon), [str(right)], module.AttachOptions(
                    output_dir=str(directory / ("single_" + imported_name)),
                    force_new_scene=True, export_smd=True))
            assert_ok(single)

        # Reject normalization collisions during preflight, before scene reset.
        model_file = cast_module.Cast.load(str(weapon))
        skeleton = model_file.Roots()[0].ChildrenOfType(cast_module.Model)[0].Skeleton()
        skeleton.Bones()[1].SetName("j slide")
        duplicate = skeleton.CreateBone()
        duplicate.SetName("j_slide")
        duplicate.SetParentIndex(0)
        model_file.save(str(weapon))
        before = cmds.file(query=True, sceneName=True)
        try:
            module.preflight_inputs(str(hands), str(weapon))
        except RuntimeError as error:
            assert "both import as" in str(error), str(error)
        else:
            raise AssertionError("Normalization collision was accepted")
        assert cmds.file(query=True, sceneName=True) == before
        cmds.file(new=True, force=True)
    print("CAST_V200_INTEGRATION_OK")


if __name__ == "__main__":
    main()
