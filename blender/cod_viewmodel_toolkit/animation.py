"""Import CoD clips through CAST, then compose local poses by bone ownership."""

import json

import bpy
from mathutils import Matrix, Vector

from .backend import backend, options, select
from .core import STATE_KEY, BuildOptions, _side, animation_inventory, state_for, verify


def _route(state, side):
    result = {name.casefold(): name for name in state["hands"]["bones"]}
    for raw, name in state["mapping"][side].items():
        # A shared j_gun animation belongs to viewhands, never the attached
        # weapon root. Other overlaps were rejected by model preflight.
        result.setdefault(raw.casefold(), name)
    return result


def _sample(rig, inventory, state, side, warnings):
    animation = inventory["animation"]
    cast = backend().cast
    route = _route(state, side)
    source = state["mapping"][side][state["settings"]["source_joint"]]
    kept, count = [], 0
    for node in animation.childNodes:
        if isinstance(node, (cast.Curve, cast.CurveModeOverride)):
            destination = route.get((node.NodeName() or "").casefold())
            if not destination:
                if isinstance(node, cast.Curve):
                    warnings.append("Skipped unmatched track: " + str(node.NodeName()))
                continue
            if isinstance(node, cast.Curve):
                if destination == source and node.KeyPropertyName() in ("tx", "ty", "tz"):
                    continue
                if node.KeyPropertyName() == "bs":
                    warnings.append("Blend-shape animation is not included in skeletal composition")
                    continue
                count += 1
            node.SetNodeName(destination)
        kept.append(node)
    if not count:
        raise ValueError("No animation tracks match this assembly")
    animation.childNodes = kept
    select(rig)
    backend().importer.importAnimationNode(options(warnings), animation,
                                           inventory["path"], rig)
    imported_action = rig.animation_data.action
    samples = []
    for frame in range(inventory["end"] + 1):
        bpy.context.scene.frame_set(frame)
        samples.append({bone.name: bone.matrix_basis.copy() for bone in rig.pose.bones})
    # Reference compensation is applied in the target parent's local axes,
    # transformed back to Blender's post-rest pose axes.
    reference = state.get("reference")
    settings = BuildOptions(**state["settings"])
    if reference:
        targets = (settings.left_target, settings.right_target) if settings.dual else (settings.target_joint,)
        curve_groups = {}
        for curve in animation.Curves():
            curve_groups.setdefault(curve.NodeName(), []).append(curve)
        for target in targets:
            offset = Vector(reference["bones"][target]["position"]) - Vector(
                state["hands"]["bones"][target]["position"])
            curves = curve_groups.get(target, [])
            axes = [False, False, False]
            for curve in curves:
                if curve.KeyPropertyName() not in ("tx", "ty", "tz"):
                    continue
                mode = backend().importer.utilityResolveCurveModeOverride(
                    rig.pose.bones[target], curve.Mode(), animation.CurveModeOverrides(),
                    isTranslate=True)
                if mode in ("relative", "additive"):
                    axes[("tx", "ty", "tz").index(curve.KeyPropertyName())] = True
            delta = Vector(tuple(offset[i] if axes[i] else 0 for i in range(3)))
            bone = rig.data.bones[target]
            local = bone.parent.matrix_local.inverted() @ bone.matrix_local if bone.parent else bone.matrix_local
            delta = local.to_3x3().inverted() @ delta
            for sample in samples:
                sample[target].translation += delta
    rig.animation_data.action = None
    imported_action.use_fake_user = False
    if not imported_action.users:
        bpy.data.actions.remove(imported_action)
    return samples


def _write_action(rig, samples, name, notifications):
    action = bpy.data.actions.new(name)
    rig.animation_data_create()
    rig.animation_data.action = action
    rig.animation_data.action_slot = action.slots.new(id_type="OBJECT", name="CoD Viewmodel")
    for bone in rig.pose.bones:
        bone.rotation_mode = "QUATERNION"
        values = [sample[bone.name].decompose() for sample in samples]
        # Equivalent quaternions must stay on the same hemisphere for linear
        # component interpolation and predictable downstream FBX/CAST playback.
        for index in range(1, len(values)):
            if values[index - 1][1].dot(values[index][1]) < 0:
                values[index][1].negate()
        for prop, component_count, column in (("location", 3, 0),
                                               ("rotation_quaternion", 4, 1),
                                               ("scale", 3, 2)):
            for axis in range(component_count):
                curve = action.fcurve_ensure_for_datablock(
                    rig, bone.path_from_id(prop), index=axis, group_name=bone.name)
                curve.keyframe_points.add(len(samples))
                coordinates = [value for frame, row in enumerate(values)
                               for value in (frame, row[column][axis])]
                curve.keyframe_points.foreach_set("co", coordinates)
                for key in curve.keyframe_points:
                    key.interpolation = "LINEAR"
                curve.update()
    for label, frame in notifications:
        marker = action.pose_markers.new(label)
        marker.frame = frame
    return action


def compose(rig, left, right=""):
    state = state_for(rig)
    settings = BuildOptions(**state["settings"])
    if settings.dual and not right:
        raise ValueError("A dual assembly needs both animation files")
    if not settings.dual and right:
        raise ValueError("A single assembly accepts one animation")
    inventories = {"left" if settings.dual else "single": animation_inventory(left)}
    if settings.dual:
        inventories["right"] = animation_inventory(right)
        if abs(inventories["left"]["fps"] - inventories["right"]["fps"]) > 1e-6:
            raise ValueError("Left/right animation frame rates differ")
    scene = bpy.context.scene
    old_timing = (scene.frame_start, scene.frame_end, scene.frame_current,
                  scene.render.fps, scene.render.fps_base)
    old_action = rig.animation_data.action if rig.animation_data else None
    old_slot = rig.animation_data.action_slot if rig.animation_data else None
    old_basis = {bone.name: bone.matrix_basis.copy() for bone in rig.pose.bones}
    actions_before = set(bpy.data.actions)
    warnings = []
    try:
        samples = {side: _sample(rig, inventory, state, side, warnings)
                   for side, inventory in inventories.items()}
        result, notifications = [], []
        if not settings.dual:
            result = samples["single"]
        else:
            left_end, right_end = inventories["left"]["end"], inventories["right"]["end"]
            offset = left_end + 1 if settings.animation_mode == "sequential" else 0
            end = offset + right_end if offset else max(left_end, right_end)
            left_names = {name for name in state["hands"]["bones"]
                          if _side(name, state["hands"]["bones"]) == "left"}
            right_names = {name for name in state["hands"]["bones"]
                           if _side(name, state["hands"]["bones"]) == "right"}
            left_names.update(state["mapping"]["left"].values())
            right_names.update(state["mapping"]["right"].values())
            for frame in range(end + 1):
                left_pose = samples["left"][min(frame, left_end)]
                right_pose = samples["right"][max(0, min(frame - offset, right_end))]
                shared_pose = left_pose if offset and frame < offset else right_pose
                result.append({name: (left_pose if name in left_names else
                                      right_pose if name in right_names else shared_pose)[name]
                               for name in rig.pose.bones.keys()})
        for side, inventory in inventories.items():
            offset = (inventories["left"]["end"] + 1
                      if side == "right" and settings.animation_mode == "sequential" else 0)
            for track in inventory["animation"].Notifications():
                notifications.extend((side + ":" + track.Name(), frame + offset)
                                     for frame in track.KeyFrameBuffer())
        # Translation locking is explicit even on unkeyed attachment roots.
        for sample in result:
            for mapping in state["mapping"].values():
                sample[mapping[settings.source_joint]].translation = (0, 0, 0)
        action = _write_action(rig, result, "CoD Viewmodel Animation", notifications)
        fps = next(iter(inventories.values()))["fps"]
        nominal_fps = max(1, round(fps))
        scene.render.fps, scene.render.fps_base = nominal_fps, nominal_fps / fps
        scene.frame_start, scene.frame_end = 0, len(result) - 1
        scene.frame_set(0)
        verify(rig)
        state.update(left=str(left), right=str(right),
                     frame_range=[0, len(result) - 1], fps=fps,
                     warnings=sorted(set(state.get("warnings", []) + warnings)))
        rig[STATE_KEY] = json.dumps(state)
        return action
    except Exception:
        if rig.animation_data:
            rig.animation_data.action = old_action
            if old_action:
                rig.animation_data.action_slot = old_slot
        for bone in rig.pose.bones:
            bone.matrix_basis = old_basis[bone.name]
        scene.frame_start, scene.frame_end, frame, scene.render.fps, scene.render.fps_base = old_timing
        scene.frame_set(frame)
        for action in set(bpy.data.actions) - actions_before:
            action.use_fake_user = False
            if not action.users:
                bpy.data.actions.remove(action)
        raise
