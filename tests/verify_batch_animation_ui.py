"""Run main() inside interactive Maya to verify native EN/ZH queue controls.

Export algorithms are tested separately. Here file picking and the batch runner
are stubbed to verify queue pairing, format selection, and callback wiring.
Use an isolated Maya profile; this test exercises preference persistence.
"""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile

import maya.cmds as cmds

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main(report_path=None):
    assert not cmds.about(batch=True), "Run inside interactive Maya, not mayapy"
    english = load(ROOT / "plug-ins" / "viewmodel_weapon_toolkit.py", "vwt_ui_test_en")
    chinese = load(ROOT / "plug-ins" / "viewmodel_weapon_toolkit_zh_CN.py", "vwt_ui_test_zh")
    reports = []
    with tempfile.TemporaryDirectory(prefix="vwt_ui_test_") as temporary:
        fixture = Path(temporary) / "sample.cast"
        fixture.write_bytes(b"cast")
        second = Path(temporary) / "second.cast"
        second.write_bytes(b"cast")
        original_picker, original_dialog = cmds.fileDialog2, cmds.confirmDialog
        try:
            for lang, module, translate in (
                    ("en", english, lambda text: text),
                    ("zh", chinese._implementation, chinese.translate_ui_text)):
                for dual in (False, True):
                    confirmations, runs = [], []
                    cmds.confirmDialog = lambda **kwargs: confirmations.append(kwargs) or "OK"
                    module._confirm_scene_reset = lambda: True
                    (module.show_dual_dialog if dual else module.show_dialog)(batch=True)

                    def click(label):
                        controls = [control for control in cmds.lsUI(type="button", long=True)
                                    if cmds.button(control, exists=True) and
                                    cmds.button(control, query=True, label=True) == translate(label)]
                        assert len(controls) == 1, (lang, label, controls)
                        command = cmds.button(controls[0], query=True, command=True)
                        assert callable(command), (label, command)
                        command()

                    fields = [module.DUAL_VIEWHANDS_FIELD, module.DUAL_WEAPON_FIELD] if dual else [
                        module.VIEWHANDS_FIELD, module.WEAPON_FIELD]
                    for field in fields:
                        cmds.textField(field, edit=True, text=str(fixture))
                    cmds.textField(module.OUTPUT_DIR_FIELD, edit=True, text=temporary)
                    cmds.fileDialog2 = lambda **kwargs: [str(fixture), str(second)]
                    click("Add Animation Pairs..." if dual else "Add Animations...")
                    assert cmds.textScrollList(module.BATCH_ANIMATION_LIST, query=True,
                                               numberOfItems=True) == 2
                    # Re-adding identical entries should not duplicate jobs.
                    click("Add Animation Pairs..." if dual else "Add Animations...")
                    assert cmds.textScrollList(module.BATCH_ANIMATION_LIST, query=True,
                                               numberOfItems=True) == 2
                    cmds.textScrollList(module.BATCH_ANIMATION_LIST, edit=True, selectIndexedItem=2)
                    click("Remove Selected")
                    assert cmds.textScrollList(module.BATCH_ANIMATION_LIST, query=True,
                                               numberOfItems=True) == 1
                    if dual:
                        for field in (module.DUAL_LEFT_ANIMATION_FIELD, module.DUAL_RIGHT_ANIMATION_FIELD):
                            cmds.textField(field, edit=True, text=str(second))
                        click("Add Current Pair")
                        assert cmds.textScrollList(module.BATCH_ANIMATION_LIST, query=True,
                                                   numberOfItems=True) == 2

                    for field, enabled in ((module.EXPORT_MA_CHECK, False),
                                           (module.EXPORT_CAST_CHECK, False),
                                           (module.EXPORT_SMD_CHECK, True),
                                           (module.EXPORT_FBX_CHECK, True)):
                        cmds.checkBox(field, edit=True, value=enabled)

                    def runner(hands, weapon, jobs, options, progress):
                        assert module.selected_output_formats(options) == ("smd", "fbx")
                        assert options.force_new_scene
                        assert progress(0, len(jobs), jobs[0] if dual else (jobs[0],))
                        runs.append(list(jobs))
                        return {"items": [{"status": "ok"} for job in jobs],
                                "completed": len(jobs), "cancelled": False,
                                "summary_path": str(Path(temporary) / "report.json")}

                    if dual:
                        module.batch_export_dual_animations = runner
                    else:
                        module.batch_export_animations = runner
                    click("Batch Export Animations")
                    assert len(runs) == 1 and len(confirmations) == 1, (runs, confirmations)
                    assert "Report" in confirmations[0]["message"] or "报告" in confirmations[0]["message"]
                    assert cmds.text(module.BATCH_ANIMATION_STATUS, query=True, label=True) == translate("Finished")
                    reports.append({"language": lang, "dual": dual, "passed": True})
        finally:
            cmds.fileDialog2, cmds.confirmDialog = original_picker, original_dialog
    if report_path:
        Path(report_path).write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print("BATCH_ANIMATION_UI_PASSED", reports)
    return reports
