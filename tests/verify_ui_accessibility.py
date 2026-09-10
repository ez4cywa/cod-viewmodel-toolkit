"""Run in interactive Maya to check native UI sizing, focus and both editions."""

import json
import os
from pathlib import Path
import sys
import traceback

import maya.cmds as cmds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_batch_animation_ui import load, main as verify_queue_ui


def main(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    verify_queue_ui(str(directory / "queue.json"))
    english = load(ROOT / "plug-ins" / "viewmodel_weapon_toolkit.py", "vwt_a11y_en")
    chinese = load(ROOT / "plug-ins" / "viewmodel_weapon_toolkit_zh_CN.py", "vwt_a11y_zh")
    results = []
    for edition, module in (("en", english), ("zh", chinese._implementation)):
        QtCore, QtWidgets, _ = module._ui_qt()
        for dual in (False, True):
            for batch in (False, True):
                show = module.show_dual_dialog if dual else module.show_dialog
                show(batch=batch)
                win = module.DUAL_WINDOW_NAME if dual else module.WINDOW_NAME
                root = module._ui_widget(win)
                field = module._ui_widget(
                    module.DUAL_VIEWHANDS_FIELD if dual else module.VIEWHANDS_FIELD)
                assert field.accessibleName() == module._ui_translate("Viewhands:")
                assert field.hasFocus(), (edition, dual, batch, "initial focus")
                assert root.minimumWidth() == 560
                for name, (label, _, browse) in module._UI_FIELD_LABELS.items():
                    widget = module._ui_widget(name)
                    assert widget.accessibleName() == module._ui_translate(label)
                    assert widget.height() >= 28, (name, widget.height())
                    if browse:
                        button = module._ui_widget(browse)
                        assert module._ui_translate(label) in button.accessibleName()
                        assert button.focusPolicy() == QtCore.Qt.StrongFocus
                for width in (560, 760):
                    root.resize(width, 740)
                    QtWidgets.QApplication.processEvents()
                    cmds.refresh()
                    image_path = directory / ("%s_%s_%s_%s.png" % (
                        edition, "dual" if dual else "single",
                        "batch" if batch else "builder", width))
                    assert root.grab().save(str(image_path))
                    assert not root.findChildren(QtWidgets.QScrollBar) or all(
                        bar.maximum() == 0 or not bar.isVisible()
                        for bar in root.findChildren(QtWidgets.QScrollBar)
                        if bar.orientation() == QtCore.Qt.Horizontal), [
                            (bar.objectName(), bar.maximum())
                            for bar in root.findChildren(QtWidgets.QScrollBar)
                            if bar.orientation() == QtCore.Qt.Horizontal]
                for frame, _ in module._UI_SECTIONS:
                    cmds.frameLayout(frame, edit=True, collapse=False)
                root.resize(560, 740)
                for _ in range(3):
                    QtWidgets.QApplication.processEvents()
                module._ui_reflow_labels()
                for name in module._UI_FIELD_LABELS:
                    widget = module._ui_widget(name)
                    assert widget.font().pointSizeF() >= 10
                    if not widget.isEnabled() or not widget.isVisible():
                        continue
                    # Maya startup can reactivate modelPanel4 asynchronously.
                    # Test traversal within the explicitly active tool window.
                    QtWidgets.QApplication.setActiveWindow(root)
                    widget.setFocus(QtCore.Qt.TabFocusReason)
                    for _ in range(3):
                        QtWidgets.QApplication.processEvents()
                    assert widget.hasFocus(), (
                        name, "keyboard focus", QtWidgets.QApplication.focusWidget())
                    parent = widget.parentWidget()
                    while parent and parent is not root:
                        if isinstance(parent, QtWidgets.QScrollArea):
                            rectangle = QtCore.QRect(
                                widget.mapTo(parent.viewport(), QtCore.QPoint(0, 0)),
                                widget.size())
                            assert parent.viewport().rect().contains(rectangle), (
                                name, rectangle, parent.viewport().rect())
                            break
                        parent = parent.parentWidget()
                assert root.grab().save(str(directory / (
                    "%s_%s_%s_expanded.png" % (
                        edition, "dual" if dual else "single",
                        "batch" if batch else "builder"))))
                results.append({"edition": edition, "dual": dual, "batch": batch,
                                "minimum_field_font_points": 10,
                                "expanded": True, "focus_visible": True})
    (directory / "accessibility.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    print("UI_ACCESSIBILITY_OK", results)


if __name__ == "__main__":
    output = Path(os.environ["VWT_UI_QA_DIR"])
    try:
        main(output)
    except Exception:
        output.mkdir(parents=True, exist_ok=True)
        (output / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        cmds.quit(force=True)
