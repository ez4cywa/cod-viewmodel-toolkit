# Maya Viewmodel Weapon Toolkit 3.1.0

## English

This release adds animation batch export to both the single-weapon and
dual-wield workflows.

- Queue multiple single animations or explicit left/right dual-animation
  pairs. Dual batches retain simultaneous/sequential playback and optional
  reference-pose compensation.
- Select MA, CAST, SMD, and FBX independently and choose a separate output
  folder for each format.
- Use DQS (Dual Quaternion) skinning throughout batch assembly. Animated CAST
  preserves the assembled rest model; CAST and FBX receive explicitly sampled
  skeletal animation.
- Isolate every clip/pair, continue after per-item or per-format failures,
  support cancellation between jobs, avoid overwrites with versioned names,
  and write a JSON batch report.
- Prefer the package-adjacent patched CAST 1.99 translator when CAST is not
  already loaded. Existing Maya CAST installations are respected and are not
  overwritten. `cast.cfg` and the obsolete `castpluginoptions.mel` are not
  required or included.

Maya 2022+ in Python 3 mode is the expected compatibility range. This release
was verified on Maya 2025 for Windows, including clean-profile loading of both
archives and MA/CAST/SMD/FBX batch round trips.

Install either the English or Simplified Chinese entry point, not both at the
same time. See the included README for installation and batch usage.

## 简体中文

本版本为单武器和双持流程增加动画批量导出。

- 单武器可排队多个动画；双持可排队明确的左右动画配对，并保留同时/顺序播放及
  可选参考姿态补偿。
- MA、CAST、SMD、FBX 可独立勾选，并可分别指定输出目录。
- 批量装配统一使用 DQS（双四元数）蒙皮。动画 CAST 保留装配后的原始静止模型；
  CAST 与 FBX 写入明确逐帧采样的骨骼动画。
- 每个动画或配对使用独立场景；单项或单格式失败后继续；支持在项目间取消；
  版本化命名避免覆盖，并生成 JSON 批次报告。
- 未加载 CAST 时优先使用发布包相邻的项目补丁版 CAST 1.99；已有 Maya CAST
  安装会被保留且不会覆盖。无需也不包含 `cast.cfg` 和已淘汰的
  `castpluginoptions.mel`。

预期兼容 Maya 2022+ 的 Python 3 模式。本版本已在 Windows 版 Maya 2025
完成验证，包括中英文压缩包的干净配置加载及 MA/CAST/SMD/FBX 批量往返检查。

英文版与简体中文版入口二选一安装，请勿同时加载。安装和批量操作方法见包内 README。

## SHA-256

- `maya-viewmodel-weapon-toolkit-3.1.0-en.zip`:
  `D9BD98A8045221868764689F85E4ABA5F24BD4DB54DD198D77C1F74C21043D9A`
- `maya-viewmodel-weapon-toolkit-3.1.0-zh-CN.zip`:
  `4C635017AB0BFF6F212AEC7BB87D7C31752D00A3850A721523E0BF0D5DB48B56`
