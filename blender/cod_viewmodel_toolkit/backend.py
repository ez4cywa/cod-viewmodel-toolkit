"""CoD toolkit adapter to pinned upstream CAST; never uses Maya/global operators."""

import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import bpy

_BACKEND = None


def backend():
    global _BACKEND
    if _BACKEND is None:
        directory = Path(__file__).resolve().parent / "vendor_cast"
        serializer = directory / "cast.py"
        if not directory.is_dir():
            root = Path(__file__).resolve().parents[2]
            directory = root / "third_party" / "cast_blender"
            serializer = root / "third_party" / "cast" / "cast.py"
        name = __package__ + ".vendor_cast"
        # Do not run upstream register(): an independently installed CAST add-on
        # may already own import_scene.cast and export_scene.cast. Import the
        # same implementation directly so failures cannot be reported as success.
        package = ModuleType(name)
        package.__path__ = [str(directory)]
        sys.modules[name] = package
        spec = importlib.util.spec_from_file_location(name + ".cast", serializer)
        cast = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cast
        spec.loader.exec_module(cast)
        if not hasattr(bpy.types.PoseBone, "cast_bind_pose_scale"):
            bpy.types.PoseBone.cast_bind_pose_scale = bpy.props.FloatVectorProperty(
                name="Cast bind pose scale", default=(1.0, 1.0, 1.0))
        _BACKEND = SimpleNamespace(
            cast=cast,
            importer=importlib.import_module(name + ".import_cast"),
            exporter=importlib.import_module(name + ".export_cast"))
    return _BACKEND


def options(warnings=None, **overrides):
    def report(levels, message):
        if "ERROR" in levels:
            raise RuntimeError(message)
        if warnings is not None:
            warnings.append(str(message))

    values = dict(
        import_time=False, import_reset=True, import_skin=True,
        import_ik=False, import_constraints=False, import_blend_shapes=True,
        import_hair=False, import_merge=False, create_hair_type="curve",
        create_hair_subtype="bevel", report=report,
        export_selected=True, incl_model=True, incl_animation=False,
        incl_notetracks=True, is_looped=False, scale=1.0, up_axis="z",
        bl_version=(2, 0, 0))
    values.update(overrides)
    return SimpleNamespace(**values)


def select(obj):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
