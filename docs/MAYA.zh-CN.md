# Maya 使用说明 — CoD Viewmodel Toolkit

[项目首页](../README.zh-CN.md) · [English](MAYA.md)

## 运行要求

- Autodesk Maya 2022 或更高版本，并须使用 Python 3 模式。Maya 2022
  自带的 Python 3.7.7 是最低支持的 Python 运行时。
- Windows 是目前已验证的操作系统。**打开输出目录** 使用 Windows 专用的
  `os.startfile`；核心 Maya 工作流尚未在 macOS 或 Linux 上完成认证。
- Release 压缩包已包含基于
  [dtzxporter/cast v2.01](https://github.com/dtzxporter/cast/releases/tag/v2.01)
  的项目补丁版 Maya 转换器，从压缩包安装时无需另行下载 CAST。
- 骨骼命名符合下文约定的 CAST 文件。

内置转换器派生自独立的 MIT 开源项目，并非官方原版。其准确上游基线、文件
哈希及本地修改见
[`third_party/cast/PATCHES.md`](../third_party/cast/PATCHES.md)。

## 安装

1. 升级前保存场景、关闭 Maya 并备份工具包文件。保留独立安装的
   `castplugin.py`、`cast.py` 和 `cast.cfg`；工具包不再覆盖这些文件。
2. 选择一个 Release 版本，把其中 `plug-ins` 的全部文件和子目录复制到 Maya
   的 `MAYA_PLUG_IN_PATH` 目录。两个版本均包含 `cod_viewmodel_cast_backend.py`、
   `cod_viewmodel_cast/{cast.py,castplugin.py}`、`cod_viewmodel_units.py` 及工具包入口：
   - 英文版：`viewmodel_weapon_toolkit.py`。
   - 简体中文版：同时复制 `viewmodel_weapon_toolkit.py` 和
     `viewmodel_weapon_toolkit_zh_CN.py`；前者是共享核心。
3. 英文版从 Attach Gun 升级时可以同时复制 `plug-ins/attach_gun.py`。
   如使用中文版，请在插件管理器中关闭旧 `attach_gun.py` 和英文主入口的
   自动加载，只启用中文入口。
4. 英文版在 Maya 插件管理器中加载 `viewmodel_weapon_toolkit.py`；简体
   中文版加载 `viewmodel_weapon_toolkit_zh_CN.py`。
5. 从 Maya 主菜单打开 **CoD Viewmodel Toolkit**（英文版）或
   **CoD 视角模型工具包**（中文版）。

源码仓库可直接加载 `plug-ins` 下的所选入口，后端会自动找到 `third_party/cast`，
无需把其中的文件复制到入口旁。Release 安装时请保留完整的 `cod_viewmodel_cast`
目录，不要把其中的 `castplugin.py` 当作独立 Maya 插件加载。

插件同时注册新命令 `viewmodelWeaponToolkit` 和兼容命令 `attachGun`。
英文版、中文版和旧入口注册相同命令，因此只能为其中一个版本启用自动加载。

### 私有 CAST 后端

工具包注册 `CoDToolkitCast`，与外部插件的 `Cast` 转换器分开。无论外部 CAST
何时加载，工具包都使用内置实现。界面与批处理共用同一后端；每次操作的选项和
运行设置都会在成功或失败后恢复，不读取或改写个人 `cast.cfg`。

单武器与双持动画通过明确的完整 DAG 路径匹配，不再临时改名场景关节。已有组装
持久名称（包括双持 `akimbo_l_`／`akimbo_r_` 前缀）不变。节点、静止变换和曲线查找
缓存以每段动画为边界。单武器动画拖放回归实测物理解析从 4 次降为 1 次；下一次
操作仍重新读取文件，当前读取会话中的文件变更也会使缓存失效。

CAST 2.01 修复变换组下骨架导出的父索引。本项目另修复多条曲线模式覆盖只处理
最后一条的问题，保留平移、旋转、缩放各自的启用标志。这些属于正确性修复，
不计作性能收益。详见 [3.5.0 更新说明](RELEASE_NOTES_3.5.0.md)、
[后端研究](CAST_BACKEND_RESEARCH.md)和[测量记录](CAST_BACKEND_BENCHMARK.md)。

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

### 可选参考姿态补偿

部分动画 CAST 的 `relative` 或 `additive` 位移轨道是针对另一套手臂静止姿态
制作的。如果武器能够播放动画但始终偏离某只手，请在 **参考姿态（可选）**
中选择与动画兼容的手臂模型。工具会计算当前与参考模型
`tag_weapon_left/right` 的本地静止位移差，只平移受影响的相对/叠加动画曲线；
绝对轨道、旋转、武器根骨和蒙皮绑定不会改变。

留空时保持旧版行为。当前模型和参考模型中的目标挂点必须具有相同名称的
父关节。补偿数值与参考文件路径会写入场景元数据和验证清单，替换单侧动画
时也会自动复用。

## 输出说明

原有构建器保持原行为：`.ma` 保存场景与动画，`.cast`、`.smd`、`.fbx` 输出静态模型。
新增的 **单武器动画批量导出** 和 **双持动画批量导出** 则为每个勾选的格式输出动画：

| 格式 | 批量导出的内容 |
| --- | --- |
| MA | 完整 Maya 场景、蒙皮与动画 |
| CAST | 合并模型与烘焙后的骨骼动画 |
| FBX | 蒙皮模型与烘焙动画 |
| SMD | 仅骨骼动画，不含网格；片段起点记为第 0 帧 |

单武器和双持批量流程统一使用 **DQS（双四元数蒙皮）**。MA、FBX 保留 Maya
蒙皮类型；CAST 写入 `quaternion` 标记，将装配后的原始静止模型与逐帧采样动画
组合保存，避免将动画首帧误当成绑定姿态。导出采样不会替换工作场景中的原始
动画曲线；本功能不修改本机或内置的 CAST 插件文件。

SMD v1 不保存帧率、缩放或剪切。帧率写入 JSON 清单，目标软件需据此设置。
如关节包含非单位缩放或剪切，该 SMD 输出会明确报错，但不影响其他勾选格式。
SMD 位移采用厘米，旋转采用 XYZ 欧拉角、弧度单位。

四种格式均可关闭，也可以分别指定输出目录。工具不会覆盖已有文件，而是
自动追加 `_v001` 一类版本后缀。

挂载成功仍不弹完成提示；错误、部分格式导出失败和未保存场景提示继续保留。

## 动画批量导出

1. 从工具包菜单或对应构建器打开 **单武器动画批量导出** 或 **双持动画批量导出**。
2. 选择一份手臂和一份武器模型。双持可选择同时/顺序模式，并沿用可选参考姿态补偿。
3. 单武器使用 **添加多个动画**。双持选择左右路径后点击 **添加当前左右配对**；
   也可使用 **批量添加动画配对**，按对应顺序分别多选相同数量的左右文件。
   导出前检查队列中显示的每一对完整路径。
4. 独立勾选 MA、CAST、SMD、FBX，至少一种。各自目录可选，留空使用清单/默认目录。
5. 点击 **开始批量导出动画**。每项使用干净场景；**当前项结束后取消** 会在本项
   完成后停止剩余队列。运行前如有未保存场景，会提示保存。

每项采用其导入动画的帧区间和帧率；双持每对左右动画的帧率必须一致。
输出名采用动画文件名（双持采用左动画名）和统一版本后缀。重复队列项自动去重，
不同路径但同名的动画使用不同版本，不覆盖文件。单项或单格式失败会记录原因，
随后继续处理。批次 JSON 报告汇总成功路径、失败原因与取消状态。

Python 接口：`batch_export_animations(hands, weapon, animation_paths, options)` 和
`batch_export_dual_animations(hands, weapon, [(left, right), ...], options)`，分别使用
`AttachOptions` 和 `DualWieldOptions`。四种格式开关及目录字段沿用现有配置；
接口返回批次汇总字典，不改变原有构建器的静态导出默认行为。

## 已知源数据警告

部分动画包含 `j_gripsafety` 轨道，但模型中不存在该关节。工具会报告并跳过
该孤立轨道，其余动画仍可正常导入。

## 兼容性

| 支持级别 | 环境 | 状态 |
| --- | --- | --- |
| 预期最低版本 | Maya 2022、Python 3.7.7、私有补丁版 CAST 2.01 | Python 3.7 语法与 API 兼容性目标；未在 Maya 2022 执行完整宿主回归。 |
| 当前验证版本 | Maya 2027、Python 3.13.9、私有补丁版 CAST 2.01、Windows | 3.5.0 后端身份、父索引、目标路由和操作生命周期回归在此环境运行；已完成项目见更新说明。 |
| 历史验证版本 | Maya 2025、Python 3.11.4、此前内置 CAST 版本、Windows | 旧版验证过单武器、双持、中文界面和导出；3.5.0 未在此版本重新测试。 |

Windows 或 Linux 版 Maya 2022 也可以用 Python 2 模式启动；本工具包必须在
Python 3 模式下运行。Maya 2021 及更早版本不受支持。最低版本结论来自代码
语法与 API 兼容性判断，不代表已在 Maya 2022 中运行完整资产回归。

自 3.3.0 起保留旧文件名入口、`attachGun` 命令、OptionVar 和双持场景元数据，原有
场景与 Maya 偏好可以继续使用。

## 测试

可使用 Maya Python 运行发布入口和中文本地化测试：

```powershell
python tests/verify_vendored_cast.py
mayapy tests/verify_plugin_identity.py
mayapy tests/verify_reference_pose_compensation.py
mayapy tests/verify_batch_animation_export.py
mayapy tests/verify_cast_v200.py
mayapy tests/verify_cast_v201.py
mayapy tests/verify_private_cast_backend.py
mayapy tests/verify_animation_read_session.py
mayapy tests/verify_maya_drop_module_path.py
```

批量回归会自动生成合成 CAST 样本，检查双持两种播放模式、四种输出及 FBX
重新导入后的逐帧结果。公开仓库不包含游戏资产。
具体覆盖范围见[批量导出验证记录](BATCH_ANIMATION_VERIFICATION.md)。
本版检查见 [3.5.0 更新说明](RELEASE_NOTES_3.5.0.md)和
[后端测量记录](CAST_BACKEND_BENCHMARK.md)；CAST 2.00 与原生界面历史检查见
[3.2.0 验证记录](VERIFICATION_3.2.0.md)。

使用 `python scripts/build_release.py <output-dir>` 构建四个平台／语言安装包。

## 许可证

本项目使用 MIT License。详见 [LICENSE](../LICENSE) 和
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。
