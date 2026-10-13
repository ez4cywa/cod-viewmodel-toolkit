"""On-demand FBX/SMD exports from an isolated Maya scene copy.

The caller chooses a format and static/animated content. This module owns
snapshotting, worker lifetime, unit conversion and non-overwriting publication;
the builder's output selections and live scene are not export prerequisites.
"""

from contextlib import nullcontext
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
from types import SimpleNamespace


FORMATS = ("fbx", "smd")
WORKER_TIMEOUT = 600


def _request_range(core, animated, frame_range):
    if not animated:
        return ()
    values = tuple(frame_range) if frame_range is not None else (
        core.cmds.playbackOptions(query=True, minTime=True),
        core.cmds.playbackOptions(query=True, maxTime=True),
    )
    if len(values) != 2 or any(isinstance(value, bool) or not isinstance(value, (int, float))
                               or not math.isfinite(value) or value != int(value)
                               for value in values):
        raise ValueError("Animation export requires two whole frame numbers")
    if values[0] < 0 or values[1] < values[0]:
        raise ValueError("Animation export requires a non-negative ordered frame range")
    return tuple(int(value) for value in values)


def _smd_mappings(core):
    """Static SMD retains the toolkit's existing attachment verification."""
    if core.cmds.ls(core.DUAL_STATE_NODE, type="network"):
        validation = core.validate_dual_wield()
        return [{"source": core._short_name(validation[side]["source_node"]),
                 "target": core._short_name(validation[side]["target_node"])}
                for side in ("left", "right")]
    result = core._LAST_RESULT
    if result is not None:
        source, target = result.source_joint_name, result.target_joint_name
    else:
        settings = core.load_saved_options()
        source, target = settings.source_joint, settings.target_joint
    validation = core.validate_attachment(source, target)
    return [{"source": core._short_name(validation["source_node"]),
             "target": core._short_name(validation["target_node"])}]


def _scene_state(cmds):
    return {
        "name": cmds.file(query=True, sceneName=True),
        "modified": cmds.file(query=True, modified=True),
        "selection": cmds.ls(selection=True, long=True) or [],
        "frame": cmds.currentTime(query=True),
        "up_axis": cmds.upAxis(query=True, axis=True),
        "playback": {name: cmds.playbackOptions(query=True, **{name: True})
                     for name in ("animationStartTime", "animationEndTime", "minTime", "maxTime")},
    }


def _save_snapshot(cmds, path, state):
    try:
        cmds.file(str(path), force=True, type="mayaAscii", exportAll=True, options="v=0;")
    finally:
        if cmds.file(query=True, sceneName=True) != state["name"]:
            cmds.file(rename=state["name"] or "untitled")
        cmds.currentTime(state["frame"], edit=True)
        cmds.playbackOptions(**state["playback"])
        if state["selection"]:
            cmds.select(state["selection"], replace=True)
        else:
            cmds.select(clear=True)
        cmds.file(modified=state["modified"])


def _log_tail(path):
    if not path.is_file():
        return ""
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - 4000))
        return stream.read(4000).decode("utf-8", "replace")


def _stop_worker(process):
    """Stop only the process/group created for this export."""
    if process.poll() is not None:
        return ""
    errors = []
    try:
        if os.name == "nt":
            result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if result.returncode:
                errors.append("Process-tree termination returned %s" % result.returncode)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError) as error:
        errors.append("Process-tree termination failed: %s" % error)
    # A failed tree-termination utility must not prevent stopping our own
    # worker or hide the original export timeout/failure.
    try:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=15)
    except (OSError, subprocess.SubprocessError) as error:
        errors.append("Worker termination failed: %s" % error)
    return "; ".join(errors)


def _run_worker(executable, request_path, folder):
    log_path = folder / "worker.log"
    environment = os.environ.copy()
    environment["MAYA_APP_DIR"] = str(folder / "maya-profile")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    Path(environment["MAYA_APP_DIR"]).mkdir()
    options = {"env": environment}
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    else:
        options["start_new_session"] = True
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [str(executable), os.path.abspath(__file__), "--request", str(request_path)],
            stdout=log, stderr=subprocess.STDOUT, **options)
        try:
            returncode = process.wait(timeout=WORKER_TIMEOUT)
        except BaseException as error:
            cleanup = _stop_worker(process)
            if isinstance(error, subprocess.TimeoutExpired):
                raise RuntimeError("Standalone export timed out after %s seconds:\n%s%s"
                                   % (WORKER_TIMEOUT, _log_tail(log_path),
                                      "\n" + cleanup if cleanup else "")) from error
            if cleanup:
                raise RuntimeError("Standalone export interrupted; cleanup: " + cleanup) from error
            raise
    if returncode:
        raise RuntimeError("Standalone export worker failed (%s):\n%s"
                           % (returncode, _log_tail(log_path)))
    response_path = folder / "response.json"
    if not response_path.is_file() or response_path.stat().st_size > 1024 * 1024:
        raise RuntimeError("Standalone export worker returned no valid report:\n" + _log_tail(log_path))
    response = json.loads(response_path.read_text(encoding="utf-8"))
    if not isinstance(response, dict):
        raise RuntimeError("Standalone export worker report must be an object")
    return response


def _publish(source, requested):
    """Choose a free version and exclusively publish one verified file."""
    for version in range(10000):
        target = requested if version == 0 else requested.with_name(
            requested.stem + "_v%03d" % version + requested.suffix)
        try:
            destination = target.open("xb")
        except FileExistsError:
            continue
        identity = os.fstat(destination.fileno())
        try:
            with destination, source.open("rb") as stream:
                shutil.copyfileobj(stream, destination)
        except BaseException:
            current = target.lstat()
            if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                target.unlink()
            raise
        return target
    raise RuntimeError("Unable to allocate a free export filename: %s" % requested)


def export_file(core, path, file_format, animated=False, frame_range=None,
                output_unit="original"):
    """Export the current scene to one FBX/SMD file without changing the scene.

    Existing filenames receive a version suffix. Static SMD needs a toolkit
    attachment; animated SMD writes skeleton frames, not mesh triangles. FBX
    supports a normal scene too. Metre conversion affects only the worker copy.
    """
    file_format = str(file_format).lower().lstrip(".")
    if file_format not in FORMATS:
        raise ValueError("Standalone export format must be fbx or smd")
    if not isinstance(animated, bool):
        raise ValueError("Choose static or animated export explicitly")
    if output_unit not in ("original", "m"):
        raise ValueError("Output unit must be original or m")
    if not str(path).strip():
        raise ValueError("Choose an export filename")
    requested = Path(path).expanduser().resolve()
    if not requested.suffix:
        requested = requested.with_suffix("." + file_format)
    if requested.suffix.lower() != "." + file_format:
        raise ValueError("The export filename must end in .%s" % file_format)
    frame_range = _request_range(core, animated, frame_range)
    core_path = core._core_module_path()
    executable = Path(sys.executable).with_name("mayapy.exe" if os.name == "nt" else "mayapy")
    if not executable.is_file():
        raise RuntimeError("Standalone export requires Maya's mayapy: %s" % executable)
    mappings = _smd_mappings(core) if file_format == "smd" and not animated else []
    state = _scene_state(core.cmds)
    requested.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".vwt-export-", dir=str(requested.parent)) as directory:
        folder = Path(directory)
        source, staging = folder / "source.ma", folder / ("export." + file_format)
        _save_snapshot(core.cmds, source, state)
        request = {
            "core": core_path, "scene": str(source), "output": str(staging),
            "format": file_format, "animated": bool(animated),
            "frame_range": list(frame_range), "output_unit": output_unit,
            "mappings": mappings, "frame": state["frame"],
            "up_axis": state["up_axis"], "playback": state["playback"],
            "response": str(folder / "response.json"),
        }
        request_path = folder / "request.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        report = _run_worker(executable, request_path, folder)
        if report.get("format") != file_format or report.get("animation_included") != bool(animated):
            raise RuntimeError("Standalone export worker returned an unexpected format or content mode")
        if not staging.is_file() or staging.stat().st_size <= 0:
            raise RuntimeError("Standalone export worker did not create a non-empty file")
        target = _publish(staging, requested)
    report.update(path=str(target), size=target.stat().st_size,
                  source_scene_preserved=True)
    core.log("Exported %s: %s" % (file_format.upper(), target))
    return report


def run_request(path):
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as cmds
    try:
        request = json.loads(Path(path).read_text(encoding="utf-8"))
        cmds.loadPlugin(request["core"], quiet=True)
        # The units helper already owns discovery of Maya's nameless registered
        # plugin globals. Do not import a second implementation in this worker.
        spec_path = Path(request["core"]).with_name("cod_viewmodel_units.py")
        import importlib.util
        spec = importlib.util.spec_from_file_location("_vwt_export_units", str(spec_path))
        units = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(units)
        core = units._registered_core(request["core"])
        cmds.file(request["scene"], open=True, force=True, prompt=False, executeScriptNodes=False)
        cmds.upAxis(axis=request["up_axis"], rotateView=False)
        cmds.playbackOptions(**request["playback"])
        cmds.currentTime(request["frame"], edit=True)
        conversion = units.convert_scene_copy() if request["output_unit"] == "m" else {"enabled": False}
        if request["format"] == "fbx":
            core._ensure_fbx_exporter()
            core.mel.eval("FBXExportUpAxis " + request["up_axis"])
        context = core._metric_output() if request["output_unit"] == "m" else nullcontext()
        with context:
            output, animated = request["output"], request["animated"]
            frame_range = tuple(request["frame_range"])
            if request["format"] == "fbx":
                if animated:
                    core._use_dqs_skinning()
                    report = core.export_fbx_animation(output, frame_range)
                else:
                    report = core.export_fbx_model(output)
            elif animated:
                report = core.export_smd_animation(output, frame_range)
            else:
                cast_path = str(Path(output).with_suffix(".cast"))
                mapping = request["mappings"][0]
                result = SimpleNamespace(source_joint_name=mapping["source"], target_joint_name=mapping["target"])
                core._export_model_cast(cast_path, result, verify=False)
                report = core.export_smd_from_cast(cast_path, output, mapping["source"], mapping["target"])
                for other in request["mappings"][1:]:
                    core.verify_exported_smd(output, other["source"], other["target"])
                report.update(animation_included=False, mesh_included=True)
        report.update(format=request["format"], unit_conversion=conversion)
        Path(request["response"]).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--request":
        raise SystemExit("Usage: mayapy cod_viewmodel_exports.py --request REQUEST.json")
    run_request(sys.argv[2])
