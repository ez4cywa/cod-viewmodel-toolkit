"""Build-time UI localization; identifiers, backend and user data stay intact."""
import ast
import io
import tokenize

TEXT = {
    "CoD Viewmodel Toolkit": "CoD 视角模型工具包（简体中文）",
    "CoD Viewmodel Toolkit 3.4.1": "CoD 视角模型工具包 3.4.1",
    "CAST single/dual weapon assembly and animation batch exports": "CAST 单武器／双持组装与动画批量导出",
    "Animation / Left": "动画／左侧动画",
    "Right Animation": "右侧动画",
    "Setup": "组装模式",
    "Single Weapon": "单武器",
    "Attach one weapon": "挂接一把武器",
    "Dual Wield": "双持",
    "Duplicate the same weapon for left and right hands": "复制同一武器，分别挂接左右手",
    "Viewhands CAST": "手臂模型 CAST",
    "CoD viewhands model, including the weapon attachment tags": "包含武器挂接节点的 CoD 第一人称手臂模型",
    "Weapon CAST": "武器模型 CAST",
    "One CoD weapon model; dual wield imports it twice": "一份 CoD 武器模型；双持模式会导入两次",
    "Optional single animation or left-hand animation": "可选的单武器动画或左侧动画",
    "Right-hand animation; required with a left clip in Dual Wield": "右侧动画；双持播放时需与左侧动画配对",
    "Weapon Root": "武器根骨骼",
    "Viewhands Tag": "手臂挂接节点",
    "Left Tag": "左侧挂接节点",
    "Right Tag": "右侧挂接节点",
    "Reference Viewhands": "参考手臂模型",
    "Optional compatible rest pose for relative/additive tag translation": "可选的兼容参考静止姿态，用于补偿相对／叠加挂接位移",
    "Playback": "播放方式",
    "Simultaneous": "同时播放",
    "Both sides play together; shared hand/root tracks use the right clip": "左右同时播放；共用手臂／根骨骼轨道使用右侧动画",
    "Sequential": "顺序播放",
    "Right clip starts after the left; each side holds its end pose": "左侧结束后播放右侧；各侧保持结束姿态",
    "Default Output": "默认输出目录",
    "Output Unit": "输出单位",
    "Keep Original": "保持原单位",
    "Do not convert output dimensions": "不转换输出尺寸",
    "Meters (Input: ft)": "米（输入：ft）",
    "Convert an export copy: 1 ft = 0.3048 m; keep the source scene unchanged": "仅转换导出副本：1 ft = 0.3048 m；不修改当前场景",
    "Blender Scene (.blend)": "Blender 场景 (.blend)",
    "CAST Model + Animation": "CAST 模型与动画",
    "FBX Model + Animation": "FBX 模型与动画",
    "Source SMD": "Source 模型／动画 (.smd)",
    "BLEND Folder": "BLEND 目录",
    "CAST Folder": "CAST 目录",
    "FBX Folder": "FBX 目录",
    "SMD Folder": "SMD 目录",
    "Status": "状态",
    "Ready": "就绪",
    "Last Report": "最近报告",
    "Check Inputs": "检查输入",
    "Check models, joints and animation compatibility without changing the scene": "检查模型、骨骼与动画兼容性，不修改场景",
    "Inputs OK: %d hand bones, %d weapon bones": "输入检查通过：手臂 %d 根骨骼，武器 %d 根骨骼",
    "Build Assembly": "组装模型",
    "Import hands then weapon into a new collection, attach at tag origins and apply optional animation": "先导入手臂，再导入武器到新集合；在节点原点挂接并应用所选动画",
    "Built %s; attachment translation verified": "已组装 %s；挂接位移验证通过",
    "Apply Animation to Selected": "为选中组装体应用动画",
    "Apply the animation fields to the selected toolkit rig without rebuilding its meshes": "将动画应用到选中的工具组装体，不重建网格",
    "Animation applied; models preserved": "已应用动画；模型保持不变",
    "Replace Side Animation": "替换单侧动画",
    "Replace one side of the selected dual rig; keep the opposite clip and both models": "替换选中双持组装体的一侧动画，保留另一侧动画和两份模型",
    "Left": "左侧",
    "Left clip": "左侧动画",
    "Right": "右侧",
    "Right clip": "右侧动画",
    " clip replaced": "侧动画已替换",
    "Export Selected Assembly": "导出选中组装体",
    "Export only the selected toolkit assembly, using versioned filenames and a JSON report": "仅导出选中的组装体；使用递增文件名并生成 JSON 报告",
    "Exported %d formats; report saved": "已导出 %d 种格式；报告已保存",
    "Add Animation Files": "添加动画文件",
    "Select one or more CAST animation files for the single-weapon queue": "选择一份或多份 CAST 动画加入单武器队列",
    "Edit Animation Queue": "编辑动画队列",
    "Add the current clip/pair, remove the selected row, or clear the queue": "添加当前动画／配对，移除选中项或清空队列",
    "Add Current": "添加当前项",
    "Add current animation fields": "将当前动画加入队列",
    "Remove": "移除",
    "Remove selected row": "移除选中项",
    "Clear": "清空",
    "Clear queue": "清空队列",
    "Select an animation, or both sides of a dual pair": "请选择动画；双持需同时选择左右两侧动画",
    "Start Batch Export": "开始批量导出",
    "Export each queue item in isolation; failed items are reported and the queue continues": "逐项独立导出；失败项记入报告，队列继续执行",
    "Queue rows must match Single Weapon or Dual Wield mode": "队列条目必须与单武器／双持模式一致",
    "Starting batch...": "正在启动批量导出…",
    "%s: %d completed, %d failed": "%s：已处理 %d 项，失败 %d 项",
    "Stopped": "已停止",
    "Batch finished": "批量导出完成",
    "Stop After Current": "完成当前项后停止",
    "Stop the queue after the current item finishes; completed files are preserved": "完成当前项后停止队列；保留已导出的文件",
    "Left Animation": "左侧动画",
    "Animation (Optional)": "动画（可选）",
    "Creates a new collection. Existing scene objects are preserved.": "新建集合，保留场景中的已有对象。",
    "Joint Mapping & Reference Pose": "骨骼映射与参考姿态",
    "Output Files": "输出文件",
    "Unit": "单位",
    "Export copy only: 1 ft = 0.3048 m. Already-metric assemblies are not scaled again.": "仅转换导出副本：1 ft = 0.3048 m。米制组装体不会重复缩放。",
    "Folder": "目录",
    "Blank format folders use Default Output. Animated SMD contains bones only.": "目录留空则使用默认目录；动画 SMD 仅含骨骼。",
    "FBX: enable Dual Quaternion / Preserve Volume skinning in the receiving app.": "FBX：请在接收软件中启用双四元数／保持体积蒙皮。",
    "Animation Batch": "动画批量导出",
    "Add Current Pair": "添加当前左右配对",
    "Add Current Animation": "添加当前动画",
    "Queue is empty. Add animation files or an explicit left/right pair.": "队列为空。请添加动画文件或明确的左右动画配对。",
    "Batch progress": "批量进度",
    "Open Last Report": "打开最近报告",
    "Selected Assembly": "选中组装体",
    "Replace Left": "替换左侧",
    "Replace Right": "替换右侧",
    "Stop the batch before disabling CoD Viewmodel Toolkit": "请先停止批量导出，再禁用 CoD 视角模型工具包",
}


def localize(source, filename):
    """Replace complete string tokens only, never substrings in identifiers."""
    result = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING:
            value = ast.literal_eval(token.string)
            if value in TEXT:
                token = token._replace(string=repr(TEXT[value]))
        result.append(token)
    source = tokenize.untokenize(result)
    if filename == "ui.py":
        # CJK glyphs occupy about twice the width of the Latin UI font.
        source = source.replace("width = max(22,", "width = max(11,").replace(
            "(7 * context.preferences.system.ui_scale)", "(14 * context.preferences.system.ui_scale)")
        source = source.replace("self.side.title() +", "('左' if self.side == 'left' else '右') +")
        source = source.replace('result["status"])', '{"ok": "成功", "failed": "失败"}.get(result["status"], result["status"]))')
    compile(source, filename, "exec")
    return source.encode("utf-8")
