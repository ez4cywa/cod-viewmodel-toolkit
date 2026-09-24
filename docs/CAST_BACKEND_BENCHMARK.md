# CAST 私有后端改进：性能与一致性验证

测试环境：2026-09-24，本机 Maya 2027 / Python 3.13.9，独立 `mayapy` 进程。
固定基线：3.4.3，Git commit `5d545521311c3689ba287f3fcd71db6968939dda`。

## 方法

`tests/benchmark_cast_backend.py` 从 Git 对象提取基线运行文件到临时目录，
不依赖工作树中正在修改的 CAST 或本机已安装版本。基线和新版本分别在独立进程运行。
每个场景操作测量三次，使用中位数；Maya 启动、合成夹具生成、场景清空和结果采样不计入时长。
完整挂载保留实际入口内部的清场、预检查、模型导入、命名处理和父子关系验证。
profile 另外运行一次，不混入无 profiler 的时长样本；各项 inclusive 时间不可直接相加。

真实模型输入：

- 手臂：`rex_vm_arms_mp_milsim_us_sf_1_1_LOD0.cast`
- 武器：`att_rex_vm_ar_mike4_rec_v0_LOD0.cast`

合成动画输入由测试实时生成：200 个目标骨骼，每个骨骼 240 帧，
包含平移 XYZ 和四元数旋转，加一条武器滑套平移；导入后共 1,201 条 Maya 动画曲线。
它用于隔离大量曲线查找和重复解析成本，不能代表所有游戏动画文件的性能。

模型一致性检查复用已有 benchmark 的快照：世界顶点、法线及其索引、面拓扑、所有 UV 集及索引、
颜色集、材质分配、贴图路径和色彩空间、关节世界矩阵、每骨骼蒙皮权重以及蒙皮方法。
动画检查每个目标通道的全部关键帧时间、值、入/出切线类型，并采样首、中、末帧的世界矩阵。
这不是渲染图像等价验证。Maya standalone 下存在双方共有的缺失 `shaderfx` 过程警告。

## 单次读取回归

`tests/verify_animation_read_session.py` 经真实外部拖放回调调用安全动画导入，
统计物理 `Cast.load` 次数，同时检查手臂轨道路由、滑套动画和武器挂点平移归零。
成功后再次拖放必须重新解析，修改文件后再次拖放必须读取新内容，不允许把缓存永久留在进程中。
测试还检查正常导入、重复导入和文件更新导入均不调用 `cmds.rename`；向真实动画 importer 注入异常后，
导入选项、运行时选项、解析缓存和动画目标缓存都恢复，关节全路径不变，下一次导入能成功。

修改前实际红测试输出：

```text
ANIMATION_READ_SESSION {"revision": "baseline", "physical_reads": 4, "expected": 1, "routing_correct": true}
AssertionError: ('One drop must have one operation-scoped parse', 4, 1)
```

## 初始基线定位结果

初次三次测量的中位数：完整挂载 1.688 秒，手臂单独导入 0.809 秒，武器单独导入 0.828 秒，
合成动画安全拖放 1.240 秒。最终对照结果以本文件后续完整对照表为准。

该次独立 profile 的完整挂载包含：解析 0.129 秒 / 2 次，骨架创建 0.023 秒，
材质创建 0.059 秒，初始 skinCluster 绑定 0.353 秒 / 46 次，批量权重写入 0.343 秒 / 46 次。
`importModelNode` 总时间 1.573 秒还包括网格、UV、颜色等处理，不能把剩余值全解释为 Maya 网格创建。
合成动画 profile：文件解析 0.140 秒 / 4 次，曲线查找/创建 0.134 秒 / 1,201 次，
动画 importer 总时间 0.859 秒。

这些观测支持优先减少动画重复解析与目标查找。初始蒙皮绑定仍占有可见成本，
但没有在本次测量中证明可以安全跳过 Maya 绑定状态初始化，因此不能据此宣称可直接省去这部分时间。

## 中间实现的完整对照与波动

下表是已加入私有后端、单次解析、动画目标映射，但尚未消除重复关键帧范围查询时的三次中位数。
保留第一次对照和随后逆序确认的全部中位数，不只选有利结果。

| 操作 | 第一组：基线 → 新版，秒 | 第二组：基线 → 新版，秒 |
| --- | --- | --- |
| 两模型完整挂载 | 1.621 → 1.973 | 2.033 → 1.973 |
| 手臂单独导入 | 0.815 → 0.939 | 0.941 → 0.967 |
| 武器单独导入 | 0.803 → 0.981 | 0.982 → 0.963 |
| 合成动画安全拖放 | 1.553 → 1.464 | 1.556 → 1.529 |

第一组运行顺序是基线 → 新版，第二组为新版 → 基线。
第一组可能受到另一测试进程负载影响；第二组各代理协调暂停其他 Maya 测试进程。
固定基线自身的完整挂载中位数从 1.621 变化到 2.033 秒，说明环境漂移明显。
因此不从这两组数字宣称模型导入有显著提速或回退。
两组真实模型快照、动画完整关键帧/切线和抽样矩阵均严格相等。

第二组独立 profile 的动画解析为 0.185 秒 / 4 次 → 0.044 秒 / 1 次，
曲线查找/创建为 0.215 → 0.104 秒，动画 importer 总时间为 1.165 → 0.928 秒。
这些局部时间不能代替整个安全拖放操作的用时。

## 关键帧范围查询的第二轮红绿回归

工作函数 profile 发现安全导入后分别调用 `_curve_time_range` 和
`_set_playback_range_from_curves`，重复把同一批约 28.8 万个关键帧时间从 Maya 返回 Python。
单次 profile 中这两步分别约 0.192 和 0.194 秒。
改进后直接复用已求出的动画范围设置播放范围，并保留无关键帧时报错的行为。

修改前回归实际失败：`physical_reads=1, key_time_queries=2`。
修改后实际通过：`physical_reads=1, key_time_queries=1`，并通过无临时改名、文件更新、异常恢复检查。

## 最终动画对照

范围查询修复后，协调暂停其他代理的 Maya 测试，用新版 → 固定基线的顺序重新测量合成动画。
未清空操作系统文件缓存，不包含 Maya 冷启动，也未测量真实游戏动画文件。

| 合成动画安全拖放 | 三次样本，秒 | 中位数，秒 |
| --- | --- | --- |
| 固定 3.4.3 基线 | 1.243、1.181、1.396 | 1.243 |
| 最终新实现 | 1.026、1.015、0.948 | 1.015 |

本合成场景的中位数下降约 **18.3%**。完整关键帧、入/出切线和抽样矩阵严格相等。
这是指定 200 骨骼 / 240 帧场景的实测结果，不是所有 `.cast` 导入的速度承诺。
真实模型的两组完整对照仍应按前述波动解释，不能套用动画的提速幅度。

最终独立 profile：物理解析从 4 次 / 0.168 秒降至 1 次 / 0.047 秒，
曲线查找/创建从 0.166 秒降至 0.102 秒；两次全量关键帧时间查询减少为一次。
不要把 profile 下的局部时间相加推算上表无 profiler 的总用时。

本轮保留正常 `skinCluster` 绑定，不采用跳过绑定初始化的捷径。
Autodesk 文档规定 `bindMethod=3` 之后需要 `geomBind`，而修改 `maximumInfluences`
可重分配权重；这些不是已经证实无副作用的提速方案。[Maya 2027 skinCluster 官方文档](https://help.autodesk.com/cloudhelp/2027/ENU/Maya-Tech-Docs/CommandsPython/skinCluster.html)

## 复现

在仓库根目录用 PowerShell 运行，输出文件是测量产物，不要提交真实模型快照：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
mayapy.exe tests/benchmark_cast_backend.py --revision baseline --models HANDS.cast WEAPON.cast --runs 3 --output baseline.json
mayapy.exe tests/benchmark_cast_backend.py --revision current --models HANDS.cast WEAPON.cast --runs 3 --output current.json --compare baseline.json
mayapy.exe tests/verify_animation_read_session.py
```

`--revision baseline` 的单次读取回归预期失败；若要确认基线行为且返回成功，使用
`--revision baseline --expected-reads 4`。无真实模型时，可省略 benchmark 的 `--models`，只运行合成动画测试。
