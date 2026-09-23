# 3.4.2 — Faster Maya attachment, quiet completion

## Changes / 更新

- CAST model import now writes skin weights in bounded API blocks instead of
  issuing a Maya command for every vertex. Influence ordering is resolved from
  the skinCluster, duplicate slots still accumulate, weights are not normalized,
  and the previous rigid-mesh behavior is preserved. DQS is unchanged.
- Single, quick, dual and weapon-batch attachment no longer display success
  dialogs. Completion remains in the Script Editor and builder status field.
  Exceptions, partial export failures and unsaved-scene confirmation remain visible.
- 挂载完成不再弹窗；错误仍提示。分块写入蒙皮权重，不改变骨骼挂载、权重或 DQS 设置。
- Blender functionality is unchanged; package versions are synchronized.

## Verification

Windows Maya 2027, Python 3.13.9. These are headless host tests, not a manual GUI
drag-and-drop test. Maya 2025 was not available for this release's regression run.

- `tests/benchmark_attachment.py`: generated 51,842-vertex pair reduced `setAttr`
  calls from 51,851 to 9. A real 46-skinCluster arms/weapon pair reduced calls from
  172,285 to 354; observed profiled build time fell from 3.45 s to 2.19 s (~37%).
  These measurements exclude export and Maya startup and are not a universal speed guarantee.
- `tests/verify_bulk_skin_weights.py`: exact comparison against the previous
  per-vertex writer, including weights and deformed world-space points; rigid,
  multi-influence, duplicate slots, zero weights, non-unit sums and chunk boundaries.
  The supplied real arms and weapon assets also passed exact weight/geometry comparison.
- `tests/verify_attachment_feedback.py`: English/Chinese single, quick, dual and
  batch callbacks; no success modal, retained exceptions and partial-output errors.
- `tests/verify_maya_drop_module_path.py`: registered-plugin single/dual drops.
- `tests/verify_batch_animation_export.py`: single/dual MA/CAST/SMD/FBX animation
  output round trips, DQS, failure continuation and cancellation.
- `tests/verify_plugin_identity.py`: English/Chinese/legacy entry points.

The optimization uses Autodesk's documented physical influence indexing and
non-normalizing [MFnSkinCluster.setWeights API](https://help.autodesk.com/cloudhelp/2027/CHS/MAYA-API-REF/py_ref/class_open_maya_anim_1_1_m_fn_skin_cluster.html).

## Installation

Close Maya, back up the current toolkit files, then replace the complete `plug-ins`
file set with the matching language ZIP. Do not overwrite personal `cast.cfg`.
Load only one language entry. No input models or existing scenes are modified.
