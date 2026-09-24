"""Blender-native panels and operators; no custom theme or fixed-pixel windows."""

from pathlib import Path
import textwrap

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy_extras.io_utils import ImportHelper

from . import core, exporting

_RUNNING = None


class CODVWT_Job(bpy.types.PropertyGroup):
    left: StringProperty(name="Animation / Left", subtype="FILE_PATH")
    right: StringProperty(name="Right Animation", subtype="FILE_PATH")


class CODVWT_Settings(bpy.types.PropertyGroup):
    mode: EnumProperty(name="Setup", items=(
        ("SINGLE", "Single Weapon", "Attach one weapon"),
        ("DUAL", "Dual Wield", "Duplicate the same weapon for left and right hands")))
    hands: StringProperty(name="Viewhands CAST", subtype="FILE_PATH",
                          description="CoD viewhands model, including the weapon attachment tags")
    weapon: StringProperty(name="Weapon CAST", subtype="FILE_PATH",
                           description="One CoD weapon model; dual wield imports it twice")
    left: StringProperty(name="Animation / Left", subtype="FILE_PATH",
                         description="Optional single animation or left-hand animation")
    right: StringProperty(name="Right Animation", subtype="FILE_PATH",
                          description="Right-hand animation; required with a left clip in Dual Wield")
    source_joint: StringProperty(name="Weapon Root", default="j_gun")
    target_joint: StringProperty(name="Viewhands Tag", default="tag_weapon")
    left_target: StringProperty(name="Left Tag", default="tag_weapon_left")
    right_target: StringProperty(name="Right Tag", default="tag_weapon_right")
    reference_pose: StringProperty(name="Reference Viewhands", subtype="FILE_PATH",
                                   description="Optional compatible rest pose for relative/additive tag translation")
    animation_mode: EnumProperty(name="Playback", items=(
        ("simultaneous", "Simultaneous", "Both sides play together; shared hand/root tracks use the right clip"),
        ("sequential", "Sequential", "Right clip starts after the left; each side holds its end pose")))
    directory: StringProperty(name="Default Output", subtype="DIR_PATH")
    output_unit: EnumProperty(name="Output Unit", items=(
        ("original", "Keep Original", "Do not convert output dimensions"),
        ("m", "Meters (Input: ft)", "Convert an export copy: 1 ft = 0.3048 m; keep the source scene unchanged")))
    blend: BoolProperty(name="Blender Scene (.blend)", default=True)
    cast: BoolProperty(name="CAST Model + Animation", default=True)
    fbx: BoolProperty(name="FBX Model + Animation", default=False)
    smd: BoolProperty(name="Source SMD", default=False)
    blend_dir: StringProperty(name="BLEND Folder", subtype="DIR_PATH")
    cast_dir: StringProperty(name="CAST Folder", subtype="DIR_PATH")
    fbx_dir: StringProperty(name="FBX Folder", subtype="DIR_PATH")
    smd_dir: StringProperty(name="SMD Folder", subtype="DIR_PATH")
    jobs: CollectionProperty(type=CODVWT_Job)
    job_index: IntProperty(default=0)
    status: StringProperty(name="Status", default="Ready", options={"SKIP_SAVE"})
    report: StringProperty(name="Last Report", subtype="FILE_PATH", options={"SKIP_SAVE"})


def build_settings(props):
    return core.BuildOptions(
        dual=props.mode == "DUAL", source_joint=props.source_joint,
        target_joint=props.target_joint, left_target=props.left_target,
        right_target=props.right_target, animation_mode=props.animation_mode,
        reference_pose=props.reference_pose)


def export_settings(props):
    return exporting.ExportOptions(
        directory=props.directory, blend=props.blend, cast=props.cast,
        fbx=props.fbx, smd=props.smd,
        output_unit=props.output_unit,
        folders={name: getattr(props, name + "_dir") for name in ("blend", "cast", "fbx", "smd")})


def available(context):
    return context.mode == "OBJECT" and _RUNNING is None


def feedback(operator, context, message, error=False):
    context.scene.cod_vwt.status = str(message)
    operator.report({"ERROR" if error else "INFO"}, str(message))
    return {"CANCELLED"} if error else {"FINISHED"}


class CODVWT_OT_preflight(bpy.types.Operator):
    bl_idname = "cod_vwt.preflight"
    bl_label = "Check Inputs"
    bl_description = "Check models, joints and animation compatibility without changing the scene"

    @classmethod
    def poll(cls, context):
        return available(context)

    def execute(self, context):
        p = context.scene.cod_vwt
        try:
            report = core.preflight(p.hands, p.weapon, build_settings(p), p.left,
                                    p.right if p.mode == "DUAL" else "")
            return feedback(self, context, "Inputs OK: %d hand bones, %d weapon bones" % (
                len(report["hands"]["bones"]), len(report["weapon"]["bones"])))
        except Exception as error:
            return feedback(self, context, error, True)


class CODVWT_OT_build(bpy.types.Operator):
    bl_idname = "cod_vwt.build"
    bl_label = "Build Assembly"
    bl_description = "Import hands then weapon into a new collection, attach at tag origins and apply optional animation"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return available(context)

    def execute(self, context):
        p = context.scene.cod_vwt
        try:
            rig = core.build(p.hands, p.weapon, build_settings(p), p.left,
                             p.right if p.mode == "DUAL" else "")
            return feedback(self, context, "Built %s; attachment translation verified" % rig.name)
        except Exception as error:
            return feedback(self, context, error, True)


class CODVWT_OT_apply(bpy.types.Operator):
    bl_idname = "cod_vwt.apply_animation"
    bl_label = "Apply Animation to Selected"
    bl_description = "Apply the animation fields to the selected toolkit rig without rebuilding its meshes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return available(context) and context.object and core.STATE_KEY in context.object

    def execute(self, context):
        p = context.scene.cod_vwt
        try:
            state = core.state_for(context.object)
            core.apply_animations(context.object, p.left, p.right if state["settings"]["dual"] else "")
            return feedback(self, context, "Animation applied; models preserved")
        except Exception as error:
            return feedback(self, context, error, True)


class CODVWT_OT_replace(bpy.types.Operator, ImportHelper):
    bl_idname = "cod_vwt.replace_clip"
    bl_label = "Replace Side Animation"
    bl_description = "Replace one side of the selected dual rig; keep the opposite clip and both models"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".cast"
    filter_glob: StringProperty(default="*.cast", options={"HIDDEN"})
    side: EnumProperty(items=(("left", "Left", "Left clip"), ("right", "Right", "Right clip")))

    @classmethod
    def poll(cls, context):
        if not available(context) or not context.object:
            return False
        try:
            return core.state_for(context.object)["settings"]["dual"]
        except ValueError:
            return False

    def execute(self, context):
        try:
            state = core.state_for(context.object)
            state[self.side] = self.filepath
            core.apply_animations(context.object, state["left"], state["right"])
            return feedback(self, context, self.side.title() + " clip replaced")
        except Exception as error:
            return feedback(self, context, error, True)


class CODVWT_OT_export(bpy.types.Operator):
    bl_idname = "cod_vwt.export"
    bl_label = "Export Selected Assembly"
    bl_description = "Export only the selected toolkit assembly, using versioned filenames and a JSON report"

    @classmethod
    def poll(cls, context):
        return available(context) and context.object and core.STATE_KEY in context.object

    def execute(self, context):
        try:
            result = exporting.export(context.object, export_settings(context.scene.cod_vwt))
            context.scene.cod_vwt.report = result["manifest"]
            return feedback(self, context, "Exported %d formats; report saved" % len(result["outputs"]))
        except Exception as error:
            return feedback(self, context, error, True)


class CODVWT_OT_add_files(bpy.types.Operator, ImportHelper):
    bl_idname = "cod_vwt.add_files"
    bl_label = "Add Animation Files"
    bl_description = "Select one or more CAST animation files for the single-weapon queue"
    filename_ext = ".cast"
    filter_glob: StringProperty(default="*.cast", options={"HIDDEN"})
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        props = context.scene.cod_vwt
        paths = [str(Path(self.directory) / file.name) for file in self.files] or [self.filepath]
        for path in paths:
            props.jobs.add().left = path
        return {"FINISHED"}


class CODVWT_OT_queue(bpy.types.Operator):
    bl_idname = "cod_vwt.queue"
    bl_label = "Edit Animation Queue"
    bl_description = "Add the current clip/pair, remove the selected row, or clear the queue"
    action: EnumProperty(items=(("ADD", "Add Current", "Add current animation fields"),
                                ("REMOVE", "Remove", "Remove selected row"),
                                ("CLEAR", "Clear", "Clear queue")))

    @classmethod
    def poll(cls, context):
        return _RUNNING is None

    def execute(self, context):
        p = context.scene.cod_vwt
        if self.action == "ADD":
            if not p.left or (p.mode == "DUAL" and not p.right):
                return feedback(self, context, "Select an animation, or both sides of a dual pair", True)
            job = p.jobs.add()
            job.left, job.right = p.left, p.right if p.mode == "DUAL" else ""
            p.job_index = len(p.jobs) - 1
        elif self.action == "REMOVE" and p.jobs:
            p.jobs.remove(min(p.job_index, len(p.jobs) - 1))
            p.job_index = max(0, min(p.job_index, len(p.jobs) - 1))
        elif self.action == "CLEAR":
            p.jobs.clear()
            p.job_index = 0
        return {"FINISHED"}


class CODVWT_UL_jobs(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        label = "%d. %s" % (index + 1, Path(item.left).name)
        if item.right:
            label += " | " + Path(item.right).name
        layout.label(text=label, icon="ACTION")


class CODVWT_OT_batch(bpy.types.Operator):
    bl_idname = "cod_vwt.batch"
    bl_label = "Start Batch Export"
    bl_description = "Export each queue item in isolation; failed items are reported and the queue continues"
    _timer = None

    @classmethod
    def poll(cls, context):
        return available(context) and bool(context.scene.cod_vwt.jobs)

    def execute(self, context):
        global _RUNNING
        p = context.scene.cod_vwt
        try:
            jobs = [(job.left, job.right) for job in p.jobs]
            if any(bool(right) != (p.mode == "DUAL") for _, right in jobs):
                raise ValueError("Queue rows must match Single Weapon or Dual Wield mode")
            self.runner = exporting.Batch(p.hands, p.weapon, jobs,
                                           build_settings(p), export_settings(p))
        except Exception as error:
            return feedback(self, context, error, True)
        _RUNNING = self.runner
        p.status = "Starting batch..."
        context.window_manager.cod_vwt_progress = 0
        if bpy.app.background:
            while not self.runner.done:
                self.runner.step()
            return self._finish(context)
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _finish(self, context):
        global _RUNNING
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        try:
            context.scene.cod_vwt.report = self.runner.finish()
            failures = sum(item["status"] != "ok" for item in self.runner.items)
            return feedback(self, context, "%s: %d completed, %d failed" % (
                "Stopped" if self.runner.cancelled else "Batch finished",
                len(self.runner.items), failures))
        except Exception as error:
            return feedback(self, context, error, True)
        finally:
            _RUNNING = None

    def modal(self, context, event):
        if event.type == "ESC":
            self.runner.cancelled = True
        if self.runner.done:
            return self._finish(context)
        if event.type == "TIMER" and event.timer == self._timer:
            result = self.runner.step()
            count = len(self.runner.items)
            context.window_manager.cod_vwt_progress = count / len(self.runner.jobs)
            context.scene.cod_vwt.status = "%d / %d: %s" % (count, len(self.runner.jobs), result["status"])
            for area in context.screen.areas:
                area.tag_redraw()
        return {"PASS_THROUGH"}

    def cancel(self, context):
        self.runner.cancelled = True
        self._finish(context)


class CODVWT_OT_stop(bpy.types.Operator):
    bl_idname = "cod_vwt.stop"
    bl_label = "Stop After Current"
    bl_description = "Stop the queue after the current item finishes; completed files are preserved"

    @classmethod
    def poll(cls, context):
        return _RUNNING is not None

    def execute(self, context):
        _RUNNING.cancelled = True
        return {"FINISHED"}


def message(layout, context, text):
    width = max(22, int((context.region.width - 36) /
                       (7 * context.preferences.system.ui_scale)))
    for line in textwrap.wrap(text, width=width):
        layout.label(text=line)


def file_field(layout, props, name, label=None):
    layout.label(text=label or props.bl_rna.properties[name].name)
    layout.prop(props, name, text="")


class CODVWT_PT_main(bpy.types.Panel):
    bl_label = "CoD Viewmodel Toolkit 3.5.0"
    bl_idname = "CODVWT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Viewmodel"

    def draw(self, context):
        layout, p = self.layout, context.scene.cod_vwt
        fields = layout.column()
        fields.enabled = _RUNNING is None
        fields.prop(p, "mode", expand=True)
        file_field(fields, p, "hands")
        file_field(fields, p, "weapon")
        fields.separator()
        file_field(fields, p, "left", "Left Animation" if p.mode == "DUAL" else "Animation (Optional)")
        if p.mode == "DUAL":
            file_field(fields, p, "right")
            fields.prop(p, "animation_mode")
        fields.operator("cod_vwt.preflight", icon="CHECKMARK")
        fields.operator("cod_vwt.build", icon="ARMATURE_DATA")
        message(layout, context, "Creates a new collection. Existing scene objects are preserved.")
        box = layout.box()
        message(box, context, p.status)


class CODVWT_PT_mapping(bpy.types.Panel):
    bl_label = "Joint Mapping & Reference Pose"
    bl_parent_id = "CODVWT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout, p = self.layout, context.scene.cod_vwt
        layout.enabled = _RUNNING is None
        layout.prop(p, "source_joint")
        if p.mode == "DUAL":
            layout.prop(p, "left_target")
            layout.prop(p, "right_target")
        else:
            layout.prop(p, "target_joint")
        file_field(layout, p, "reference_pose")


class CODVWT_PT_output(bpy.types.Panel):
    bl_label = "Output Files"
    bl_parent_id = "CODVWT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    def draw(self, context):
        layout, p = self.layout, context.scene.cod_vwt
        layout.enabled = _RUNNING is None
        file_field(layout, p, "directory")
        layout.prop(p, "output_unit", text="Unit")
        if p.output_unit == "m":
            message(layout, context, "Export copy only: 1 ft = 0.3048 m. Already-metric assemblies are not scaled again.")
        for extension in ("blend", "cast", "fbx", "smd"):
            layout.prop(p, extension)
            row = layout.row()
            row.enabled = getattr(p, extension)
            row.prop(p, extension + "_dir", text="Folder")
        message(layout, context, "Blank format folders use Default Output. Animated SMD contains bones only.")
        if p.fbx:
            message(layout, context, "FBX: enable Dual Quaternion / Preserve Volume skinning in the receiving app.")
        layout.operator("cod_vwt.export", icon="EXPORT")


class CODVWT_PT_batch(bpy.types.Panel):
    bl_label = "Animation Batch"
    bl_parent_id = "CODVWT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout, p = self.layout, context.scene.cod_vwt
        content = layout.column()
        content.enabled = _RUNNING is None
        if p.mode == "SINGLE":
            content.operator("cod_vwt.add_files", icon="FILEBROWSER")
        content.operator("cod_vwt.queue", text="Add Current Pair" if p.mode == "DUAL" else "Add Current Animation",
                         icon="ADD").action = "ADD"
        if p.jobs:
            content.template_list("CODVWT_UL_jobs", "", p, "jobs", p, "job_index", rows=4)
            job = p.jobs[min(p.job_index, len(p.jobs) - 1)]
            file_field(content, job, "left")
            if p.mode == "DUAL":
                file_field(content, job, "right")
            row = content.row()
            row.operator("cod_vwt.queue", text="Remove", icon="REMOVE").action = "REMOVE"
            row.operator("cod_vwt.queue", text="Clear").action = "CLEAR"
        else:
            message(content, context, "Queue is empty. Add animation files or an explicit left/right pair.")
        layout.operator("cod_vwt.batch", icon="PLAY")
        layout.operator("cod_vwt.stop", icon="CANCEL")
        if _RUNNING:
            layout.progress(factor=context.window_manager.cod_vwt_progress, type="BAR", text="Batch progress")
        if p.report:
            layout.operator("wm.path_open", text="Open Last Report", icon="TEXT").filepath = p.report


class CODVWT_PT_scene(bpy.types.Panel):
    bl_label = "Selected Assembly"
    bl_parent_id = "CODVWT_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        self.layout.operator("cod_vwt.apply_animation", icon="ACTION")
        row = self.layout.row()
        row.operator("cod_vwt.replace_clip", text="Replace Left").side = "left"
        row.operator("cod_vwt.replace_clip", text="Replace Right").side = "right"


CLASSES = (CODVWT_Job, CODVWT_Settings, CODVWT_OT_preflight, CODVWT_OT_build,
           CODVWT_OT_apply, CODVWT_OT_replace, CODVWT_OT_export, CODVWT_OT_add_files,
           CODVWT_OT_queue, CODVWT_UL_jobs, CODVWT_OT_batch, CODVWT_OT_stop,
           CODVWT_PT_main, CODVWT_PT_mapping, CODVWT_PT_output, CODVWT_PT_batch, CODVWT_PT_scene)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cod_vwt = PointerProperty(type=CODVWT_Settings)
    bpy.types.WindowManager.cod_vwt_progress = FloatProperty(default=0, min=0, max=1, options={"SKIP_SAVE"})


def unregister():
    global _RUNNING
    if _RUNNING:
        raise RuntimeError("Stop the batch before disabling CoD Viewmodel Toolkit")
    del bpy.types.WindowManager.cod_vwt_progress
    del bpy.types.Scene.cod_vwt
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
