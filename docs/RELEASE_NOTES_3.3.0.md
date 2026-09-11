# CoD Viewmodel Toolkit 3.3.0

The project is now **CoD Viewmodel Toolkit**, focused on Call of Duty
first-person CAST hands, weapon and animation workflows in **Maya and Blender**.

## Packages

- `cod-viewmodel-toolkit-3.3.0-maya-en.zip` — Maya English.
- `cod-viewmodel-toolkit-3.3.0-maya-zh-CN.zip` — Maya 简体中文.
- `cod-viewmodel-toolkit-3.3.0-blender-en.zip` — Blender English, install from disk.

Maya retains its existing loader filenames and `viewmodelWeaponToolkit` /
`attachGun` commands. Its CAST 2.00 backend and assembly/export behavior are
unchanged from 3.2.0. Do not overwrite `cast.cfg` when upgrading.

Blender requires 5.2+ and was verified with 5.2.1 LTS on Windows. It adds
single/dual assembly, left/right animation composition and replacement,
reference-pose translation compensation, independent output directories and
batch queues with failure continuation. The bundled private backend derives
from upstream CAST 2.00; no Maya installation or separate CAST add-on is needed.

Blender exports `.blend`, `.cast`, `.fbx` and `.smd`. BLEND contains only the
assembly scene. Animated SMD is skeletal only. **FBX receiving applications
must use Dual Quaternion / Preserve Volume skinning** to match the verified
CoD deformation; default linear skinning does not match it. Textures remain
external references, and blend-shape animation is outside skeletal composition.

Real single-weapon data and synthetic dual-wield tests passed. A real
left/right dual-clip pair was not available and is not claimed as tested.
Compatibility depends on the source skeleton, not just the game title.

## 中文摘要

项目统一更名为 **CoD Viewmodel Toolkit**，主要服务使命召唤第一人称 CAST
工作流。本次同时发布 Maya 英文、Maya 简体中文和 Blender 英文安装包。
Maya 保留旧加载文件名和命令；Blender 版独立运行，使用上游 CAST 2.00 的项目
补丁后端。已验证 Blender 5.2.1 LTS 的真实单武器素材及合成双持测试。

FBX 接收软件需开启双四元数／保持体积蒙皮；动画 SMD 仅含骨骼；BLEND 仅保存
组装体场景。具体安装和限制请参阅对应平台说明。

[Blender guide](BLENDER.md) · [Blender 中文说明](BLENDER.zh-CN.md)
· [Verification](VERIFICATION_3.3.0.md) · [Maya guide](../README.md)
