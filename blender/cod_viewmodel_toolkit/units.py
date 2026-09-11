"""Metric export copies; source objects, actions and scene units are untouched."""

from contextlib import contextmanager
import json

import bpy

from .core import STATE_KEY, state_for

FEET_TO_METERS = 0.3048


def _copy_action(owner, root_factor):
    data = owner.animation_data
    if not data:
        return
    if data.drivers or data.nla_tracks:
        raise ValueError("Metric export requires a baked action without drivers or NLA tracks")
    if not data.action:
        return
    previous_slot = data.action_slot
    slot_index = list(data.action.slots).index(previous_slot) if previous_slot else None
    action = data.action.copy()
    data.action = action
    if slot_index is not None:
        data.action_slot = action.slots[slot_index]
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                for curve in bag.fcurves:
                    if curve.data_path in ("location", "scale") and root_factor != 1.0:
                        if curve.modifiers:
                            raise ValueError("Bake root transform-curve modifiers before metric export")
                        for key in curve.keyframe_points:
                            key.co.y *= root_factor
                            key.handle_left.y *= root_factor
                            key.handle_right.y *= root_factor
                        curve.update()


@contextmanager
def metric_copy(rig):
    from .exporting import assembly_objects
    source_scene = bpy.context.scene
    state = state_for(rig)
    already_metric = state.get("linear_unit") == "m"
    factor = 1.0 if already_metric else FEET_TO_METERS
    window = bpy.context.window
    pools = (bpy.data.objects, bpy.data.meshes, bpy.data.armatures, bpy.data.actions)
    snapshots = [set(pool) for pool in pools]
    scene = bpy.data.scenes.new("CoD Metric Export")
    scene.frame_start, scene.frame_end = source_scene.frame_start, source_scene.frame_end
    scene.render.fps, scene.render.fps_base = source_scene.render.fps, source_scene.render.fps_base
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
    try:
        mapping = {}
        for original in assembly_objects(rig):
            if original.constraints:
                raise ValueError("Bake object constraints before metric export")
            if original.type == "ARMATURE" and any(bone.constraints for bone in original.pose.bones):
                raise ValueError("Bake pose constraints before metric export")
            clone = original.copy()
            clone.data = original.data.copy()
            scene.collection.objects.link(clone)
            mapping[original] = clone
        for original, clone in mapping.items():
            if original.parent and original.parent not in mapping:
                raise ValueError("Metric export requires the assembly to have no external parent")
            clone.parent = mapping.get(original.parent)
            clone.matrix_parent_inverse = original.matrix_parent_inverse.copy()
            clone.matrix_basis = original.matrix_basis.copy()
            # Retain exact rest-bone bases. Armature.transform recomputes bone
            # roll from tiny head/tail differences and can change CoD poses.
            # A uniform assembly-object scale preserves skinning exactly.
            root_factor = factor if original.parent is None else 1.0
            clone.location *= root_factor
            clone.scale *= root_factor
            _copy_action(clone, root_factor)
            for modifier in clone.modifiers:
                if modifier.type == "ARMATURE":
                    modifier.object = mapping.get(modifier.object, modifier.object)
        converted = mapping[rig]
        state["linear_unit"] = "m"
        state["export_data_scale"] = state.get("export_data_scale", 1.0) * factor
        state["output_conversion"] = {
            "source_unit": "m" if already_metric else "ft",
            "output_unit": "m", "factor": factor,
            "already_metric": already_metric, "source_scene_preserved": True,
            "method": "uniform_assembly_scale", "export_data_scale": state["export_data_scale"]}
        converted[STATE_KEY] = json.dumps(state)
        if window:
            window.scene = scene
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            scene.frame_set(source_scene.frame_current)
            yield converted
    finally:
        if window:
            window.scene = source_scene
        bpy.data.scenes.remove(scene)
        for pool, before in zip(pools, snapshots):
            for item in set(pool) - before:
                if pool == bpy.data.objects:
                    pool.remove(item, do_unlink=True)
                else:
                    item.use_fake_user = False
                    if not item.users:
                        pool.remove(item)
