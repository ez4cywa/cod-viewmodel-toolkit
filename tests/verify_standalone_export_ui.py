"""Exercise export dialogs and cancellation without opening a desktop window."""

import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


class UICommands:
    """Small native-control fixture; the real exporter remains behind its API."""

    def __init__(self):
        self.controls = {}
        self.sequence = 0
        self.menu_records = []
        self.dialog_result = []
        self.errors = []

    def __getattr__(self, command):
        def invoke(*args, **values):
            name = args[0] if args else None
            if values.get("exists"):
                return name in self.controls
            if command == "fileDialog2":
                return self.dialog_result
            if command == "playbackOptions":
                return 2 if values.get("minTime") or values.get("animationStartTime") else 12
            if command == "optionVar":
                return False
            if command == "confirmDialog":
                self.errors.append(values)
                return "OK"
            if command == "deleteUI":
                self.controls.pop(name, None)
                return
            if values.get("query"):
                state = self.controls[name]
                for key in ("text", "select", "value1", "value2", "label"):
                    if values.get(key):
                        return state.get(key, 1 if key == "select" else "")
                return None
            if values.get("edit"):
                self.controls[name].update(values)
                return name
            if command in ("setParent", "showWindow"):
                return
            self.sequence += 1
            name = name or "%s%d" % (command, self.sequence)
            self.controls[name] = dict(values)
            if command == "menuItem":
                self.menu_records.append(values)
            return name
        return invoke


def load_core(commands, chinese=False):
    maya = types.ModuleType("maya")
    maya.__path__ = []
    modules = {"maya": maya, "maya.cmds": commands}
    for name in ("maya.mel", "maya.OpenMaya", "maya.OpenMayaMPx", "maya.OpenMayaUI", "maya.api", "maya.api.OpenMaya"):
        modules[name] = types.ModuleType(name)
    modules["maya.mel"].eval = lambda *_: "mainWindow"
    modules["maya.OpenMayaMPx"].MPxCommand = object
    modules["maya.OpenMayaUI"].MExternalDropCallback = object
    with patch.dict(sys.modules, modules):
        filename = "viewmodel_weapon_toolkit_zh_CN.py" if chinese else "viewmodel_weapon_toolkit.py"
        spec = importlib.util.spec_from_file_location(
            "standalone_export_ui_zh" if chinese else "standalone_export_ui_core",
            ROOT / "plug-ins" / filename)
        core = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = core
        spec.loader.exec_module(core)
    return core._implementation if chinese else core


def verify_dialogs(core, commands, chinese=False):
    assert hasattr(core, "show_export_dialog")
    exporter = types.SimpleNamespace(export_file=Mock(return_value={"path": "exported.fbx", "format": "fbx"}))
    core._exports_module = lambda: exporter
    for file_format in ("fbx", "smd"):
        prefix = "codViewmodelExport" + file_format.upper()
        core.show_export_dialog(file_format)
        path = prefix + "Path"
        assert commands.controls[path]["text"] == ""
        with patch.object(core, "_exports_module", side_effect=AssertionError("Cancelled browse started an exporter")):
            commands.dialog_result = []
            core._browse_export_file(path, file_format)
        assert commands.controls[path]["text"] == ""
        commands.dialog_result = ["D:/exports/test." + file_format]
        core._browse_export_file(path, file_format)
        controls = {"path": path, "mode": prefix + "Mode", "frames": prefix + "Frames",
                    "unit": prefix + "Unit", "status": prefix + "Status"}
        commands.controls[controls["frames"]].update(value1=3, value2=9)
        # Explicit static mode must win even if the prior batch result was animated.
        core._LAST_RESULT = types.SimpleNamespace(animated_outputs=True)
        commands.controls[controls["mode"]]["select"] = 1
        core._export_from_dialog(file_format, controls)
        assert exporter.export_file.call_args.kwargs["animated"] is False
        assert exporter.export_file.call_args.kwargs["frame_range"] is None
        assert exporter.export_file.call_args.kwargs["output_unit"] == "original"
        commands.controls[controls["mode"]]["select"] = 2
        commands.controls[controls["unit"]]["select"] = 2
        core._export_from_dialog(file_format, controls)
        assert exporter.export_file.call_args.kwargs["animated"] is True
        assert exporter.export_file.call_args.kwargs["frame_range"] == (3, 9)
        assert exporter.export_file.call_args.kwargs["output_unit"] == "m"
        assert not commands.errors, commands.errors
        exporter.export_file.side_effect = RuntimeError("fixture writer failure")
        core._export_from_dialog(file_format, controls)
        assert len(commands.errors) == 1
        commands.errors.clear()
        exporter.export_file.side_effect = None
    core.create_menu()
    for label in (("单独导出 FBX…", "单独导出 SMD…") if chinese
                  else ("Export FBX...", "Export SMD...")):
        assert any(item.get("label") == label for item in commands.menu_records), label
    assert not any("MAX" in item.get("label", "") for item in commands.menu_records)
    if chinese:
        assert commands.controls["codViewmodelExportFBXFrames"]["label"] == "帧范围："
    print("STANDALONE_EXPORT_UI_OK", "ZH" if chinese else "EN")


def main():
    for chinese in (False, True):
        commands = UICommands()
        core = load_core(commands, chinese)
        core.log = lambda *_: None
        # Exercise the same missing-__file__ case as Maya's registration loader.
        core._TOOLKIT_PLUGIN_PATH = str(ROOT / "plug-ins" / (
            "viewmodel_weapon_toolkit_zh_CN.py" if chinese else "viewmodel_weapon_toolkit.py"))
        core.__dict__.pop("__file__", None)
        exporters = core._exports_module()
        assert Path(exporters.__file__).resolve() == ROOT / "plug-ins/cod_viewmodel_exports.py"
        assert core._exports_module() is exporters
        verify_dialogs(core, commands, chinese)
        for label in (("导入 CAST…", "内置 CAST 拖入处理") if chinese
                      else ("Import CAST...", "Built-in CAST Drag and Drop")):
            assert any(item.get("label") == label for item in commands.menu_records), label
        with patch.object(core, "import_cast_file", return_value={"kind": "model"}) as importer:
            commands.dialog_result = []
            core._import_cast_ui()
            importer.assert_not_called()
            commands.dialog_result = ["model.cast"]
            core._import_cast_ui()
            importer.assert_called_once_with("model.cast")
            assert not commands.errors
            importer.side_effect = RuntimeError("fixture CAST import failure")
            core._import_cast_ui()
            assert len(commands.errors) == 1
            commands.errors.clear()
        print("CAST_IMPORT_MENU_OK", "ZH" if chinese else "EN")
        backend = types.SimpleNamespace(unregister=Mock())
        plugin = types.SimpleNamespace(deregisterCommand=Mock())
        with patch.object(core.OpenMayaMPx, "MFnPlugin", return_value=plugin, create=True), \
                patch.object(core, "_cast_backend", return_value=backend), \
                patch.object(core, "remove_menu"):
            core.uninitializePlugin(object())
        for file_format in ("FBX", "SMD"):
            assert "codViewmodelExport%sWindow" % file_format not in commands.controls
        backend.unregister.assert_called_once_with(plugin)
        print("STANDALONE_EXPORT_UNLOAD_OK", "ZH" if chinese else "EN")


if __name__ == "__main__":
    main()
