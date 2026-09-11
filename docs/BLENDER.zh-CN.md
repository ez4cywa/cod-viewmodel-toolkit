# Blender — CoD Viewmodel Toolkit 3.3.0

[English](BLENDER.md) · [项目首页](../README.zh-CN.md)

要求 Blender 5.2+，已在 Windows 官方 Blender 5.2.1 LTS 中验证。当前侧栏为
英文，不依赖 Maya。发布包不包含游戏素材、Blender 程序或 Maya 运行环境。

## 安装与使用

1. 下载 `cod-viewmodel-toolkit-3.3.0-blender-en.zip`。
2. 在 Blender 的 Edit > Preferences > Add-ons 菜单选择 Install from Disk，
   安装 ZIP，并启用 **CoD Viewmodel Toolkit**。
3. 在 3D 视图按 `N`，打开 **Viewmodel** 标签。
4. 选择 Single Weapon（单武器）或 Dual Wield（双持），指定 Viewhands CAST
   和 Weapon CAST。模型输入必须仅含一个骨骼模型；动画文件单独选择。
5. Check Inputs 只做检查；Build Assembly 创建新的组装集合，不清空原场景。
6. 设置 Default Output、输出格式与可选独立目录，再导出选中的工具包骨架。

武器必须以 `j_gun` 为唯一根骨。手臂需有 `tag_weapon`，双持需有
`tag_weapon_left` 和 `tag_weapon_right`，可在 Joint Mapping 中修改名称。
武器骨骼先添加隔离前缀，再合并至同一个骨架；根骨对齐挂点、建立父子关系，
位移归零。共享 `j_gun` 动画归手臂所有，不会错误驱动附加武器根骨。

双持是复制同一武器，不合并两种不相干骨架。左右分支按 `_le`/`_left`、
`_ri`/`_right` 名称及其子骨识别。Simultaneous 同时播放，共享根／躯干轨道
采用右动画；Sequential 在左动画结束后播放右动画，各侧在自身区间外保持
首／末姿势。左右帧率必须一致，输出逐整数帧烘焙为一个 Action。

选中工具包骨架后，可应用新动画，或 Replace Left / Replace Right 单侧替换，
无需重建模型。另一侧会读取原动画路径，需保留源文件。Reference Viewhands
仅补偿匹配挂点的 relative/additive 位移轴，不改变 absolute 轴；参考挂点
父骨须与当前模型一致。

## 导出与批量

- `.blend`：仅组装体场景，含动画和 DQS，不是整个工作区快照。打开时可能
  显示 Library file 提示，导出内容位于 `CoD Viewmodel` 场景。
- `.cast`：模型及骨骼动画，使用项目补丁版 CAST 2.00。组合文件往返测试使用
  本包私有后端；另装的原版 CAST 可能表现不同。
- `.fbx`：骨架、网格及烘焙动画。接收软件必须启用 **Dual Quaternion／
  Preserve Volume（双四元数／保持体积）**；Blender 默认 FBX 导入为线性蒙皮。
  在 Blender 逐帧比较时，将导入的动画偏移设为 `0`。
- `.smd`：有动画时只导出骨骼动画；无动画的组装体导出静态蒙皮三角网格。
  SMD 不表示骨骼缩放或 DQS。

每种格式可以指定独立目录，留空则继承 Default Output；文件用 `_001` 等
递增后缀避免覆盖。JSON 报告记录输入、挂接检查、警告和结果路径。

Animation Batch 可加入多个单动画或明确的左右配对，逐项处理，失败后继续。
Escape 或 Stop After Current 会在当前项完成后停止，保留已有结果。
单次大文件导入／导出可能暂时阻塞界面，不能在调用中途取消。每项结束后
恢复原场景时间范围、帧率与选择，只清理该项创建的对象。

## 已知范围

本版合成骨骼动画，跳过并报告 blend-shape 动画；模型 shape keys 会导入。
此流程关闭 CAST IK、约束和毛发。纹理仍为外部引用，不自动打包全部图片。
没有匹配骨骼的轨道会跳过并报告，完全不匹配的动画会失败。

已使用真实单武器素材和合成双持夹具验证，尚未用真实左右双动画配对验证。
不同使命召唤作品、骨架与提取器需以具体数据为准。内置私有 CAST 不注册全局
CAST 导入／导出命令，可以与另装的 CAST 插件共存。

Python API 示例见 [英文说明](BLENDER.md#python-api)，测试范围见
[3.3.0 验证记录](VERIFICATION_3.3.0.md)。
