"""Run in a disposable interactive Maya process with an isolated MAYA_APP_DIR.

VWT_GUI_QA_DIR selects the report directory. This script closes its Maya process.
Unlike mayapy tests, this exercises actual menu/progress/drop registration in GUI.
"""
import json
import os
from pathlib import Path
import sys
import traceback

import maya.cmds as cmds
import maya.utils

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_maya_drop_module_path import main as verify_drop, loaded_plugin_globals


def main(output):
    assert not cmds.about(batch=True), "This test requires an interactive Maya process"
    result = {"maya": cmds.about(version=True), "editions": []}
    previous_backend = None
    for entry in ("viewmodel_weapon_toolkit.py", "viewmodel_weapon_toolkit_zh_CN.py"):
        plugin = ROOT / "plug-ins" / entry
        sys.argv = [__file__, "--plugin", str(plugin)]
        verify_drop()
        namespace = loaded_plugin_globals(plugin)
        backend = namespace["_cast_backend"]()
        assert backend.registered
        assert backend.module.version == "2.01"
        if previous_backend is not None:
            assert backend is previous_backend
        previous_backend = backend
        maya.utils.processIdleEvents()
        assert cmds.menu(namespace["MENU_NAME"], exists=True)
        assert namespace["_CAST_DROP_CALLBACK"] is not None
        assert backend.module._castReadCache is None
        assert backend.module._animationState is None
        namespace["show_dialog"]()
        cmds.refresh(force=True)
        window = namespace["_ui_widget"](namespace["WINDOW_NAME"])
        assert window is not None and window.isVisible()
        assert window.grab().save(str(output / (plugin.stem + ".png")))
        result["editions"].append({
            "entry": entry, "menu": True, "drop_callback": True,
            "single_dual_drops": True, "window": True,
            "backend": backend.info(),
        })
        cmds.file(new=True, force=True)
        cmds.unloadPlugin(plugin.stem, force=True)
        assert not backend.registered
        assert backend.translator_name not in (cmds.translator(query=True, list=True) or [])
        assert not cmds.menu(namespace["MENU_NAME"], exists=True)
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("PRIVATE_CAST_GUI_OK")


if __name__ == "__main__":
    directory = Path(os.environ["VWT_GUI_QA_DIR"]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        main(directory)
    except Exception:
        (directory / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        raise
    finally:
        cmds.quit(force=True)
