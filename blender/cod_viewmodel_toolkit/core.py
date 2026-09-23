"""CoD CAST assembly and routed animation workflows for Blender 5.2.

Public operations preflight before changing a scene. Assemblies live in a
dedicated collection; no operation clears the user's scene or preferences.
"""

from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
import uuid

import bpy
from mathutils import Matrix, Vector

from .backend import backend, options as cast_options, select

VERSION = "3.4.2"
STATE_KEY = "vwt_assembly"


@dataclass
class BuildOptions:
    dual: bool = False
    source_joint: str = "j_gun"
    target_joint: str = "tag_weapon"
    left_target: str = "tag_weapon_left"
    right_target: str = "tag_weapon_right"
    animation_mode: str = "simultaneous"
    reference_pose: str = ""


def cast_path(path):
    path = Path(bpy.path.abspath(str(path))).expanduser().resolve()
    if path.suffix.lower() != ".cast" or not path.is_file():
        raise ValueError("Select an existing CAST file: %s" % path)
    return path


def _read(path):
    cast = backend().cast
    loaded = cast.Cast.load(str(cast_path(path)))
    return loaded, [child for root in loaded.Roots() for child in root.childNodes]


def model_inventory(path):
    loaded, nodes = _read(path)
    cast = backend().cast
    models = [node for node in nodes if isinstance(node, cast.Model)]
    if len(models) != 1 or not models[0].Skeleton():
        raise ValueError("Each model input must contain exactly one skinned skeleton")
    if any(isinstance(node, (cast.Animation, cast.Instance)) for node in nodes):
        raise ValueError("Use a model-only CAST input (no animation or world instances)")
    model = models[0]
    bones = model.Skeleton().Bones()
    records, folded = {}, set()
    for index, bone in enumerate(bones):
        name = bone.Name()
        if not name or len(name.encode("utf-8")) > 63 or any(c in name for c in ('"', '\\', '\n', '\r', '\x00')):
            raise ValueError("Unsupported Blender/CAST bone name: %r" % name)
        if name.casefold() in folded:
            raise ValueError("Ambiguous case-insensitive joint name: %s" % name)
        folded.add(name.casefold())
        parent = bone.ParentIndex()
        if parent < -1 or parent >= len(bones) or parent == index:
            raise ValueError("Invalid parent index for %s" % name)
        position = tuple(bone.LocalPosition() or (0, 0, 0))
        rotation = tuple(bone.LocalRotation() or (0, 0, 0, 1))
        if not all(math.isfinite(x) for x in position + rotation):
            raise ValueError("Non-finite rest transform: %s" % name)
        records[name] = {"parent": bones[parent].Name() if parent >= 0 else None,
                         "position": position, "rotation": rotation}
    for name in records:
        visited, current = set(), name
        while current:
            if current in visited:
                raise ValueError("Skeleton cycle at %s" % name)
            visited.add(current)
            current = records[current]["parent"]
    if not records:
        raise ValueError("Model has no joints")
    return {"path": str(cast_path(path)), "bones": records,
            "mesh_count": len(model.Meshes())}


def animation_inventory(path):
    _, nodes = _read(path)
    cast = backend().cast
    if any(isinstance(node, (cast.Model, cast.Instance)) for node in nodes):
        raise ValueError("Choose an animation-only CAST file")
    animations = [node for node in nodes if isinstance(node, cast.Animation)]
    if len(animations) != 1:
        raise ValueError("Expected exactly one animation in %s" % path)
    animation = animations[0]
    fps = float(animation.Framerate())
    if not math.isfinite(fps) or fps <= 0 or fps > 240:
        raise ValueError("Animation frame rate must be between 0 and 240")
    frames, identities = [], set()
    for curve in animation.Curves():
        if not curve.NodeName() or curve.KeyPropertyName() not in (
                "tx", "ty", "tz", "rq", "sx", "sy", "sz", "bs"):
            raise ValueError("Unsupported or unnamed animation track")
        key = (curve.NodeName().casefold(), curve.KeyPropertyName())
        if key in identities:
            raise ValueError("Duplicate animation track: %s %s" % key)
        identities.add(key)
        keys, values = list(curve.KeyFrameBuffer() or []), list(curve.KeyValueBuffer() or [])
        components = 4 if curve.KeyPropertyName() == "rq" else 1
        if not keys or len(values) != len(keys) * components:
            raise ValueError("Malformed animation track: %s" % (key,))
        if keys != sorted(set(keys)) or min(keys) < 0:
            raise ValueError("Animation frames must be unique, sorted and nonnegative")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Non-finite animation values")
        frames.extend(keys)
    for track in animation.Notifications():
        frames.extend(track.KeyFrameBuffer() or [])
    if not animation.Curves():
        raise ValueError("Animation contains no curves")
    return {"path": str(cast_path(path)), "fps": fps,
            "start": 0, "end": int(max(frames or [0])), "animation": animation}


def preflight(hands_path, weapon_path, settings=None, left="", right=""):
    settings = settings or BuildOptions()
    if settings.animation_mode not in ("simultaneous", "sequential"):
        raise ValueError("Animation mode must be simultaneous or sequential")
    hands, weapon = model_inventory(hands_path), model_inventory(weapon_path)
    targets = (settings.left_target, settings.right_target) if settings.dual else (settings.target_joint,)
    for name in targets:
        if name not in hands["bones"]:
            raise ValueError("Viewhands joint not found: %s" % name)
    if settings.source_joint not in weapon["bones"]:
        raise ValueError("Weapon joint not found: %s" % settings.source_joint)
    if weapon["bones"][settings.source_joint]["parent"] is not None:
        raise ValueError("The weapon attachment joint must be its skeleton root")
    if any(record["parent"] is None and name != settings.source_joint
           for name, record in weapon["bones"].items()):
        raise ValueError("The weapon must have a single skeleton root")
    overlap = {name.casefold() for name in hands["bones"]} & {name.casefold() for name in weapon["bones"]}
    if overlap - {settings.source_joint.casefold()}:
        raise ValueError("Ambiguous hands/weapon joints: %s" % ", ".join(sorted(overlap)))
    for prefix in (("akimbo_l__", "akimbo_r__") if settings.dual else ("weapon__",)):
        for name in weapon["bones"]:
            if len((prefix + name).encode("utf-8")) > 63 or (prefix + name).casefold() in {
                    item.casefold() for item in hands["bones"]}:
                raise ValueError("Cannot isolate weapon joint name: %s" % name)
    if settings.dual and bool(left) != bool(right):
        raise ValueError("Select both left and right animations, or leave both blank")
    animations = [animation_inventory(path) for path in (left, right) if path]
    if len(animations) == 2 and abs(animations[0]["fps"] - animations[1]["fps"]) > 1e-6:
        raise ValueError("Left/right animation frame rates differ")
    reference = None
    if settings.reference_pose:
        reference = model_inventory(settings.reference_pose)
        for target in targets:
            current, ref = hands["bones"][target], reference["bones"].get(target)
            if not ref or current["parent"] != ref["parent"]:
                raise ValueError("Reference pose parent mismatch: %s" % target)
    return {"hands": hands, "weapon": weapon, "reference": reference,
            "settings": asdict(settings), "animations": animations}


def _import_model(path, prefix, collection, warnings):
    previous = set(bpy.data.objects)
    backend().importer.load(cast_options(warnings), bpy.context, str(path))
    created = set(bpy.data.objects) - previous
    rigs = [obj for obj in created if obj.type == "ARMATURE"]
    if len(rigs) != 1:
        raise RuntimeError("CAST did not create exactly one armature")
    rig = rigs[0]
    for obj in created:
        obj.name = prefix + obj.name
        for owner in list(obj.users_collection):
            owner.objects.unlink(obj)
        collection.objects.link(obj)
        for modifier in obj.modifiers:
            if modifier.type == "ARMATURE":
                modifier.use_deform_preserve_volume = True
    select(rig)
    return rig


def _attach(hands, weapon, source_name, target_name, prefix):
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"
              and any(mod.type == "ARMATURE" and mod.object == weapon for mod in obj.modifiers)]
    mapping = {bone.name: prefix + bone.name for bone in weapon.data.bones}
    # Blender also renames vertex groups bound to this armature.
    for bone in weapon.data.bones:
        bone.name = mapping[bone.name]
    for mesh in meshes:
        for old, new in mapping.items():
            group = mesh.vertex_groups.get(old)
            if group:
                group.name = new
    source = mapping[source_name]
    target_world = hands.matrix_world @ hands.data.bones[target_name].head_local
    source_world = weapon.matrix_world @ weapon.data.bones[source].head_local
    weapon.matrix_world.translation += target_world - source_world
    bpy.context.view_layer.update()
    # Keep each mesh in armature space for upstream CAST export, which reads
    # mesh.data directly rather than evaluating mesh.matrix_world.
    for mesh in meshes:
        world = mesh.matrix_world.copy()
        transform = hands.matrix_world.inverted() @ world
        mesh.data.transform(transform, shape_keys=True)
        mesh.parent = hands
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        mesh.matrix_basis = Matrix.Identity(4)
        for modifier in mesh.modifiers:
            if modifier.type == "ARMATURE" and modifier.object == weapon:
                modifier.object = hands
    select(hands)
    weapon.select_set(True)
    bpy.ops.object.join()
    select(hands)
    bpy.ops.object.mode_set(mode="EDIT")
    joint, target = hands.data.edit_bones[source], hands.data.edit_bones[target_name]
    joint.use_connect = False
    joint.parent = target
    bpy.ops.object.mode_set(mode="OBJECT")
    hands.pose.bones[source].location = (0, 0, 0)
    return mapping


def build(hands_path, weapon_path, settings=None, left="", right=""):
    settings = settings or BuildOptions()
    report = preflight(hands_path, weapon_path, settings, left, right)
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        raise ValueError("Switch to Object Mode before building")
    before_objects, before_collections = set(bpy.data.objects), set(bpy.data.collections)
    owned_pools = (bpy.data.actions, bpy.data.meshes, bpy.data.armatures,
                   bpy.data.materials, bpy.data.images)
    before_data = [set(pool) for pool in owned_pools]
    selected, active = list(bpy.context.selected_objects), bpy.context.object
    scene = bpy.context.scene
    old_timing = (scene.frame_start, scene.frame_end, scene.frame_current,
                  scene.render.fps, scene.render.fps_base)
    warnings = []
    collection = bpy.data.collections.new("Viewmodel " + uuid.uuid4().hex[:8])
    collection_name = collection.name
    bpy.context.scene.collection.children.link(collection)
    try:
        hands = _import_model(report["hands"]["path"], "hands__", collection, warnings)
        # Normalize the main rig's object transform while preserving mesh world
        # placement. This makes all export backends operate in one local space.
        select(hands)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        for mesh in collection.objects:
            if mesh.type == "MESH":
                world = mesh.matrix_world.copy()
                mesh.data.transform(hands.matrix_world.inverted() @ world, shape_keys=True)
                mesh.parent = hands
                mesh.matrix_parent_inverse = Matrix.Identity(4)
                mesh.matrix_basis = Matrix.Identity(4)
        mapping = {}
        targets = (("left", settings.left_target, "akimbo_l__"),
                   ("right", settings.right_target, "akimbo_r__")) if settings.dual else (
                       ("single", settings.target_joint, "weapon__"),)
        for side, target, prefix in targets:
            weapon = _import_model(report["weapon"]["path"], prefix, collection, warnings)
            mapping[side] = _attach(hands, weapon, settings.source_joint, target, prefix)
        hands.name = "Viewmodel_Rig"
        state = {"version": VERSION, "collection": collection.name,
                 "hands": report["hands"], "weapon": report["weapon"],
                 "reference": report["reference"], "settings": asdict(settings),
                 "mapping": mapping, "left": left, "right": right,
                 "warnings": warnings}
        hands[STATE_KEY] = json.dumps(state)
        if left:
            apply_animations(hands, left, right)
        select(hands)
        verify(hands)
        return hands
    except Exception:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in set(bpy.data.objects) - before_objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        for pool, before in zip(owned_pools, before_data):
            for item in set(pool) - before:
                if pool == bpy.data.actions:
                    item.use_fake_user = False
                if not item.users:
                    pool.remove(item)
        for group in set(bpy.data.collections) - before_collections:
            if not group.objects and not group.children:
                bpy.data.collections.remove(group)
        scene.frame_start, scene.frame_end, frame, scene.render.fps, scene.render.fps_base = old_timing
        scene.frame_set(frame)
        for obj in selected:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        raise
    finally:
        for group in set(bpy.data.collections) - before_collections:
            if group.name != collection_name and not group.objects and not group.children:
                bpy.data.collections.remove(group)


def state_for(rig):
    if not rig or rig.type != "ARMATURE" or STATE_KEY not in rig:
        raise ValueError("Select a Viewmodel Toolkit armature")
    return json.loads(rig[STATE_KEY])


def verify(rig):
    state = state_for(rig)
    settings = BuildOptions(**state["settings"])
    rows = []
    for side, mapping in state["mapping"].items():
        source = mapping[settings.source_joint]
        target = {"single": settings.target_joint, "left": settings.left_target,
                  "right": settings.right_target}[side]
        bone = rig.data.bones[source]
        if not bone.parent or bone.parent.name != target:
            raise ValueError("Attachment parent changed: %s" % source)
        offset = rig.data.bones[target].matrix_local.inverted() @ bone.matrix_local
        if offset.translation.length > 1e-4:
            raise ValueError("Attachment rest translation is not zero: %s" % source)
        if rig.pose.bones[source].location.length > 1e-4:
            raise ValueError("Attachment animated translation is not zero: %s" % source)
        rows.append({"source": source, "target": target,
                     "rest_translation": list(offset.translation)})
    return {"valid": True, "attachments": rows,
            "bones": len(rig.data.bones), "version": VERSION}


def _side(name, records):
    while name:
        if re.search(r"(?:^|_)(le|left)(?:_|$)", name.lower()):
            return "left"
        if re.search(r"(?:^|_)(ri|right)(?:_|$)", name.lower()):
            return "right"
        name = records[name]["parent"]
    return "shared"


def apply_animations(rig, left, right=""):
    # Kept here as the public seam; sampling/composition is isolated from model
    # import so replacing one clip never rebuilds or damages the user's meshes.
    from .animation import compose
    return compose(rig, left, right)
