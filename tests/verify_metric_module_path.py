"""Mayapy: metric exports use the real registered core without ``__file__``.

Run in an isolated MAYA_APP_DIR. All scenes, CAST inputs and worker requests
are synthetic and temporary; English, Chinese and legacy entries are loaded
from one installation rather than importing a second test implementation.
"""

import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
from unittest.mock import patch

import maya.cmds as cmds
import maya.standalone

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from verify_batch_animation_export import make_animation, make_model, samples


def loaded_plugin_globals(path):
    """Use the registered functions, skipping dead weak proxies after unload."""
    gc.collect()
    expected = os.path.normcase(os.path.abspath(str(path)))
    found = {}
    for obj in gc.get_objects():
        if type(obj) is types.FunctionType and obj.__name__ == "initializePlugin":
            namespace = obj.__globals__
            registered = namespace.get("_TOOLKIT_PLUGIN_PATH", "")
            if registered and os.path.normcase(os.path.abspath(registered)) == expected:
                found[id(namespace)] = namespace
    assert len(found) == 1, "Expected one real registered core: %r" % list(found)
    return next(iter(found.values()))


def scene_snapshot():
    frame = cmds.currentTime(query=True)
    joints = cmds.ls(type="joint", long=True) or []
    evaluated = samples(joints, 3)
    cmds.currentTime(frame)
    return {
        "name": cmds.file(query=True, sceneName=True),
        "modified": cmds.file(query=True, modified=True),
        "selection": cmds.ls(selection=True, long=True),
        "nodes": set(cmds.ls(long=True)),
        "curves": set(cmds.ls(type="animCurve")),
        "unit": cmds.currentUnit(query=True, linear=True),
        "frame": frame,
        "playback": tuple(cmds.playbackOptions(query=True, **{name: True})
                          for name in ("animationStartTime", "animationEndTime", "minTime", "maxTime")),
        "evaluated": evaluated,
    }


def verify_export(namespace, folder, animated):
    core = types.SimpleNamespace(**namespace)
    mode = "animation" if animated else "static"
    hands, weapon, clip = [folder / (name + ".cast") for name in ("hands", "weapon", "clip")]
    cmds.currentUnit(linear="cm")
    make_model(core, hands, True)
    make_model(core, weapon, False)
    serializer = core._cast_backend().serializer
    document = serializer.Cast.load(str(hands))
    model = next(node for node in document.Roots()[0].childNodes if isinstance(node, serializer.Model))
    next(bone for bone in model.Skeleton().Bones() if bone.Name() == "j_wrist_le").SetLocalPosition((-10, 0, 0))
    document.save(str(hands))
    make_animation(core, clip, 3, [("j_gun", "tx", 0, 10, "absolute")])
    options = core.AttachOptions(output_dir=str(folder / mode), force_new_scene=True,
                                 output_unit="m", export_animation=animated)
    result = namespace["_build_single_attachment"](str(hands), str(weapon), options)
    if animated:
        result.animated_outputs = True
        result.animation_path = str(clip)
        namespace["import_animation_file"](str(clip))
        result.frame_range = (0, 3)
    cmds.currentUnit(linear="ft")
    cmds.file(rename=str(folder / (mode + "_live.ma")))
    cmds.select(result.target_node, replace=True)
    cmds.currentTime(2)
    before = scene_snapshot()
    units = namespace["_units_module"]()
    export_copy, run_worker = units.export_copy, units.subprocess.run
    requests = []
    if not animated:
        with patch.dict(namespace, {"_TOOLKIT_PLUGIN_PATH": ""}), \
                patch.object(core, "_allocate_result_output_paths", side_effect=AssertionError("Allocated before validation")), \
                patch.object(cmds, "file", side_effect=AssertionError("Wrote a snapshot before validation")):
            try:
                export_copy(core, result, options)
            except RuntimeError as error:
                assert "core path is unavailable" in str(error), error
            else:
                raise AssertionError("Expected missing core path to fail before side effects")
        previous_metric = namespace["_OUTPUT_IN_METERS"]
        try:
            with namespace["_metric_output"]():
                assert namespace["_OUTPUT_IN_METERS"]
                raise RuntimeError("metric context fixture")
        except RuntimeError as error:
            assert str(error) == "metric context fixture"
        assert namespace["_OUTPUT_IN_METERS"] is previous_metric

    def observe_core(actual_core, *args, **kwargs):
        assert actual_core._write_result_outputs.__globals__ is namespace, "Metric export borrowed a different core"
        return export_copy(actual_core, *args, **kwargs)

    def observe_worker(command, *args, **kwargs):
        request = json.loads(Path(command[2]).read_text(encoding="utf-8"))
        assert Path(request["core"]).resolve() == ROOT / "plug-ins/viewmodel_weapon_toolkit.py", request["core"]
        requests.append(request)
        return run_worker(command, *args, **kwargs)

    with patch.object(units, "export_copy", side_effect=observe_core), \
            patch.object(units.subprocess, "run", side_effect=observe_worker):
        namespace["_write_result_outputs"](result, options)
    assert len(requests) == 1, "Expected one real metric worker"
    assert before == scene_snapshot(), "Metric worker changed the live scene"
    assert result.unit_conversion["factor"] == 0.3048 and not result.output_errors
    assert Path(result.output_manifest).is_file()
    assert Path(result.output_cast).stat().st_size > 0
    exported = serializer.Cast.load(result.output_cast)
    exported_model = next(node for node in exported.Roots()[0].childNodes if isinstance(node, serializer.Model))
    wrist = next(bone for bone in exported_model.Skeleton().Bones() if bone.Name() == "j_wrist_le")
    assert abs(wrist.LocalPosition()[0] + 3.048) < 1e-6
    if animated:
        animation = next(node for node in exported.Roots()[0].childNodes if isinstance(node, serializer.Animation))
        track = next(curve for curve in animation.Curves() if curve.NodeName() == "viewhands_j_gun"
                     and curve.KeyPropertyName() == "tx")
        assert abs(track.KeyValueBuffer()[-1] - 3.048) < 1e-6
    cmds.file(result.output_scene, open=True, force=True, prompt=False, executeScriptNodes=False)
    assert cmds.currentUnit(query=True, linear=True) == "m"
    assert abs(cmds.getAttr("j_wrist_le.tx", time=0) + 3.048) < 1e-6
    if animated:
        assert abs(cmds.getAttr("viewhands_j_gun.tx", time=3) - 3.048) < 1e-6
    print("METRIC_NO_FILE_%s_OK: real worker; source preserved; 10ft=3.048m" % mode.upper())


def verify_entry(entry):
    missing = object()
    with tempfile.TemporaryDirectory(prefix="cod_metric_module_path_") as temporary:
        folder = Path(temporary)
        plugin = ROOT / "plug-ins" / entry
        cmds.file(new=True, force=True)
        cmds.loadPlugin(str(plugin), quiet=True)
        registered_path = ROOT / "plug-ins/viewmodel_weapon_toolkit.py" if entry == "attach_gun.py" else plugin
        namespace = loaded_plugin_globals(registered_path)
        previous = namespace.pop("__file__", missing)
        namespace["_UNITS_MODULE"] = None
        try:
            module_name = namespace.get("__name__")
            print("METRIC_CORE_IDENTITY: entry=%s; namespace=%s; module_present=%s" % (
                entry, module_name, module_name in sys.modules))
            for animated in (False, True):
                verify_export(namespace, folder, animated)
            print("METRIC_ENTRY_%s_OK" % plugin.stem.upper())
        finally:
            if previous is not missing:
                namespace["__file__"] = previous
            cmds.file(new=True, force=True)
            cmds.unloadPlugin(plugin.stem, force=True)
            if entry == "attach_gun.py":
                cmds.unloadPlugin("viewmodel_weapon_toolkit", force=True)


def main():
    entries = ("viewmodel_weapon_toolkit.py", "viewmodel_weapon_toolkit_zh_CN.py", "attach_gun.py")
    if "--entry" not in sys.argv:
        # Maya retains unloaded plugin globals. Fresh hosts avoid mistaking an
        # old English namespace for the English core loaded by the legacy entry.
        for entry in entries:
            process = subprocess.run([sys.executable, __file__, "--entry", entry],
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
            sys.stdout.buffer.write(process.stdout)
            sys.stdout.flush()
            assert process.returncode == 0, "Metric entry verification failed: %s" % entry
        print("METRIC_MODULE_PATH_OK")
        return
    entry = sys.argv[sys.argv.index("--entry") + 1]
    assert entry in entries, "Unknown toolkit entry: %s" % entry
    verify_entry(entry)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
