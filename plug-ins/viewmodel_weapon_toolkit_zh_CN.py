"""Simplified Chinese entry point for CoD Viewmodel Toolkit 3.4.0.

This file reuses the English implementation beside it and localizes Maya UI
text at the command boundary. Technical identifiers, joint names, file
formats, animation mode values, and diagnostic details remain unchanged so
that scenes, scripts, and support logs are compatible between editions.

Load either this file or ``viewmodel_weapon_toolkit.py`` in Maya's Plug-in
Manager. The two editions register the same commands and must not be loaded
at the same time.
"""

import importlib.util
import os
import sys

import maya.cmds as _maya_cmds


VERSION = "3.4.0"
_LOADER_FILE = globals().get("__file__") or sys._getframe().f_code.co_filename
_CORE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(_LOADER_FILE)),
    "viewmodel_weapon_toolkit.py",
)
_CORE_MODULE_NAME = "viewmodel_weapon_toolkit_zh_cn_core"


_EXACT_TRANSLATIONS = {
    "Output unit:": "输出单位：",
    "Keep original": "保持原样",
    "Meters (input: ft)": "米（输入：ft）",
    "Meters converts an export copy: 1 ft = 0.3048 m. The working scene is unchanged.":
        "仅转换导出副本：1 ft = 0.3048 m，不改变当前工作场景。",
    "Source files": "输入文件",
    "Joint mapping": "关节映射",
    "Joint mapping and reference pose": "关节映射与参考姿态",
    "Output files": "输出文件",
    "Current scene tools": "当前场景工具",
    "Operation status": "操作状态",
    "Duplicates one weapon onto the left and right hand tags.": "将同一武器复制到左右手挂点。",
    "Select at least one format. Blank folders use the default folder.": "至少勾选一种格式。目录留空时使用默认目录。",
    "CAST, SMD and FBX here export static models. Use Animation Batch for animated exports.": "此处 CAST、SMD 和 FBX 导出静态模型。导出动画请使用动画批量导出。",
    "No animations queued. Add files to begin.": "队列为空，请先添加动画文件。",
    "Single Animation Batch...": "单武器动画批量导出…",
    "Dual Animation Batch...": "双持动画批量导出…",
    "Model + animation CAST (.cast)": "模型与动画 CAST（.cast）",
    "Skeleton animation only (.smd)": "仅骨骼动画（.smd）",
    "Skinned model + animation (.fbx)": "蒙皮模型与动画（.fbx）",
    "Animated formats (independent folders; select at least one):": "动画输出格式（至少勾选一种，各格式目录独立）：",
    "SMD stores skeletal animation only; use the JSON report for its frame rate.": "SMD 仅保存骨骼动画；帧率记录在 JSON 清单中。",
    "Animation pairs (left | right):": "动画配对队列（左侧 | 右侧）：",
    "Animation queue:": "动画队列：",
    "Batch skinning: DQS (Dual Quaternion).": "批量蒙皮：DQS（双四元数）。",
    "Selected paths:": "选中项完整路径：",
    "Selected paths (left, then right):": "选中项完整路径（先左后右）：",
    "Add Current Pair": "添加当前左右配对",
    "Add Animation Pairs...": "批量添加动画配对…",
    "Add Animations...": "添加多个动画…",
    "Remove Selected": "移除选中项",
    "Clear Queue": "清空队列",
    "Ready": "就绪",
    "Finished": "已完成",
    "Failed": "失败",
    "Cancelled": "已取消",
    "Batch Export Animations": "开始批量导出动画",
    "Cancel After Current Item": "当前项结束后取消",
    "Check every left/right pair in the queue before exporting.": "导出前请检查队列中每一项的左右动画是否匹配。",
    "Select animations": "选择多个动画",
    "Select left animations": "选择多个左侧动画",
    "Select right animations (same order)": "按对应顺序选择右侧动画",
    "CoD Viewmodel Toolkit": "CoD 视角模型工具包",
    "Select": "选择",
    "Save": "保存",
    "Discard": "放弃更改",
    "Cancel": "取消",
    "OK": "确定",
    "Browse...": "浏览…",
    "Close": "关闭",
    "About": "关于",
    "Viewhands:": "手臂文件：",
    "Weapon:": "武器文件：",
    "Left animation:": "左侧动画：",
    "Right animation:": "右侧动画：",
    "Reference pose (optional):": "参考姿态（可选）：",
    "Manifest/default:": "清单/默认目录：",
    "Weapon root:": "武器根骨：",
    "Weapon joint:": "武器关节：",
    "Viewhands tag:": "手臂挂点：",
    "Left target:": "左侧挂点：",
    "Right target:": "右侧挂点：",
    "Animation mode:": "动画模式：",
    "Maya ASCII scene (.ma)": "Maya ASCII 场景（.ma）",
    "Combined model Cast (.cast)": "合并模型 CAST（.cast）",
    "Source model (.smd)": "Source 模型（.smd）",
    "Static model with skinning (.fbx)": "含蒙皮的静态模型（.fbx）",
    "Maya ASCII scene + animation (.ma)": "Maya ASCII 场景与动画（.ma）",
    "Static combined model Cast (.cast)": "静态合并模型 CAST（.cast）",
    "Static Source model (.smd)": "静态 Source 模型（.smd）",
    "Preflight": "预检",
    "Attach && Export": "挂接并导出",
    "Batch Weapons...": "批量处理武器…",
    "Import Animation Safely...": "安全导入动画…",
    "Validate Current": "验证当前结果",
    "Select Attachment": "选择挂接对象",
    "Save Current Result": "保存当前结果",
    "Open Output Folders": "打开输出目录",
    "Preflight Dual": "双持预检",
    "Build + Import Both": "构建并导入双侧动画",
    "Validate Dual": "验证双持结果",
    "Replace Left Clip...": "替换左侧动画…",
    "Replace Right Clip...": "替换右侧动画…",
    "Quick Attach (Single Weapon)...": "快速挂接（单武器）…",
    "Single-Weapon Builder...": "单武器构建器…",
    "Dual-Wield Builder...": "双持构建器…",
    "Auto-Safe Dropped CAST Animations": "自动安全处理拖入的 CAST 动画",
    "Validate Current Attachment": "验证当前挂接",
    "Select Current Attachment": "选择当前挂接",
    "Clear Saved Settings": "清除已保存设置",
    "Starting...": "正在开始…",
    "Safely route pure animation CAST files dropped onto a "
    "CoD Viewmodel Toolkit scene.":
        "安全处理拖入到CoD 视角模型工具包场景中的纯动画 CAST 文件。",
}


_PHRASE_TRANSLATIONS = (
    ("CAST viewmodel assembly, safe animation import, and batch export for Maya.",
     "面向 Maya 的 CAST 第一人称模型装配、安全动画导入与批量导出工具。"),
    ("WORKFLOWS", "主要流程"),
    ("- Single weapon: attach weapon:j_gun to viewhands:tag_weapon;\n"
     "  includes preflight and validation.",
     "- 单武器：将 weapon:j_gun 挂接到 viewhands:tag_weapon；\n"
     "  包含预检和验证。"),
    ("- Dual wield: duplicate one weapon onto tag_weapon_left/right;\n"
     "  compose left/right clips in simultaneous or sequential mode.",
     "- 双持：复制同一个武器到 tag_weapon_left/right；\n"
     "  以同时或顺序模式合成左右动画。"),
    ("- Optional reference-pose compensation corrects compatible weapon-tag\n"
     "  offsets.",
     "- 可选参考姿态补偿可修正兼容资源的武器挂点偏移。"),
    ("- Pure-animation CAST import and drag/drop safely avoid duplicate-joint\n"
     "  conflicts.",
     "- 导入或拖放纯动画 CAST 时，会安全绕过重名关节冲突。"),
    ("ANIMATION & EXPORT", "动画与导出"),
    ("- Queue multiple single clips or explicit left/right dual pairs.",
     "- 可排队多个单武器动画，或明确的左右双持动画配对。"),
    ("- Builders: animated MA scenes plus optional static CAST/SMD/FBX\n"
     "  model outputs.",
     "- 构建器：输出含动画的 MA 场景，以及可选的静态 CAST/SMD/FBX 模型。"),
    ("- Animation batches: animated MA/CAST/FBX and skeletal-animation SMD;\n"
     "  all use DQS skinning.",
     "- 动画批量导出：输出含动画的 MA/CAST/FBX 和仅骨骼动画的 SMD；\n"
     "  统一使用 DQS 蒙皮。"),
    ("- Choose formats and folders independently. Versioned names avoid\n"
     "  overwrites; JSON reports record results.",
     "- 格式与目录可独立选择；版本化命名避免覆盖；\n"
     "  JSON 报告记录每项结果。"),
    ("COMPATIBILITY", "兼容性"),
    ("- Expected: Maya 2022+ in Python 3 mode.\n"
     "  Verified: Maya 2025 for Windows.",
     "- 预期兼容 Maya 2022+ 的 Python 3 模式；\n"
     "  已在 Windows 版 Maya 2025 验证。"),
    ("- Uses an already loaded compatible Cast translator, or the adjacent\n"
     "  patched CAST 2.00 fallback.",
     "- 优先使用已加载的兼容 Cast 转换器；\n"
     "  否则回退到相邻的补丁版 CAST 2.00。"),
    ("DUAL-WIELD SCOPE", "双持范围"),
    ("- Duplicates the same weapon; does not merge two different weapon\n"
     "  skeletons.",
     "- 双持只复制同一个武器；不会合并两套不同的武器骨架。"),
    ("Source and releases:", "源码与发布："),
    ("Single Animation Batch", "单武器动画批量导出"),
    ("Dual Animation Batch", "双持动画批量导出"),
    ("Left and right animation counts must match", "左右动画数量必须一致"),
    ("Add at least one animation to the queue", "请先向队列添加至少一个动画或动画配对"),
    ("Animation queue contains an empty path", "动画队列中存在空路径"),
    ("Finished\nOK:", "已完成\n成功："),
    ("Cancelled\nOK:", "已取消\n成功："),
    ("\nPartial:", "\n部分成功："),
    ("\nFailed:", "\n失败："),
    ("\nReport:", "\n报告："),
    ("About CoD Viewmodel Toolkit", "关于CoD 视角模型工具包"),
    (" - File Browser", " - 文件浏览器"),
    (" - Unsaved Scene", " - 未保存场景"),
    (" - Save Scene", " - 保存场景"),
    (" - Preflight Passed", " - 预检通过"),
    (" - Preflight", " - 预检"),
    (" - Done", " - 完成"),
    (" - Error", " - 错误"),
    (" - Batch Result", " - 批处理结果"),
    (" - Batch Error", " - 批处理错误"),
    (" - Quick Attach", " - 快速挂接"),
    (" - Animation Imported", " - 动画已导入"),
    (" - Animation Error", " - 动画错误"),
    (" - Validation Passed", " - 验证通过"),
    (" - Validation Failed", " - 验证失败"),
    (" - Select Attachment", " - 选择挂接对象"),
    (" - Saved", " - 已保存"),
    (" - Save Result", " - 保存结果"),
    (" - Open Output Folders", " - 打开输出目录"),
    (" - Dual Preflight Passed", " - 双持预检通过"),
    (" - Dual Preflight", " - 双持预检"),
    (" - Dual-Wield Done", " - 双持构建完成"),
    (" - Dual-Wield Error", " - 双持错误"),
    (" - Dual Animation Replaced", " - 双持动画已替换"),
    (" - Replace Dual Animation", " - 替换双持动画"),
    (" - Dual Validation Passed", " - 双持验证通过"),
    (" - Dual Validation Failed", " - 双持验证失败"),
    (" - Dual-Wield Builder", " - 双持构建器"),
    (" - Single Weapon", " - 单武器"),
    ("Failed:\n", "失败：\n"),
    ("The current scene has unsaved changes.", "当前场景包含未保存的更改。"),
    ("The toolkit needs a new scene.", "工具需要新建场景。"),
    ("Save, discard, or cancel?", "请选择保存、放弃更改或取消。"),
    ("Preflight passed without changing the scene.",
     "预检通过，场景未被修改。"),
    ("This dialog builds the single-weapon workflow.",
     "此窗口用于构建单武器场景。"),
    ("Done.", "处理完成。"),
    ("Use Dual-Wield Builder for an Akimbo result.",
     "双持场景请使用双持构建器。"),
    ("Batch complete. One output set was produced per weapon.",
     "批处理完成，每个武器均生成一组输出。"),
    ("Succeeded:", "成功："),
    ("Failed:", "失败："),
    ("Cancelled:", "已取消："),
    ("No valid saved viewhands path.", "没有有效的已保存手臂文件路径。"),
    ("Use Single-Weapon Builder to pick one first.",
     "请先在单武器构建器中选择文件。"),
    ("Saved formats:", "已保存格式："),
    ("Manifest:", "验证清单："),
    ("Animation imported.", "动画已导入。"),
    ("New animation curves:", "新增动画曲线："),
    ("Attachment translation protected:", "已保护挂接位移："),
    ("Use Save Current Result to persist the animation.",
     "请使用“保存当前结果”持久化动画。"),
    ("Parent:", "父对象："),
    ("Translation:", "位移："),
    ("Saved current result:", "当前结果已保存："),
    ("Preflight passed", "预检通过"),
    ("Dual-wield scene built.", "双持场景已构建。"),
    ("Left:", "左侧："),
    ("Right:", "右侧："),
    ("Mode:", "模式："),
    ("Framerate:", "帧率："),
    ("Left frames:", "左侧帧范围："),
    ("Right frames:", "右侧帧范围："),
    ("Orphan nodes: none", "孤立节点：无"),
    ("Differing shared tracks:", "存在差异的共享轨道："),
    ("Reference compensation:", "参考姿态补偿："),
    ("disabled", "未启用"),
    ("Orphan nodes:", "孤立节点："),
    ("Playback:", "播放范围："),
    ("Joints:", "关节数："),
    ("Meshes:", "网格数："),
    ("Left parent:", "左侧父对象："),
    ("Right parent:", "右侧父对象："),
    ("Curves:", "曲线数："),
    ("Frames:", "帧范围："),
    ("Left animation replaced.", "左侧动画已替换。"),
    ("Right animation replaced.", "右侧动画已替换。"),
    ("Duplicates one weapon:", "复制同一个武器："),
    ("Simultaneous mode splits hand branches and uses the right animation "
     "for shared torso/root tracks.",
     "同时播放模式会拆分左右手分支，共享躯干/根骨轨道采用右侧动画。"),
    ("Reference pose compensation shifts relative/additive weapon-tag "
     "translation tracks from the selected reference viewhands rest pose.",
     "参考姿态补偿会依据所选参考手臂的静止姿态，修正武器挂点的相对/叠加位移轨道。"),
    ("Single mode -", "单武器模式 -"),
    ("Use Dual-Wield Builder for Akimbo scenes.",
     "双持场景请使用双持构建器。"),
    ("Protect weapon joint translation when importing animation",
     "导入动画时保护武器关节位移"),
    ("Output formats and folders", "输出格式与目录"),
    ("select at least one", "至少选择一种格式"),
    ("blank folder uses Manifest/default", "目录留空时使用清单/默认目录"),
    ("Cast/SMD/FBX are static model outputs", "Cast/SMD/FBX 为静态模型输出"),
    (".cast/.smd model export uses bundled/compatible Cast v2.00;",
     ".cast/.smd 模型导出使用内置/兼容的 Cast v2.00；"),
    (".fbx excludes animation.", ".fbx 不包含动画。"),
    ("Use saved settings and pick one weapon file.",
     "使用已保存设置并选择一个武器文件。"),
    ("Preflight, attach, batch, save, and validation tools.",
     "提供预检、挂接、批处理、保存和验证功能。"),
    ("Duplicate one weapon and compose left/right Akimbo animations.",
     "复制一个武器并合成左右双持动画。"),
    ("Saved CoD Viewmodel Toolkit settings cleared.",
     "已清除CoD 视角模型工具包的保存设置。"),
    ("Dual mode duplicates one weapon onto tag_weapon_left/right.",
     "双持模式会复制一个武器并挂到 tag_weapon_left/right。"),
    ("It does not combine two different weapon skeletons.",
     "不支持合并两套不同的武器骨架。"),
    ("Optional versioned .ma, .cast, .smd, and static .fbx outputs.",
     "可选输出带版本后缀的 .ma、.cast、.smd 和静态 .fbx。"),
    ("Each format can use an independent output folder.",
     "每种格式均可使用独立输出目录。"),
    ("A JSON verification manifest is always written.",
     "始终会写入 JSON 验证清单。"),
    ("Pure animation CAST drops are safely routed by default.",
     "默认安全处理拖入的纯动画 CAST。"),
    ("Uses Maya's Cast translator for imports.",
     "导入功能使用 Maya Cast 转换器。"),
    ("Select .cast file", "选择 .cast 文件"),
    ("Select one weapon .cast for the single-weapon workflow",
     "为单武器流程选择一个武器 .cast 文件"),
    ("Select .cast animation", "选择 .cast 动画"),
    ("Select replacement left animation", "选择要替换的左侧动画"),
    ("Select replacement right animation", "选择要替换的右侧动画"),
    ("Select weapon .cast files (one output set per weapon)",
     "选择武器 .cast 文件（每个武器生成一组输出）"),
    ("CoD Viewmodel Toolkit", "CoD 视角模型工具包"),
)


def translate_ui_text(value):
    """Translate one user-facing UI value while preserving data values."""
    if not isinstance(value, str):
        return value
    translated = _EXACT_TRANSLATIONS.get(value)
    if translated is not None:
        return translated
    if value.startswith("Select ") and value.endswith(" folder"):
        label = value[len("Select "):-len(" folder")]
        return "选择%s目录" % translate_ui_text(label)
    translated = value
    for source, target in _PHRASE_TRANSLATIONS:
        translated = translated.replace(source, target)
    return translated


def _translate_value(value):
    if isinstance(value, list):
        return [_translate_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_translate_value(item) for item in value)
    return translate_ui_text(value)


class _LocalizedCmdsProxy:
    """Translate selected Maya UI keyword values and forward everything else."""

    _UI_COMMANDS = {
        "button", "checkBox", "confirmDialog", "fileDialog2", "menu",
        "menuItem", "progressWindow", "text", "window", "frameLayout",
        "textField", "textScrollList", "optionMenu",
    }
    _UI_KEYWORDS = {
        "annotation", "button", "cancelButton", "caption", "defaultButton",
        "dismissString", "label", "message", "okCaption", "status", "title",
    }

    def __init__(self, commands):
        self._commands = commands

    def __getattr__(self, name):
        command = getattr(self._commands, name)
        if name not in self._UI_COMMANDS:
            return command

        def localized_command(*args, **kwargs):
            localized = dict(kwargs)
            response_map = {}
            if name == "confirmDialog":
                for original in kwargs.get("button", []) or []:
                    response_map[translate_ui_text(original)] = original
            for key in self._UI_KEYWORDS.intersection(localized):
                localized[key] = _translate_value(localized[key])
            result = command(*args, **localized)
            if name == "confirmDialog":
                return response_map.get(result, result)
            return result

        return localized_command


def _load_core():
    if not os.path.isfile(_CORE_PATH):
        raise ImportError("中文版入口旁缺少 viewmodel_weapon_toolkit.py")
    spec = importlib.util.spec_from_file_location(_CORE_MODULE_NAME, _CORE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError("无法加载 %s" % _CORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.VERSION != VERSION:
        raise RuntimeError(
            "中文版入口与核心版本不一致：%s != %s" % (VERSION, module.VERSION))
    module.cmds = _LocalizedCmdsProxy(_maya_cmds)
    module._zh_cn_entry_version = VERSION
    module._zh_cn_translate_ui_text = translate_ui_text
    return module


_implementation = _load_core()


def initializePlugin(m_object):
    """Register the shared implementation with a Simplified Chinese UI."""
    for plugin_name in ("viewmodel_weapon_toolkit", "attach_gun"):
        try:
            loaded = _maya_cmds.pluginInfo(
                plugin_name, query=True, loaded=True)
        except Exception:
            loaded = False
        if loaded:
            raise RuntimeError(
                "请先卸载英文版插件 %s；英文版与中文版不能同时加载。"
                % plugin_name)
    _implementation.initializePlugin(m_object)


def uninitializePlugin(m_object):
    """Unregister the shared implementation."""
    _implementation.uninitializePlugin(m_object)
