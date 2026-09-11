# Output units / 输出单位 — 3.4.0

In **Output Unit**, choose **Meters (input: ft)** to interpret the imported
CoD distance numbers as feet. The conversion is exactly **1 ft = 0.3048 m**.
**Keep original** remains the default. This is an explicit input assumption,
not automatic detection of units from arbitrary CAST files.

在输出设置的“输出单位”中选择“米（输入：英尺）”。默认仍为“保持原单位”。
选项适用于单武器、双持和批量导出；只转换输出副本，不改变输入文件或当前场景。

| Output | Metric behavior / 米制行为 |
| --- | --- |
| Maya `.ma` | Working unit `m`; geometry, joints, bind matrices and translation animation converted. / 工作单位为米，转换几何、骨骼、绑定矩阵和位移动画。 |
| Blender `.blend` | Metric, scale length 1, meters; uniform assembly-object scaling preserves exact bone bases and deformation. / 米制场景，通过组装根对象统一缩放保留骨骼朝向和变形。 |
| Blender FBX | Meter unit metadata (`UnitScaleFactor=100`) and converted physical size. / 米标记及正确尺寸。 |
| Maya FBX | Correct converted physical size; Maya's standalone exporter retains centimeter storage metadata. A unit-aware importer reconstructs the correct size. / 实际尺寸正确，但后台导出器仍以厘米存储；支持单位的导入器会还原正确尺寸。 |
| CAST / SMD | Distance values in meters; no standard working-unit setting is implied. / 距离数值为米，不代表格式具有场景工作单位设置。 |
| JSON | Records input/output units, factor and repeat-conversion state. / 记录输入输出单位、换算比例和重复转换状态。 |

Maya uses a separate `mayapy` process to convert the exported scene copy; large
scenes take extra time. No freezing is performed. Blender deliberately retains
local bone data and uses a uniform object scale: applying transforms is not
required. Toolkit-produced metric native scenes carry a marker so exporting
them again does not multiply by 0.3048 again. Original foot-valued animation
clips can be reapplied through the toolkit to these native scenes.

Maya 会启动独立 `mayapy` 进程，因此大场景导出会更慢。不执行冻结变换。
Blender 保留局部骨骼数据，用对象统一缩放，不需要手动 Apply Scale。
工具生成的米制原生场景带有标记，重复导出不会再次缩小。

Custom live translations driven by constraints/expressions in Maya, or
Blender constraints/drivers/NLA, need baking before metric-copy export.
Ordinary toolkit-built assemblies and baked clips are supported. SMD still
cannot represent animated scale/shear, and FBX round trips still require
matching DQS skinning for the original deformation; unit conversion does not
change these format limitations.
