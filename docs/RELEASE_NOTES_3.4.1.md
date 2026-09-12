# CoD Viewmodel Toolkit 3.4.1 — Maya animation import fix

## 简体中文

修复 Maya 拖入 CAST 动画时出现 `NameError: name '__file__' is not defined`，
导致动画导入中止的问题。Maya 注册插件时可能不提供 `__file__`；单位模块现在
通过插件已记录的实际安装路径定位，不再依赖该变量。

覆盖单武器动画拖放以及双持左右动画替换。该修复不修改骨骼挂点偏移：
需要保持零平移的是武器 `j_gun`，而不是手臂的 `tag_weapon`。

提供 Maya 英文、Maya 简体中文、Blender 英文、Blender 简体中文四个安装包。
Blender 仅同步版本号，功能与 3.4.0 一致。

更新 Maya 前保存当前场景，关闭 Maya 后，用所选语言包中的插件文件更新原安装目录，
再重新打开 Maya。不要把不同版本的核心文件和单位模块混用。

## English

Fix CAST animation drops failing with `NameError: name '__file__' is not defined`
in Maya's registered plugin environment. The units module now resolves from the
recorded plugin installation path instead of assuming Python supplies `__file__`.

Regression coverage exercises single-weapon drops and both dual-wield sides in
the actual Maya-loaded implementation, without importing a second core module.
The patch does not zero the hand rig's `tag_weapon` mount offset or alter joint
parenting. Weapon `j_gun` translation remains protected.

All four platform/language packages are included. Blender functionality is
unchanged from 3.4.0; its package version is synchronized only.

Save the current scene and close Maya before replacing installed plugin files
with the selected language package. Reopen Maya after updating the complete set.

[Verification](https://github.com/ez4cywa/cod-viewmodel-toolkit/blob/3.4.1/docs/VERIFICATION_3.4.1.md)
