"""Maya metric export worker. Convert an isolated scene, never the live rig.

Maya's CAST model backend stores distances in internal centimetres while its
animation writer uses current working units. Keep those boundaries explicit.
"""

from dataclasses import asdict
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

FEET_TO_METERS = 0.3048
FEET_TO_CENTIMETERS = 30.48
UNIT_KEY = "cod_viewmodel_linear_unit"


def scale_cast(document, serializer, model_factor=1.0, animation_factor=1.0):
    """Scale distance fields through the upstream serializer; no binary parsing."""
    def visit(node):
        if isinstance(node, serializer.Curve):
            if node.KeyPropertyName() in ("tx", "ty", "tz"):
                node.SetFloatKeyValueBuffer([value * animation_factor for value in node.KeyValueBuffer()])
        if isinstance(node, (serializer.Model, serializer.Bone, serializer.Mesh, serializer.BlendShape)):
            for getter, setter, vector_buffer in (
                    ("Position", "SetPosition", False),
                    ("LocalPosition", "SetLocalPosition", False),
                    ("WorldPosition", "SetWorldPosition", False),
                    ("VertexPositionBuffer", "SetVertexPositionBuffer", True),
                    ("TargetShapeVertexPositions", "SetTargetShapeVertexPositions", True)):
                if not hasattr(node, getter):
                    continue
                values = getattr(node, getter)()
                if values is not None:
                    scaled = [value * model_factor for value in values]
                    if vector_buffer:
                        scaled = [tuple(scaled[index:index + 3]) for index in range(0, len(scaled), 3)]
                    getattr(node, setter)(scaled)
        for child in node.childNodes:
            visit(child)
    for root in document.Roots():
        visit(root)
    return document


def scene_is_metric():
    import maya.cmds as cmds
    return (cmds.fileInfo(UNIT_KEY, query=True) or []) == ["m"]


def _matrix_translation(plug, factor):
    import maya.cmds as cmds
    if cmds.connectionInfo(plug, isDestination=True):
        return
    stored = cmds.getAttr(plug)
    if stored is None:
        return
    values = list(stored)
    if len(values) == 1 and isinstance(values[0], (list, tuple)):
        values = list(values[0])
    if len(values) != 16:
        raise RuntimeError("Expected a 4x4 matrix: " + plug)
    for index in (12, 13, 14):
        values[index] *= factor
    locked = cmds.getAttr(plug, lock=True)
    if locked:
        cmds.setAttr(plug, lock=False)
    try:
        cmds.setAttr(plug, *values, type="matrix")
    finally:
        if locked:
            cmds.setAttr(plug, lock=True)


def convert_scene_copy():
    """Run only in the worker. Preserve dimensionless scale and skin weights."""
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    already_metric = scene_is_metric()
    factor = 1.0 if already_metric else FEET_TO_CENTIMETERS
    cmds.currentUnit(linear="cm")
    if factor != 1.0:
        curves = set()
        linear_attributes = [prefix + axis for prefix in (
            "translate", "rotatePivot", "scalePivot", "rotatePivotTranslate", "scalePivotTranslate")
            for axis in "XYZ"]
        for node in cmds.ls(type="transform", long=True) or []:
            for attribute in linear_attributes:
                plug = node + "." + attribute
                inputs = cmds.listConnections(plug, source=True, destination=False,
                                              skipConversionNodes=True) or []
                if inputs:
                    if len(inputs) != 1 or cmds.nodeType(inputs[0]) not in ("animCurveTL", "animCurveUL"):
                        raise RuntimeError("Bake connected translations before metric export: " + plug)
                    curves.add(inputs[0])
                    continue
                value = cmds.getAttr(plug)
                locked = cmds.getAttr(plug, lock=True)
                if locked:
                    cmds.setAttr(plug, lock=False)
                try:
                    cmds.setAttr(plug, value * factor)
                finally:
                    if locked:
                        cmds.setAttr(plug, lock=True)
            for attribute in ("offsetParentMatrix", "castRestPosition", "bindPose"):
                if cmds.attributeQuery(attribute, node=node, exists=True):
                    _matrix_translation(node + "." + attribute, factor)
        for curve in curves:
            cmds.scaleKey(curve, valueScale=factor, valuePivot=0.0)
        for shape in cmds.ls(type="mesh", long=True) or []:
            if cmds.connectionInfo(shape + ".inMesh", isDestination=True):
                history = cmds.listHistory(shape) or []
                if not any(cmds.nodeType(node) == "mesh" and not cmds.connectionInfo(
                        node + ".inMesh", isDestination=True) for node in history):
                    raise RuntimeError("Apply procedural mesh history before metric export: " + shape)
                continue
            selection = om.MSelectionList()
            selection.add(shape)
            mesh = om.MFnMesh(selection.getDagPath(0))
            points = mesh.getPoints(om.MSpace.kObject)
            mesh.setPoints(om.MPointArray([om.MPoint(p.x * factor, p.y * factor, p.z * factor, p.w)
                                          for p in points]), om.MSpace.kObject)
        for cluster in cmds.ls(type="skinCluster") or []:
            for index in cmds.getAttr(cluster + ".bindPreMatrix", multiIndices=True) or []:
                _matrix_translation("%s.bindPreMatrix[%d]" % (cluster, index), factor)
            _matrix_translation(cluster + ".geomMatrix", factor)
        for pose in cmds.ls(type="dagPose") or []:
            for attribute in ("worldMatrix", "xformMatrix"):
                for index in cmds.getAttr(pose + "." + attribute, multiIndices=True) or []:
                    _matrix_translation("%s.%s[%d]" % (pose, attribute, index), factor)
        for blend in cmds.ls(type="blendShape") or []:
            for target in cmds.getAttr(blend + ".inputTarget", multiIndices=True) or []:
                base = "%s.inputTarget[%d].inputTargetGroup" % (blend, target)
                for group in cmds.getAttr(base, multiIndices=True) or []:
                    items = "%s[%d].inputTargetItem" % (base, group)
                    for item in cmds.getAttr(items, multiIndices=True) or []:
                        plug = "%s[%d].inputPointsTarget" % (items, item)
                        points = cmds.getAttr(plug) or []
                        if points:
                            cmds.setAttr(plug, len(points), *[
                                (p[0] * factor, p[1] * factor, p[2] * factor, p[3]) for p in points], type="pointArray")
        cmds.dgdirty(allPlugs=True)
    cmds.currentUnit(linear="m")
    cmds.fileInfo(UNIT_KEY, "m")
    return {"enabled": True, "source_unit": "m" if already_metric else "ft",
            "output_unit": "m", "factor": 1.0 if already_metric else FEET_TO_METERS,
            "maya_internal_scale": factor, "already_metric": already_metric,
            "source_scene_preserved": True}


def export_copy(core, result, options, allocate=True):
    import maya.cmds as cmds
    core.validate_output_options(options)
    if allocate:
        core._allocate_result_output_paths(result, options.output_dir, options)
    executable = Path(sys.executable).with_name("mayapy.exe" if os.name == "nt" else "mayapy")
    if not executable.is_file():
        raise RuntimeError("Metric scene export requires Maya's mayapy executable: " + str(executable))
    original_selection = cmds.ls(selection=True, long=True) or []
    modified = cmds.file(query=True, modified=True)
    with tempfile.TemporaryDirectory(prefix="cod_metric_export_") as directory:
        folder = Path(directory)
        scene_path, request_path = folder / "source.ma", folder / "request.json"
        try:
            cmds.file(str(scene_path), force=True, type="mayaAscii", exportAll=True, options="v=0;")
        finally:
            cmds.select(original_selection, replace=True) if original_selection else cmds.select(clear=True)
            cmds.file(modified=modified)
        bind_path = ""
        if getattr(result, "_cast_bind_model", None) is not None:
            bind_path = str(folder / "bind.cast")
            result._cast_bind_model.save(bind_path)
        request = {"core": os.path.abspath(core.__file__), "scene": str(scene_path),
                   "result": asdict(result), "dual": isinstance(result, core.DualWieldResult),
                   "options": asdict(options), "bind": bind_path,
                   "bind_error": getattr(result, "_cast_bind_error", ""),
                   # The cached bind document is captured from the original
                   # ft-valued CAST assembly, even when a metric MA is reopened.
                   "bind_factor": getattr(result, "_cast_bind_to_meters", FEET_TO_METERS),
                   "frame": cmds.currentTime(query=True),
                   "up_axis": cmds.upAxis(query=True, axis=True),
                   "playback": {name: cmds.playbackOptions(query=True, **{name: True}) for name in
                                ("animationStartTime", "animationEndTime", "minTime", "maxTime")},
                   "response": str(folder / "response.json")}
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        core.log("Exporting metric scene copy (ft -> m)...")
        process = subprocess.run([str(executable), os.path.abspath(__file__), str(request_path)],
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 timeout=600,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        response_path = Path(request["response"])
        if process.returncode or not response_path.is_file():
            raise RuntimeError("Metric export worker failed:\n" + process.stdout.decode("utf-8", "replace")[-4000:])
        response = json.loads(response_path.read_text(encoding="utf-8"))
        for name in ("cast_verification", "smd_verification", "fbx_verification", "output_errors",
                     "unit_conversion", "warnings", "framerate"):
            setattr(result, name, response[name])
        result.frame_range = tuple(response["frame_range"])


def run_request(path):
    import maya.standalone
    maya.standalone.initialize(name="python")
    import maya.cmds as cmds
    try:
        request = json.loads(Path(path).read_text(encoding="utf-8"))
        cmds.loadPlugin(request["core"], quiet=True)
        core = next((module for module in tuple(sys.modules.values())
                    if getattr(module, "__file__", "") and os.path.normcase(os.path.abspath(module.__file__))
                    == os.path.normcase(request["core"])), None)
        if core is None:
            spec = importlib.util.spec_from_file_location("cod_metric_core", request["core"])
            core = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = core
            spec.loader.exec_module(core)
        cmds.file(request["scene"], open=True, force=True, prompt=False, executeScriptNodes=False)
        cmds.upAxis(axis=request["up_axis"], rotateView=False)
        cmds.playbackOptions(**request["playback"])
        cmds.currentTime(request["frame"])
        result_type = core.DualWieldResult if request["dual"] else core.AttachResult
        option_type = core.DualWieldOptions if request["dual"] else core.AttachOptions
        result = result_type(**request["result"])
        options = option_type(**request["options"])
        options.output_unit = "original"
        conversion = convert_scene_copy()
        result.unit_conversion = conversion
        core._OUTPUT_IN_METERS = True
        if options.export_fbx:
            core._ensure_fbx_exporter()
            core.mel.eval('FBXExportUpAxis ' + request["up_axis"])
        if result.animated_outputs:
            core._set_scene_animation_range(result.frame_range)
        if request["bind"]:
            serializer = sys.modules[core._castplugin_module().Cast.__module__]
            result._cast_bind_model = scale_cast(serializer.Cast.load(request["bind"]), serializer,
                model_factor=request["bind_factor"])
        if request["bind_error"]:
            result._cast_bind_error = request["bind_error"]
        core._write_result_outputs(result, options, allocate=False)
        Path(request["response"]).write_text(json.dumps(asdict(result), ensure_ascii=False), encoding="utf-8")
    finally:
        maya.standalone.uninitialize()


if __name__ == "__main__":
    run_request(sys.argv[1])
