# 3.4.0 verification

Runtimes: Maya 2025 / Python 3.11.4 and Blender 5.2.1 LTS on Windows.
No game assets are distributed. Real-asset tests take caller-supplied paths.

- `verify_maya_units.py`: 10 ft becomes 3.048 m; animated/static outputs,
  source scene/units/selection/curves preserved, repeated exports and metric
  scene re-export, original clip reapplication, MA/FBX geometry and pose checks,
  CAST translation samples.
- `verify_maya_unit_assets.py`: supplied 190-bone, 38-frame, 60-fps assembly;
  all-frame MA/FBX poses and mesh bounds, unchanged input hashes. The worker
  inherits the source up axis explicitly to avoid a 90-degree FBX mismatch.
- `verify_blender_units.py`: metric BLEND/FBX/CAST round trips, FBX meter
  metadata, source preservation, repeated output and source clip reapplication,
  dual export and cleanup after rejecting unsupported constraints.
- `verify_blender_assets.py --meters`: supplied real assembly at frames
  0/18/37. Maximum bone-position error: BLEND 0.0000047 m, CAST 0.0000197 m,
  FBX 0.0000208 m. FBX mesh comparison uses matching DQS skinning.
- Existing Maya batch and Blender toolkit regressions pass (single/dual,
  replacement, sequential composition, failure continuation and cancellation).
- Maya EN/ZH UI: 560/760-pixel widths, expanded sections, focus visibility,
  keyboard traversal. Delayed startup avoids Maya viewport focus stealing.

Maya FBX retains centimeter storage metadata while physical size is correct.
This is a documented limitation, not a claimed native-meter FBX pass.
See [output units](OUTPUT_UNITS.md) for behavior and supported inputs.
