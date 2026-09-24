# 3.4.3 — Further CAST import optimization

- Reduce temporary lists when preparing mesh positions, normals and UV buffers.
- Reuse parsed CAST documents between preflight and import within one attachment
  operation. Invalidate changed files and release documents on success or error.
- Speed up face-index validation while preserving malformed-input diagnostics.
- Preserve geometry, UV tables/assignments, normals, vertex colors, material
  assignments, skin weights and DQS. Success dialogs remain disabled; errors remain visible.
- Blender functionality is unchanged; package versions remain synchronized.

## 性能与验证

本机 Maya 2027、同一组手臂和武器模型交替测试三轮：检查、导入和挂载的中位耗时
由 3.4.2 的 **2.216 秒降至 1.814 秒，减少约 18.1%**，不含启动和导出。
直接使用 CAST 导入器时收益较小，初步约 6%；完整收益包含工具包的解析复用。
此结果不代表所有模型或机器都达到相同速度。

Scene equivalence, cache lifetime/invalidation, malformed-input diagnostics,
registered-plugin single/dual animation drops and MA/CAST/SMD/FBX animation
round trips are covered by Maya host tests. These are headless tests, not manual
GUI mouse-drop tests. See [measurement details](CAST_IMPORT_OPTIMIZATION.md).

## 更新方法

关闭 Maya，备份旧版后，使用对应语言 ZIP 完整替换 `plug-ins` 文件。
保留个人 `cast.cfg`，只加载一种语言入口。输入模型和已有场景不需修改。

Maya 2027 / Windows is the verified host for this release. Earlier Maya version
targets remain unchanged but were not re-tested for this release.
