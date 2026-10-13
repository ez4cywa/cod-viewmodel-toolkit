"""Mayapy: builders can retain a result without writing any output files."""

from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import maya.cmds as cmds
import maya.standalone

maya.standalone.initialize(name="python")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plug-ins"))
sys.path.insert(0, str(ROOT / "tests"))
import viewmodel_weapon_toolkit as core
from verify_batch_animation_export import make_animation, make_model


def assert_no_files(result, folder):
    assert not folder.exists(), "A scene-only build created an output folder"
    for field in ("output_scene", "output_cast", "output_smd", "output_fbx", "output_manifest"):
        assert getattr(result, field) == "", field
    assert not any(result.requested_outputs.values())


def main():
    assert core.selected_output_formats(core.AttachOptions()) == ()
    core.clear_saved_settings()
    for name in (core.EXPORT_MA_OPTVAR, core.EXPORT_CAST_OPTVAR, core.EXPORT_SMD_OPTVAR, core.EXPORT_FBX_OPTVAR):
        cmds.optionVar(intValue=(name, 1))
    cmds.optionVar(stringValue=(core.OUTPUT_DIR_OPTVAR, "preserved-output"))
    cmds.optionVar(stringValue=(core.SOURCE_JOINT_OPTVAR, "preserved_joint"))
    upgraded = core.load_saved_options()
    assert core.selected_output_formats(upgraded) == ()
    assert upgraded.output_dir == "preserved-output" and upgraded.source_joint == "preserved_joint"
    upgraded.export_fbx = True
    core.save_options("preserved-hands.cast", upgraded)
    assert core.selected_output_formats(core.load_saved_options()) == ("fbx",)
    assert core.load_viewhands_path() == "preserved-hands.cast"
    core.clear_saved_settings()

    with tempfile.TemporaryDirectory(prefix="cod_optional_outputs_") as temporary:
        folder = Path(temporary)
        hands, weapon = folder / "hands.cast", folder / "weapon.cast"
        left, right = folder / "vm_akimbo_l_test.cast", folder / "vm_akimbo_r_test.cast"
        core.ensure_cast_plugin()
        make_model(core, hands, True)
        make_model(core, weapon, False)
        units = core._units_module()
        for clip in (left, right):
            make_animation(core, clip, 3, [
                ("j_gun", "tx", 0, 2, "absolute"),
                ("j_slide", "tz", 1, 4, "absolute"),
                ("j_wrist_le", "tx", -4, -8, "absolute"),
                ("j_wrist_ri", "tx", 4, 8, "absolute"),
            ])
        output = folder / "disabled-output"
        options = core.AttachOptions(output_dir=str(output), force_new_scene=True, output_unit="m")
        with patch.object(units, "export_copy", side_effect=AssertionError("No-output build started metric worker")):
            result = core.attach_gun(str(hands), str(weapon), options)
        assert_no_files(result, output)
        core.validate_attachment()
        try:
            core.save_current_result(options)
        except RuntimeError as exc:
            assert "Select at least one" in str(exc)
        else:
            raise AssertionError("Saving with no selected formats succeeded")
        assert_no_files(result, output)
        core.save_options(str(hands), core.AttachOptions(output_dir=str(output), save_scene=True))
        saved = core.save_current_result()
        assert Path(saved).is_file() and Path(result.output_manifest).is_file()
        assert result.output_cast == result.output_smd == result.output_fbx == ""
        assert result.requested_outputs == {"ma": True, "cast": False, "smd": False, "fbx": False}

        dual_output = folder / "disabled-dual"
        with patch.object(units, "export_copy", side_effect=AssertionError("No-output dual started metric worker")):
            dual = core.attach_dual_wield(str(hands), str(weapon), str(left), str(right), core.DualWieldOptions(
                output_dir=str(dual_output), force_new_scene=True, output_unit="m"))
        assert_no_files(dual, dual_output)
        core.validate_dual_wield()
        core.save_current_result(core.AttachOptions(output_dir=str(dual_output), save_scene=True))
        _, state = core._read_dual_state()
        assert state["output_manifest"] == dual.output_manifest
        assert state["requested_outputs"] == dual.requested_outputs
        assert Path(dual.output_scene).is_file() and Path(dual.output_manifest).is_file()

        with patch.object(core, "attach_gun", side_effect=AssertionError("Invalid batch started a build")):
            try:
                core.batch_attach(str(hands), [str(weapon)], core.AttachOptions())
            except RuntimeError as exc:
                assert "Select at least one" in str(exc)
            else:
                raise AssertionError("No-output batch was accepted")

        quick_output = folder / "disabled-quick"
        quick_options = core.AttachOptions(output_dir=str(quick_output), force_new_scene=True, output_unit="m")
        with patch.object(core, "load_viewhands_path", return_value=str(hands)), \
             patch.object(core, "load_saved_options", return_value=quick_options), \
             patch.object(core, "_confirm_scene_reset", return_value=True), \
             patch.object(cmds, "fileDialog2", return_value=[str(weapon)]), \
             patch.object(units, "export_copy", side_effect=AssertionError("Quick attach started metric worker")):
            core.quick_attach()
        assert_no_files(core._LAST_RESULT, quick_output)

    print("OPTIONAL_OUTPUTS_OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
