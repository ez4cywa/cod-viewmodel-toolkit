# 3.6.2 — 动画连续导入自动刷新场景修复

修复 Maya 在导入较长动画后再导入较短动画时不会自动重置场景动画，而是复用原有
动画曲线、保留长动画尾部关键帧并拼接两段动画的问题。同时修复双持单侧替换时
未清理无关键帧曲线、未还原无动画通道骨骼 `castRestPosition` 及保留旧通知轨的问题。

## 原因与修复

### 单持动画重新导入

此前 `import_animation_file`（由 **安全导入动画…**、**导入 CAST…**、视口拖放和
动画批量队列共用）固定以 `importReset=False`（`importReset=0`）调用内置
`CoDToolkitCast` 转换器。当场景已导入较长动画（如 `0–228` 帧的检视动画）后再次
导入较短动画（如 `0–21` 帧的抬枪动画）时：

1. 转换器复用骨骼已连接的 `animCurve`，仅覆盖 `0–21` 帧关键帧，原 `22–228` 帧关键帧
   仍留在曲线上；
2. 仅在长动画中含有关键帧、而在短动画中无关键帧的骨骼（如弹匣、相机或部分手指位移通道）
   保留旧动画曲线或偏移姿态；
3. `CastNotetracks` 保留长动画的通知轨；
4. 帧范围统计从复用的 `animCurve` 读取最大帧号，导致时间轴仍保持 `0–228` 帧，表现为
   短动画与长动画后半段缝合。

本版在校验待导入动画至少有一条轨道匹配当前场景后，为单持导入启用
`importReset=True`（`importReset=1`）：

- 先清除现有通道动画曲线与 `CastNotetracks`，并将带有 `castRestPosition` 的骨骼
  还原至挂载后的初始静止变换；
- 再创建新动画曲线、写入通知轨，并将时间轴与已打开的独立 FBX/SMD 导出窗口帧范围
  同步更新为新动画的实际帧区间；
- 若待导入动画与当前场景没有任何匹配轨道，在修改场景帧率或清理现有动画前直接报错拒绝。

### 双持单侧替换

`replace_dual_animation` 在清理被替换侧关键帧后，现在会删除关键帧数量归零的残留
`animCurve`，对具有 `castRestPosition` 的被路由骨骼恢复初始静止变换，并根据保留侧与
新导入侧重建 `CastNotetracks`。

## 验证范围

2026-10-24 已通过的检查：

- Python 3.14：`verify_source_contracts.py`、`verify_vendored_cast.py`、
  `verify_empty_material_references.py`、`verify_cast_import_names.py`、
  `verify_vendored_blender_cast.py`、`verify_build_release.py`、
  `verify_standalone_exports.py`、`verify_standalone_export_ui.py`。
- Maya 2027 / Python 3.13.9：
  - 使用真实资产（`viewhands_mp_base_iw8_LOD0.cast` + `sargas.cast`，先导入
    `sat_vm_sl_sargas_inspect.cast` `0–228` 帧、146 条曲线、14 条通知轨，再导入
    `sat_vm_sl_sargas_raise.cast` `0–21` 帧、135 条曲线、8 条通知轨）验证单持与双持
    替换：导入后帧范围为 `(0.0, 21.0)`、曲线数 `321`、残留曲线 `0`、通知轨与直接
    在干净场景导入 `raise` 完全一致，全部 182 根骨骼在采样帧的世界矩阵与干净导入零差异。
  - 源码入口与本机已安装中英文入口通过 `verify_plugin_identity.py`、
    `verify_animation_read_session.py`、`verify_cast_import_gateway.py`、
    `verify_maya_drop_module_path.py`、`verify_batch_animation_export.py`、
    `verify_maya_units.py`、`verify_standalone_export_host.py`，以及新增的长动画转短动画
    单持／双持回归。
  - Maya 中英文发布包通过 `verify_release_package.py` 验证。
- Blender 5.2.1 LTS：中英文发布包在隔离 `BLENDER_USER_SCRIPTS` 环境下通过
  `verify_blender_release.py` 验证。
