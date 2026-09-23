"""Mayapy: successful builders are non-modal; failures still show a dialog."""
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch
import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plug-ins"))
import viewmodel_weapon_toolkit as core
import viewmodel_weapon_toolkit_zh_CN as chinese


def main():
    for module in (core, chinese._implementation):
        for callback, worker in (("_run_from_dialog", "attach_gun"),
                                 ("quick_attach", "attach_gun"),
                                 ("_run_dual_from_dialog", "attach_dual_wield"),
                                 ("_batch_from_dialog", "attach_gun")):
            for fail in (False, True, "partial"):
                fake = MagicMock()
                fake.output_errors = {"fbx": "fixture partial failure"} if fail == "partial" else {}
                options = module.AttachOptions(force_new_scene=True)
                with patch.multiple(module,
                        _require_dialog_paths=lambda **kw: ("hands.cast", "weapon.cast"),
                        _dialog_options=lambda **kw: options,
                        _dual_dialog_options=lambda **kw: options,
                        _dual_dialog_paths=lambda: ("h", "w", "l", "r"),
                        _save_dual_dialog_settings=lambda *a: None,
                        _confirm_scene_reset=lambda: True,
                        _field_text=lambda *a: "weapon.cast",
                        load_viewhands_path=lambda: __file__,
                        load_saved_options=lambda **kw: options,
                        save_options=lambda *a: None), \
                     patch.object(module, worker, side_effect=RuntimeError("fixture failure") if fail is True else None,
                                  return_value=fake), \
                     patch.object(cmds, "fileDialog2", return_value=["weapon.cast"]), \
                     patch.object(cmds, "progressWindow", return_value=False), \
                     patch.object(cmds, "control", return_value=False), \
                     patch.object(cmds, "confirmDialog") as dialog:
                    getattr(module, callback)()
                    assert dialog.call_count == int(bool(fail)), (callback, fail, dialog.call_args_list)
        print("ATTACHMENT_FEEDBACK_OK", module.__name__)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
