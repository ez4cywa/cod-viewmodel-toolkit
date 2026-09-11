"""Opt-in real-asset metric regression; paths supplied only by the caller."""
import hashlib
import sys
from pathlib import Path

from verify_maya_units import cmds, ROOT, compare_scaled, samples, _module_from_path

hands, weapon, clip, output = sys.argv[1:]
paths = [hands, weapon, clip]
hashes = [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths]
plugin = ROOT / "plug-ins/viewmodel_weapon_toolkit.py"
cmds.loadPlugin(str(plugin), quiet=True)
core = _module_from_path(plugin)
settings = core.AttachOptions(output_dir=output, force_new_scene=True,
    export_fbx=True, export_smd=True, export_animation=True, output_unit="m")
result = core._build_single_attachment(hands, weapon, settings)
result.animated_outputs = True
result.animation_path = clip
core.import_animation_file(clip)
end = int(cmds.playbackOptions(query=True, maxTime=True))
result.frame_range = (0, end)
nodes = [core._short_name(n) for n in cmds.ls(type="joint")]
before = samples(nodes, end)
core._write_result_outputs(result, settings)
assert not result.output_errors, result.output_errors
compare_scaled(before, samples(nodes, end), 1.0)
cmds.file(result.output_scene, open=True, force=True, prompt=False, executeScriptNodes=False)
assert cmds.currentUnit(query=True, linear=True) == "m"
compare_scaled(before, samples(nodes, end), 0.3048, matrix_factor=30.48, tolerance=0.01)
time_unit = cmds.currentUnit(query=True, time=True)
cmds.file(new=True, force=True)
cmds.currentUnit(linear="m", time=time_unit)
core._ensure_fbx_exporter()
cmds.file(result.output_fbx, i=True, type="FBX", ignoreVersion=True)
compare_scaled(before, samples(nodes, end), 0.3048, matrix_factor=30.48, tolerance=0.02)
assert hashes == [hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths]
print("MAYA_REAL_METRIC_OK", len(nodes), end + 1, "frames; MA/FBX poses and bounds; inputs unchanged")
