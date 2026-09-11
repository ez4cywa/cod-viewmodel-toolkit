"""Scoped CoD exports and batches; no scene resets or preference writes."""

from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import re
import tempfile

import bpy

from .backend import backend, options, select
from .core import BuildOptions, VERSION, build, preflight, state_for, verify


@dataclass
class ExportOptions:
    directory: str = ""
    blend: bool = True
    cast: bool = True
    fbx: bool = False
    smd: bool = False
    folders: dict = field(default_factory=dict)
    output_unit: str = "original"


def _folder(path):
    if not str(path).strip():
        raise ValueError("Choose an output directory")
    folder = Path(bpy.path.abspath(str(path))).expanduser().resolve()
    if folder.exists() and not folder.is_dir():
        raise ValueError("Output path is not a directory: %s" % folder)
    return folder


def output_plan(settings, stem):
    if settings.output_unit not in ("original", "m"):
        raise ValueError("Output unit must be original or m")
    default = _folder(settings.directory)
    folders = {extension: _folder(settings.folders.get(extension) or str(default))
               for extension in ("blend", "cast", "fbx", "smd")
               if getattr(settings, extension)}
    if not folders:
        raise ValueError("Select at least one export format")
    folders["json"] = default
    stem = re.sub(r'[^A-Za-z0-9_.-]+', '_', stem).strip(' ._') or "viewmodel"
    stem = stem[:100]
    for number in range(1, 100000):
        name = "%s_%03d" % (stem, number)
        paths = {key: directory / (name + "." + key) for key, directory in folders.items()}
        if not any(path.exists() for path in paths.values()):
            return paths
    raise ValueError("Too many existing output versions for %s" % stem)


def assembly_objects(rig):
    return [rig] + [obj for obj in bpy.context.scene.objects
                   if obj.type == "MESH" and any(mod.type == "ARMATURE" and mod.object == rig
                                                 for mod in obj.modifiers)]


def _blend(rig, path):
    source = bpy.context.scene
    export_scene = bpy.data.scenes.new("CoD Viewmodel")
    try:
        for obj in assembly_objects(rig):
            export_scene.collection.objects.link(obj)
        export_scene.frame_start, export_scene.frame_end = source.frame_start, source.frame_end
        export_scene.render.fps, export_scene.render.fps_base = source.render.fps, source.render.fps_base
        for name in ("system", "scale_length", "length_unit"):
            setattr(export_scene.unit_settings, name, getattr(source.unit_settings, name))
        export_scene.frame_set(source.frame_current)
        bpy.data.libraries.write(str(path), {export_scene}, path_remap="RELATIVE_ALL", fake_user=True)
    finally:
        bpy.data.scenes.remove(export_scene)


def _smd(rig, path, animated):
    distance_scale = state_for(rig).get("export_data_scale", 1.0)
    bones = []

    def visit(bone):
        bones.append(bone)
        for child in bone.children:
            visit(child)

    for bone in rig.data.bones:
        if not bone.parent:
            visit(bone)
    indices = {bone.name: index for index, bone in enumerate(bones)}
    lines = ["version 1", "nodes"]
    for bone in bones:
        lines.append('%d "%s" %d' % (indices[bone.name], bone.name,
                                     indices[bone.parent.name] if bone.parent else -1))
    lines.extend(("end", "skeleton"))
    scene = bpy.context.scene
    frames = range(scene.frame_start, scene.frame_end + 1) if animated else (scene.frame_start,)
    for frame in frames:
        scene.frame_set(frame)
        lines.append("time %d" % (frame - scene.frame_start))
        for bone in bones:
            pose = rig.pose.bones[bone.name]
            matrix = pose.parent.matrix.inverted() @ pose.matrix if pose.parent else pose.matrix
            position, rotation = matrix.translation * distance_scale, matrix.to_euler("XYZ")
            lines.append("%d %.9g %.9g %.9g %.9g %.9g %.9g" % (
                indices[bone.name], *position, *rotation))
    lines.append("end")
    if not animated:
        lines.append("triangles")
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in assembly_objects(rig)[1:]:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles()
                transform = rig.matrix_world.inverted() @ obj.matrix_world
                normal_transform = transform.to_3x3().inverted().transposed()
                uv = mesh.uv_layers.active
                for triangle in mesh.loop_triangles:
                    material = mesh.materials[triangle.material_index] if mesh.materials else None
                    lines.append(re.sub(r'\s+', '_', material.name) if material else "default")
                    for loop_index in triangle.loops:
                        vertex = mesh.vertices[mesh.loops[loop_index].vertex_index]
                        position = (transform @ vertex.co) * distance_scale
                        normal = (normal_transform @ mesh.corner_normals[loop_index].vector).normalized()
                        texture = uv.data[loop_index].uv if uv else (0.0, 0.0)
                        weights = [(indices[obj.vertex_groups[group.group].name], group.weight)
                                   for group in vertex.groups
                                   if obj.vertex_groups[group.group].name in indices and group.weight > 1e-7]
                        total = sum(weight for _, weight in weights)
                        weights = [(bone, weight / total) for bone, weight in weights] if total else [(0, 1.0)]
                        links = " ".join("%d %.9g" % pair for pair in weights)
                        lines.append("%d %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d %s" % (
                            weights[0][0], *position, *normal, *texture, len(weights), links))
            finally:
                evaluated.to_mesh_clear()
        lines.append("end")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export(rig, settings, stem="viewmodel"):
    if settings.output_unit == "m":
        output_plan(settings, stem)
        from .units import metric_copy
        with metric_copy(rig) as converted:
            return export(converted, replace(settings, output_unit="original"), stem)
    verification = verify(rig)
    paths = output_plan(settings, stem)
    state = state_for(rig)
    scene = bpy.context.scene
    selected, active, frame = list(bpy.context.selected_objects), bpy.context.object, scene.frame_current
    animated = bool(rig.animation_data and rig.animation_data.action)
    old_range = (scene.frame_start, scene.frame_end)
    if animated and state.get("frame_range"):
        scene.frame_start, scene.frame_end = state["frame_range"]
    else:
        scene.frame_start = scene.frame_end = 0
    outputs = {}
    try:
        for extension, destination in paths.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            if extension == "json":
                continue
            select(rig)
            scene.frame_set(scene.frame_start)
            # Stage in the same directory so relative texture references remain
            # valid after renaming the completed file.
            handle, temporary = tempfile.mkstemp(prefix=".cod-export-", suffix="." + extension,
                                                 dir=str(destination.parent))
            os.close(handle)
            staged = Path(temporary)
            try:
                if extension == "blend":
                    _blend(rig, staged)
                elif extension == "cast":
                    backend().exporter.save(options(incl_animation=animated,
                        scale=state.get("export_data_scale", 1.0)), bpy.context, str(staged))
                elif extension == "fbx":
                    for obj in assembly_objects(rig):
                        obj.select_set(True)
                    from .fbx import stable_fbx_rotation
                    with stable_fbx_rotation():
                        result = bpy.ops.export_scene.fbx(
                            filepath=str(staged), use_selection=True, object_types={"ARMATURE", "MESH"},
                            add_leaf_bones=False, use_armature_deform_only=False,
                            bake_anim=animated, bake_anim_use_all_actions=False,
                            bake_anim_use_nla_strips=False, bake_anim_simplify_factor=0.0,
                            path_mode="AUTO", axis_forward="-Z", axis_up="Y",
                            **({"apply_scale_options": "FBX_SCALE_UNITS"} if state.get("linear_unit") == "m" else {}))
                    if result != {"FINISHED"}:
                        raise RuntimeError("FBX export was cancelled")
                elif extension == "smd":
                    _smd(rig, staged, animated)
                if not staged.is_file() or staged.stat().st_size == 0:
                    raise RuntimeError("Exporter did not write a valid file: " + extension)
                if destination.exists():
                    raise FileExistsError("Output appeared during export: %s" % destination)
                os.rename(str(staged), str(destination))
                outputs[extension] = str(destination)
            finally:
                if staged.exists():
                    staged.unlink()
        report = {"tool": "CoD Viewmodel Toolkit", "version": VERSION,
                  "blender": bpy.app.version_string, "cast_upstream": "2.00",
                  "verification": verification, "assembly": state,
                  "linear_unit": state.get("linear_unit", "original"),
                  "unit_conversion": state.get("output_conversion", {"enabled": False}),
                  "animated": animated, "frame_range": [scene.frame_start, scene.frame_end],
                  "fps": scene.render.fps / scene.render.fps_base,
                  "outputs": outputs, "smd": "skeleton animation" if animated else "static skinned model"}
        with paths["json"].open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        return {"status": "ok", "manifest": str(paths["json"]), **report}
    finally:
        select(rig)
        rig.select_set(False)
        for obj in selected:
            if obj.name in scene.objects:
                obj.select_set(True)
        if active and active.name in scene.objects:
            bpy.context.view_layer.objects.active = active
        scene.frame_start, scene.frame_end = old_range
        scene.frame_set(frame)


class Batch:
    """One synchronous item per step, usable by CLI or a cancellable UI timer."""

    def __init__(self, hands, weapon, jobs, build_options, export_options):
        preflight(hands, weapon, build_options)
        output_plan(export_options, "batch")
        self.hands, self.weapon = hands, weapon
        self.jobs = list(jobs)
        if not self.jobs:
            raise ValueError("Add animation files to the queue")
        self.build_options, self.export_options = build_options, export_options
        self.items, self.cancelled = [], False
        self.report_path = None

    @property
    def done(self):
        return self.cancelled or len(self.items) >= len(self.jobs)

    def step(self):
        if self.done:
            return None
        job = self.jobs[len(self.items)]
        scene = bpy.context.scene
        frame, first, last = scene.frame_current, scene.frame_start, scene.frame_end
        fps, base = scene.render.fps, scene.render.fps_base
        selected, active = list(bpy.context.selected_objects), bpy.context.object
        pools = (bpy.data.objects, bpy.data.collections, bpy.data.actions,
                 bpy.data.meshes, bpy.data.armatures, bpy.data.materials, bpy.data.images)
        snapshots = [set(pool) for pool in pools]
        try:
            left, right = job
            rig = build(self.hands, self.weapon, self.build_options, left, right)
            stem = Path(left).stem + ("__" + Path(right).stem if right else "")
            result = export(rig, self.export_options, stem)
            result["inputs"] = [left, right]
        except Exception as error:
            result = {"status": "failed", "inputs": list(job), "error": str(error)}
        finally:
            if bpy.context.object and bpy.context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            for pool, before in zip(pools, snapshots):
                for item in set(pool) - before:
                    if pool == bpy.data.objects:
                        pool.remove(item, do_unlink=True)
                    elif pool == bpy.data.collections or not item.users or (
                            pool == bpy.data.actions and item.use_fake_user):
                        pool.remove(item)
            scene.frame_start, scene.frame_end = first, last
            scene.render.fps, scene.render.fps_base = fps, base
            scene.frame_set(frame)
            for obj in selected:
                if obj.name in scene.objects:
                    obj.select_set(True)
            if active and active.name in scene.objects:
                bpy.context.view_layer.objects.active = active
        self.items.append(result)
        return result

    def finish(self):
        if self.report_path:
            return self.report_path
        paths = output_plan(self.export_options, "batch_report")
        destination = paths["json"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            json.dump({"version": VERSION, "total": len(self.jobs),
                       "completed": len(self.items), "cancelled": self.cancelled,
                       "items": self.items}, stream, ensure_ascii=False, indent=2)
        self.report_path = str(destination)
        return self.report_path
