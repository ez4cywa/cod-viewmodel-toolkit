# Maya Viewmodel Weapon Toolkit

[English](README.md)

Maya Viewmodel Weapon Toolkit 3.0.2 是面向 Maya 2022 或更高版本、并须以
Python 3 模式运行的第一人称武器装配与动画工具。它可导入 CAST 手臂和武器
模型，支持单武器、同一武器复制双持、左右动画合成与替换、安全拖放动画、
结构验证及多格式输出。本版本已在 Windows 版 Maya 2025 中完成验证。

## 主要功能

- 将武器文件中的 `j_gun` 挂到手臂文件的 `tag_weapon`。
- 将同一武器复制两份，分别挂到 `tag_weapon_left` 和
  `tag_weapon_right`。
- 让左右双持动画在同一帧区间同时播放。
- 提供顺序播放模式，便于前后对比两段完整动画。
- 在已生成的双持场景中只替换左侧或右侧动画。
- 即使 CAST 全局启用了 **Import Resets Scene**，工具包管理的动画导入也会
  保留场景中的已有动画。
- 安全处理重名关节，拖入纯动画 CAST 时不会错误驱动武器根骨。
- 可独立选择是否输出 `.ma`、`.cast`、`.smd`、`.fbx`。
- 每种格式可选择不同输出目录，并自动生成 JSON 验证清单。
- 发布包内置基于上游 v1.99 的项目补丁版 CAST Maya 转换器，包含 Batch
  模式、单次调用选项和缺失 UV 导出修复。
- 发布包同时提供英文版和简体中文版；两个版本复用同一套核心逻辑。

## 运行要求

- Autodesk Maya 2022 或更高版本，并须使用 Python 3 模式。Maya 2022
  自带的 Python 3.7.7 是最低支持的 Python 运行时。
- Windows 是目前已验证的操作系统。**打开输出目录** 使用 Windows 专用的
  `os.startfile`；核心 Maya 工作流尚未在 macOS 或 Linux 上完成认证。
- Release 压缩包已包含基于
  [dtzxporter/cast v1.99](https://github.com/dtzxporter/cast/releases/tag/v1.99)
  的项目补丁版 Maya 转换器，从压缩包安装时无需另行下载 CAST。
- 骨骼命名符合下文约定的 CAST 文件。

内置转换器派生自独立的 MIT 开源项目，并非官方原版。其准确上游基线、文件
哈希及本地修改见
[`third_party/cast/PATCHES.md`](third_party/cast/PATCHES.md)。

## 安装

1. 备份目标 Maya 插件目录中已有的 `castplugin.py` 和 `cast.py`。不要复制
   或覆盖 `cast.cfg`，其中保存了个人 CAST 设置。
2. 选择一个 Release 版本，把其中 `plug-ins` 目录的全部文件复制到 Maya
   的 `MAYA_PLUG_IN_PATH` 目录。两个版本均包含补丁版 CAST 1.99：
   - 英文版：`viewmodel_weapon_toolkit.py`。
   - 简体中文版：同时复制 `viewmodel_weapon_toolkit.py` 和
     `viewmodel_weapon_toolkit_zh_CN.py`；前者是共享核心。
3. 英文版从 Attach Gun 升级时可以同时复制 `plug-ins/attach_gun.py`。
   如使用中文版，请在插件管理器中关闭旧 `attach_gun.py` 和英文主入口的
   自动加载，只启用中文入口。
4. 英文版在 Maya 插件管理器中加载 `viewmodel_weapon_toolkit.py`；简体
   中文版加载 `viewmodel_weapon_toolkit_zh_CN.py`。
5. 从 Maya 主菜单打开 **Viewmodel Weapon Toolkit**（英文版）或
   **视角模型武器工具包**（中文版）。

如果使用源码仓库，请将 `third_party/cast/cast.py` 和
`third_party/cast/castplugin.py` 与所选工具包入口文件放在同一插件目录。

插件同时注册新命令 `viewmodelWeaponToolkit` 和兼容命令 `attachGun`。
英文版、中文版和旧入口注册相同命令，因此只能为其中一个版本启用自动加载。

## 骨骼约定

### 单武器

- `j_gun` 来自武器文件。
- `tag_weapon` 来自手臂文件。
- 插件先使用 `cmds.parent(..., absolute=True)` 挂接武器，再将 `j_gun`
  的本地 XYZ 位移设为零。
- 不会冻结关节变换。

### 双持

- `tag_weapon_left` 和 `tag_weapon_right` 来自手臂文件。
- 同一个武器模型导入两次，分别使用持久化前缀 `akimbo_l_` 和
  `akimbo_r_`。
- 左动画驱动左手分支和左武器；右动画驱动右手分支和右武器。
- 同时模式中，共享的躯干/根骨轨道默认采用右侧动画；顺序模式会将两段
  完整动画放到连续的时间区间。

双持功能只适用于同一武器骨架的两个副本，不支持两套不同或不对称的武器
骨架。

## 输出说明

`.ma` 是保留完整动画的权威输出。`.cast`、`.smd`、`.fbx` 当前作为合并后
的静态模型交换格式，不应替代动画 Maya 场景。

四种格式均可关闭，也可以分别指定输出目录。工具不会覆盖已有文件，而是
自动追加 `_v001` 一类版本后缀。

## 已知源数据警告

部分动画包含 `j_gripsafety` 轨道，但模型中不存在该关节。工具会报告并跳过
该孤立轨道，其余动画仍可正常导入。

## 兼容性

| 支持级别 | 环境 | 状态 |
| --- | --- | --- |
| 预期最低版本 | Maya 2022、Python 3.7.7、补丁版 CAST 1.99 | 源码语法和所需 Maya API 兼容；尚未在 Maya 2022 中执行基于实际资产的完整回归。 |
| 发布验证版本 | Maya 2025、Python 3.11.4、补丁版 CAST 1.99、Windows | 单武器、双持、中文界面和导出的发布验证目标。 |

Windows 或 Linux 版 Maya 2022 也可以用 Python 2 模式启动；本工具包必须在
Python 3 模式下运行。Maya 2021 及更早版本不受支持。最低版本结论来自代码
语法与 API 兼容性判断，不代表已在 Maya 2022 中运行完整资产回归。

3.0.2 保留旧文件名入口、`attachGun` 命令、OptionVar 和双持场景元数据，原有
场景与 Maya 偏好可以继续使用。

## 测试

可使用 Maya Python 运行发布入口和中文本地化测试：

```powershell
python tests/verify_vendored_cast.py
mayapy tests/verify_plugin_identity.py
```

完整动画回归需要用户自备合法 CAST 资源，因此不会包含在公开仓库中。

## 许可证

本项目使用 MIT License。详见 [LICENSE](LICENSE) 和
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
