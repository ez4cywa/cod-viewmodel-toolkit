"""Maya smoke test for the English, Chinese, and legacy entry points."""

import contextlib
import json
import os
import pathlib
import shutil
import sys
import tempfile

import maya.cmds as cmds

if not hasattr(cmds, "pluginInfo"):
    import maya.standalone
    maya.standalone.initialize(name="python")


ROOT = pathlib.Path(__file__).resolve().parents[1]
PRIMARY = ROOT / "plug-ins" / "viewmodel_weapon_toolkit.py"
CHINESE = ROOT / "plug-ins" / "viewmodel_weapon_toolkit_zh_CN.py"
LEGACY = ROOT / "plug-ins" / "attach_gun.py"
VENDORED_CAST = ROOT / "third_party" / "cast" / "castplugin.py"
VENDORED_CAST_MODULE = ROOT / "third_party" / "cast" / "cast.py"


def _same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == \
        os.path.normcase(os.path.abspath(str(right)))


def _assert_loaded(path, plugin_name):
    loaded_path = cmds.pluginInfo(plugin_name, query=True, path=True)
    version = str(cmds.pluginInfo(plugin_name, query=True, version=True))
    if not _same_path(loaded_path, path):
        raise RuntimeError("Maya loaded the wrong path: %s" % loaded_path)
    if version != "3.1.0":
        raise RuntimeError("Expected version 3.1.0, got %s" % version)
    if not hasattr(cmds, "viewmodelWeaponToolkit"):
        raise RuntimeError("viewmodelWeaponToolkit command is missing")
    if not hasattr(cmds, "attachGun"):
        raise RuntimeError("attachGun compatibility command is missing")


def _assert_vendored_cast_loaded(expected_path):
    loaded_path = cmds.pluginInfo("castplugin", query=True, path=True)
    version = str(cmds.pluginInfo("castplugin", query=True, version=True))
    translators = cmds.pluginInfo(
        "castplugin", query=True, translator=True) or []
    if isinstance(translators, str):
        translators = [translators]
    if not _same_path(loaded_path, expected_path):
        raise RuntimeError("Maya loaded the wrong CAST plugin: %s" % loaded_path)
    if version != "1.99":
        raise RuntimeError("Expected bundled CAST 1.99, got %s" % version)
    if not any(str(name).lower() == "cast" for name in translators):
        raise RuntimeError("Bundled CAST translator is not registered")
    cast_module = sys.modules.get("cast")
    expected_module = pathlib.Path(expected_path).parent / "cast.py"
    if cast_module is None or not _same_path(
            getattr(cast_module, "__file__", ""), expected_module):
        raise RuntimeError("Bundled cast.py was not loaded beside castplugin.py")


def _module_from_path(path):
    for module in tuple(sys.modules.values()):
        module_path = getattr(module, "__file__", "")
        if module_path and _same_path(module_path, path):
            return module
    raise RuntimeError("Loaded plugin module was not found: %s" % path)


@contextlib.contextmanager
def _temporary_dual_state(plugin_module, state):
    node = cmds.createNode("network", name=plugin_module.DUAL_STATE_NODE)
    cmds.addAttr(node, longName="attachGunDualJson", dataType="string")
    cmds.setAttr(
        node + ".attachGunDualJson",
        json.dumps(state, sort_keys=True),
        type="string",
    )
    try:
        yield
    finally:
        cmds.delete(node)


def _assert_incomplete_dual_output_metadata_is_compatible(plugin_module):
    """Output bookkeeping must not block rig/animation validation."""
    state = {
        "schema_version": 1,
        "animation_mode": "simultaneous",
        "shared_hands_source": "right",
        "source_joint": "j_gun",
        "left_target_joint": "tag_weapon_left",
        "right_target_joint": "tag_weapon_right",
        "left_prefix": "left_",
        "right_prefix": "right_",
        "hands_joint_uuids": {},
        "left_weapon_joint_uuids": {},
        "right_weapon_joint_uuids": {},
        "left_source_uuid": "left-source",
        "right_source_uuid": "right-source",
        "left_target_uuid": "left-target",
        "right_target_uuid": "right-target",
        "left_clip_range": [0.0, 30.0],
        "right_clip_range": [0.0, 30.0],
        "playback_range": [0.0, 30.0],
        "framerate": 30.0,
        "viewhands_path": "hands.cast",
        "weapon_path": "weapon.cast",
        "left_animation_path": "left.cast",
        "right_animation_path": "right.cast",
        "expected_joint_count": 0,
        "expected_mesh_count": 0,
    }
    with _temporary_dual_state(plugin_module, state):
        _, loaded = plugin_module._read_dual_state()
    for key in (
            "output_scene", "output_cast", "output_smd", "output_fbx",
            "output_manifest"):
        if loaded.get(key) != "":
            raise RuntimeError("Incomplete metadata did not default %s" % key)
    if loaded.get("requested_outputs") != {
            "ma": False, "cast": False, "smd": False, "fbx": False}:
        raise RuntimeError("Incomplete metadata output choices are incorrect")
    if loaded.get("reference_pose_path") != "":
        raise RuntimeError("Legacy metadata gained a reference-pose path")
    if loaded.get("reference_pose_compensation", {}).get("enabled"):
        raise RuntimeError("Legacy metadata enabled reference compensation")

    invalid_state = dict(state)
    invalid_state.pop("source_joint")
    with _temporary_dual_state(plugin_module, invalid_state):
        try:
            plugin_module._read_dual_state()
        except RuntimeError as exc:
            if str(exc) != "Dual-wield metadata is missing: source_joint":
                raise
        else:
            raise RuntimeError("Missing structural metadata was accepted")


class _FakeDialogCommands:
    def __init__(self):
        self.keywords = {}
        self.file_dialog_result = ["selected.cast"]

    def confirmDialog(self, **kwargs):
        self.keywords = kwargs
        return kwargs["button"][-1]

    def fileDialog2(self, **kwargs):
        self.keywords = kwargs
        return self.file_dialog_result


def main():
    if cmds.pluginInfo("castplugin", query=True, loaded=True):
        cmds.unloadPlugin("castplugin", force=True)
    sys.modules.pop("castplugin", None)
    sys.modules.pop("cast", None)
    runtime_cast_dir = pathlib.Path(tempfile.mkdtemp(
        prefix="viewmodel_weapon_toolkit_cast_"))
    runtime_cast = runtime_cast_dir / "castplugin.py"
    shutil.copy2(str(VENDORED_CAST_MODULE), str(runtime_cast_dir / "cast.py"))
    shutil.copy2(str(VENDORED_CAST), str(runtime_cast))
    cmds.loadPlugin(str(runtime_cast), quiet=True)
    _assert_vendored_cast_loaded(runtime_cast)

    cmds.loadPlugin(str(PRIMARY), quiet=True)
    cmds.loadPlugin(str(LEGACY), quiet=True)
    _assert_loaded(PRIMARY, "viewmodel_weapon_toolkit")
    _assert_loaded(LEGACY, "attach_gun")
    primary_module = _module_from_path(PRIMARY)
    if primary_module._cast_animation_import_options(False) != \
            "importAtTime=0;importReset=0;importLooping=0":
        raise RuntimeError("Static CAST animation options are incorrect")
    if primary_module._cast_animation_import_options(True) != \
            "importAtTime=1;importReset=0;importLooping=0":
        raise RuntimeError("Offset CAST animation options are incorrect")
    _assert_incomplete_dual_output_metadata_is_compatible(primary_module)
    cmds.unloadPlugin("attach_gun", force=True)
    if not hasattr(cmds, "viewmodelWeaponToolkit"):
        raise RuntimeError("Unloading the legacy loader removed primary commands")
    cmds.unloadPlugin("viewmodel_weapon_toolkit", force=True)

    cmds.loadPlugin(str(CHINESE), quiet=True)
    _assert_loaded(CHINESE, "viewmodel_weapon_toolkit_zh_CN")
    chinese_core = sys.modules.get("viewmodel_weapon_toolkit_zh_cn_core")
    if chinese_core is None:
        raise RuntimeError("Chinese shared core module is unavailable")
    if chinese_core.VERSION != "3.1.0":
        raise RuntimeError("Chinese core changed the release version")
    translator = chinese_core.cmds._commands
    if translator is not cmds:
        raise RuntimeError("Chinese UI proxy is not attached to maya.cmds")
    if chinese_core._zh_cn_entry_version != "3.1.0":
        raise RuntimeError("Chinese entry point changed the release version")
    translate_ui_text = chinese_core._zh_cn_translate_ui_text
    if translate_ui_text("Dual-Wield Builder...") != \
            "双持构建器…":
        raise RuntimeError("Chinese menu translation is unavailable")
    if translate_ui_text("Reference pose (optional):") != \
            "参考姿态（可选）：":
        raise RuntimeError("Chinese reference-pose field is untranslated")
    if translate_ui_text("Failed:\nexample") != \
            "失败：\nexample":
        raise RuntimeError("Chinese error translation is unavailable")
    if translate_ui_text(
            ".cast/.smd model export uses bundled/compatible Cast v1.99;") != \
            ".cast/.smd 模型导出使用内置/兼容的 Cast v1.99；":
        raise RuntimeError("Chinese bundled CAST text is unavailable")
    fake_commands = _FakeDialogCommands()
    proxy = type(chinese_core.cmds)(fake_commands)
    response = proxy.confirmDialog(
        title="Viewmodel Weapon Toolkit - Unsaved Scene",
        message="Failed:\nexample",
        button=["Save", "Cancel"],
        defaultButton="Save",
        cancelButton="Cancel",
    )
    if response != "Cancel":
        raise RuntimeError("Localized dialog response was not normalized")
    if fake_commands.keywords["button"] != ["保存", "取消"]:
        raise RuntimeError("Localized dialog buttons are incorrect")
    if fake_commands.keywords["title"] != \
            "视角模型武器工具包 - 未保存场景":
        raise RuntimeError("Localized dialog title is incorrect")
    file_dialog_result = proxy.fileDialog2(
        caption="Select .cast file",
        okCaption="Select",
    )
    if file_dialog_result is not fake_commands.file_dialog_result:
        raise RuntimeError("Localized file dialog changed its path list")
    if fake_commands.keywords["caption"] != "选择 .cast 文件":
        raise RuntimeError("Localized file dialog caption is incorrect")
    cmds.unloadPlugin("viewmodel_weapon_toolkit_zh_CN", force=True)
    if hasattr(cmds, "viewmodelWeaponToolkit"):
        raise RuntimeError("Chinese command survived plugin unload")

    cmds.loadPlugin(str(LEGACY), quiet=True)
    _assert_loaded(LEGACY, "attach_gun")
    _assert_loaded(PRIMARY, "viewmodel_weapon_toolkit")
    cmds.unloadPlugin("attach_gun", force=True)
    if not hasattr(cmds, "viewmodelWeaponToolkit"):
        raise RuntimeError("Primary command did not survive legacy unload")
    cmds.unloadPlugin("viewmodel_weapon_toolkit", force=True)
    cmds.unloadPlugin("castplugin", force=True)
    shutil.rmtree(str(runtime_cast_dir))
    print("PLUGIN_IDENTITY_VERIFICATION_OK")


if __name__ == "__main__":
    main()
