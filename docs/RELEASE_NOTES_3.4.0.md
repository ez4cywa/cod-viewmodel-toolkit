# CoD Viewmodel Toolkit 3.4.0 — ft to meters

## 中文

Maya 和 Blender 新增可选的米制输出：在输出设置选择 **Meters (input: ft)**，
按 **1 ft = 0.3048 m** 转换导出副本。默认仍保持原单位，不修改当前场景或输入文件。
支持单武器、双持和批量导出；工具生成的米制原生场景重复导出不会再次缩小。

- Maya `.ma` 和 Blender `.blend` 使用米制工作单位。
- CAST/SMD 写入米制距离数值；Blender FBX 写入米单位标记。
- **Maya FBX 实际尺寸正确，但后台导出器仍以厘米存储并标记。** 支持单位的导入器会还原正确尺寸。
- 修复 Maya 重复导入动画时复用曲线的识别，并让后台导出继承源场景朝上轴。

安装包：Maya 英文、Maya 简体中文、Blender 英文。Maya 升级时不要覆盖 `cast.cfg`。
已验证 Maya 2025、Blender 5.2.1 LTS，包含真实 190 骨骼／38 帧单武器素材和合成双持。
FBX 接收软件仍需匹配双四元数／保持体积蒙皮；动画 SMD 仅含骨骼。

## English

Optional **Meters (input: ft)** output converts an isolated export copy using
**1 ft = 0.3048 m**. Keep original remains the default. Input files and the live
scene stay unchanged. Single, dual and batch workflows are supported; marked
metric native scenes are not scaled again on re-export.

MA/BLEND use meter working units. CAST/SMD write numeric meter distances.
Blender FBX carries meter metadata. **Maya FBX retains centimeter storage
metadata but has the correct converted physical size.** Unit-aware importers
restore the correct dimensions. Maya's worker now inherits the source up axis;
repeated animation imports correctly detect reused curves.

Packages: Maya EN, Maya 简体中文, Blender EN. Preserve `cast.cfg` when upgrading
Maya. Tested on Maya 2025 and Blender 5.2.1 LTS, including real 190-bone/38-frame
single-weapon data and synthetic dual-wield tests. FBX still requires matching
Dual Quaternion / Preserve Volume skinning; animated SMD is skeletal only.

[Output units](https://github.com/ez4cywa/cod-viewmodel-toolkit/blob/3.4.0/docs/OUTPUT_UNITS.md)
· [Verification](https://github.com/ez4cywa/cod-viewmodel-toolkit/blob/3.4.0/docs/VERIFICATION_3.4.0.md)
