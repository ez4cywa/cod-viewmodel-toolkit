# 3.5.0 — Private CAST 2.01 integration

Maya now consistently uses the toolkit's own CAST backend, with operation-local
animation parsing and explicit target routing. Existing attachment rules,
output formats, skinning behavior and English/Chinese/legacy entry points remain
unchanged. Blender retains its patched CAST 2.00 implementation; its package
version is synchronized, with no import/export algorithm changes.

## 改进内容

1. **固定内置后端。** 工具包注册独立的 `CoDToolkitCast`，不再根据已加载的外部
   CAST 选择实现。独立安装的 `cast.py`、`castplugin.py` 和 `cast.cfg` 可以保留。
   界面与批处理使用同一实现，每操作设置在成功或异常后恢复，不改写个人配置。
2. **减少动画重复解析。** 单武器动画拖放回归测得物理 `Cast.load` 从 4 次降为
   1 次，全量关键帧时间查询从 2 次降为 1 次。解析结果仅在当前操作内复用；
   文件变更会使缓存失效，下一次操作重新读取。
3. **明确动画目标。** 单武器、双持与单侧替换使用完整 DAG 路径，不再为匹配轨道
   临时改名关节。每段动画独立缓存节点、静止变换及曲线查找，保留绝对、相对、叠加
   轨道语义。双持组装原有持久前缀保持不变。
4. **合并正确性修复。** 基于上游
   [CAST 2.01](https://github.com/dtzxporter/cast/releases/tag/v2.01)，保留原有十项
   项目补丁，合并[骨架导出父索引修复](https://github.com/dtzxporter/cast/commit/02a759082b22e278ba8cc2aff4df9169bdfb2195)。
   另修复多条曲线模式覆盖只考虑最后一条的问题，分别尊重平移、旋转和缩放标志。

原有武器 `j_gun` 挂载到手臂 `tag_weapon`、局部平移归零且不冻结关节的规则不变。
动画导出的 DQS 行为、文件不覆盖规则、错误弹窗及未保存场景提示不变；挂载成功仍
不弹完成提示。没有通过丢弃网格通道、材质或蒙皮数据来换取速度。

## 安装与升级

保存场景并关闭 Maya，备份旧工具包后，复制对应语言 ZIP 的完整 `plug-ins`
内容，包括子目录。新版运行文件布局为：

```text
plug-ins/
  viewmodel_weapon_toolkit.py
  viewmodel_weapon_toolkit_zh_CN.py   # Chinese edition
  attach_gun.py                      # legacy entry
  cod_viewmodel_units.py
  cod_viewmodel_cast_backend.py
  cod_viewmodel_cast/
    cast.py
    castplugin.py
```

不再把 `cast.py` / `castplugin.py` 放在插件目录顶层。不要覆盖或删除用户独立安装
的同名文件，也不要覆盖 `cast.cfg`。只加载一个工具包入口，不要单独加载私有目录
中的 `castplugin.py`。源码仓库可直接加载 `plug-ins` 下的入口，无需复制 `third_party`。
具体操作见 [Maya 中文指南](MAYA.zh-CN.md) / [English guide](MAYA.md)。

## 验证范围与性能

本轮宿主测试使用 Windows Maya 2027 / Python 3.13.9。Maya 2025 的既有验证属于
历史记录，本版未重新运行；Maya 2022 / Python 3.7 仍是兼容性目标，不代表已在
Maya 2022 完成实际宿主回归。Blender 算法本轮未改动；中英文 ZIP 在 Windows
Blender 5.2.1 LTS 的隔离配置中通过安装、组装、动画和米制导出测试。

已覆盖的新增回归包括：

- 私有后端身份、操作设置隔离及外部 CAST 共存。
- 变换组下骨架导出父索引；原实现的最小夹具会把子骨骼父索引错误写成 `-1`。
- 绝对、相对和叠加目标映射，含四元数、已有叠加关键帧、跳过目标与普通名称回退。
- 多条祖先覆盖和通道标志、blendshape 目标隔离、逐片段缓存刷新、嵌套与异常恢复。
- 单次动画拖放解析计数、重复操作重新读取及文件变更后导入新内容。
- 原始 standalone 插件加载兼容性，配置文件检查仅使用临时目录副本。
- 初始化失败时的注册清理，以及缺失骨骼与非变换 shape 同名时正确跳过轨道。
- 中英文 ZIP 安装、单武器与双持拖放回调、MA/CAST/SMD/FBX 批量导出和往返读取。
- 米制输出、参考姿态补偿、批量蒙皮权重及成功静默/错误提示规则。

这些是 `mayapy` 宿主回归，不是本轮人工 GUI 鼠标拖放记录。GUI 与批处理共用实现，
但这不等于两种运行环境的全部交互都已人工验证。本轮独立 GUI 验收遇到 Maya
插件信任提示，按用户选择跳过；没有修改 Maya 的安全设置。

解析从四次减少为一次是已验证的调用次数变化，不等于所有动画都获得固定百分比
的加速。200 骨骼 / 240 帧合成动画的安全导入中位数为 1.243 → 1.015 秒，
下降约 18.3%，完整关键帧、切线和抽样世界矩阵一致。真实模型导入存在环境波动，
本版不宣称它获得同等提速。模型导入、完整挂载和合成动画的时间应分别看待；最新结果、基线、夹具和
一致性检查见[性能与一致性记录](CAST_BACKEND_BENCHMARK.md)。集成决策及下一阶段
热点研究见[后端研究](CAST_BACKEND_RESEARCH.md)，上游基线与补丁清单见
[PATCHES.md](../third_party/cast/PATCHES.md)。
