r"""Maya Viewmodel Weapon Toolkit plugin for Maya 2022 and newer.

Python 3 mode is required. The minimum compatibility target is Maya 2022
with Python 3.7.7; the release is verified on Maya 2025 for Windows.

The plugin imports one viewhands Cast file and one weapon Cast file, then
parents the weapon's ``j_gun`` under the viewhands' ``tag_weapon`` and zeroes
the weapon joint's local translation. Animation import temporarily routes the
viewhands ``j_gun`` tracks around the attached weapon's same-named root.
Dragging a pure animation Cast file onto Maya uses that same collision-safe
route automatically; model and unrelated Cast files retain Maya's defaults.

The original single-weapon workflow remains available. The Dual-Wield Builder
duplicates one weapon, attaches the copies to ``tag_weapon_left`` and
``tag_weapon_right``, and can compose left/right Cast animations on the same
frames or place them sequentially. It is intended for one duplicated weapon;
asymmetric two-weapon skeletons are outside its scope.

Output formats and their folders are independently selectable: Maya ASCII
(``.ma``), combined model Cast (``.cast``), Source model (``.smd``), and FBX
(``.fbx``). A JSON verification manifest is always written to the common
output folder. Release packages include a project-patched Maya Cast plugin
based on official v1.99; a compatible v1.99 or newer translator can also be
used.

Load this file through Maya's Plug-in Manager. A ``Viewmodel Weapon Toolkit``
menu appears in the main menu bar. The legacy ``attach_gun.py`` loader and
``attachGun`` command remain supported for existing installations.
"""

import datetime
import importlib.util
import json
import os
import re
import sys
import tempfile
import traceback
from urllib.parse import unquote, urlparse
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace

import maya.mel as mel
import maya.cmds as cmds
import maya.OpenMaya as OpenMaya
import maya.OpenMayaMPx as OpenMayaMPx
import maya.OpenMayaUI as OpenMayaUI


# ---------------------------------------------------------------------------
# Constants.
# ---------------------------------------------------------------------------

DEFAULT_SOURCE_JOINT = "j_gun"
DEFAULT_TARGET_JOINT = "tag_weapon"
DEFAULT_LEFT_TARGET_JOINT = "tag_weapon_left"
DEFAULT_RIGHT_TARGET_JOINT = "tag_weapon_right"
PRODUCT_NAME = "Maya Viewmodel Weapon Toolkit"
PRODUCT_SHORT_NAME = "Viewmodel Weapon Toolkit"
PLUGIN_BASENAME = "viewmodel_weapon_toolkit"
LEGACY_PLUGIN_BASENAME = "attach_gun"
DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "MayaViewmodelWeaponToolkit")

HANDS_NAMESPACE = "hands"
WEAPON_NAMESPACE = "weapon"
LEFT_WEAPON_NAMESPACE = "akimbo_l"
RIGHT_WEAPON_NAMESPACE = "akimbo_r"
LEFT_WEAPON_PREFIX = "akimbo_l_"
RIGHT_WEAPON_PREFIX = "akimbo_r_"
DUAL_STATE_NODE = "attachGunDualState"
DUAL_SIDES = ("left", "right")
DUAL_ANIMATION_MODES = ("simultaneous", "sequential")

MENU_NAME = "ViewmodelWeaponToolkitMenu"
COMMAND_NAME = "viewmodelWeaponToolkit"
LEGACY_COMMAND_NAME = "attachGun"
WINDOW_NAME = "ViewmodelWeaponToolkitWindow"
DUAL_WINDOW_NAME = "ViewmodelWeaponToolkitDualWindow"
VERSION = "3.0.2"

VIEWHANDS_OPTVAR = "attachGun_viewhandsPath"
OUTPUT_DIR_OPTVAR = "attachGun_outputDir"
MA_OUTPUT_DIR_OPTVAR = "attachGun_maOutputDir"
CAST_OUTPUT_DIR_OPTVAR = "attachGun_castOutputDir"
SMD_OUTPUT_DIR_OPTVAR = "attachGun_smdOutputDir"
FBX_OUTPUT_DIR_OPTVAR = "attachGun_fbxOutputDir"
SOURCE_JOINT_OPTVAR = "attachGun_sourceJoint"
TARGET_JOINT_OPTVAR = "attachGun_targetJoint"
PROTECT_TRANSLATION_OPTVAR = "attachGun_protectTranslation"
EXPORT_MA_OPTVAR = "attachGun_exportMa"
EXPORT_CAST_OPTVAR = "attachGun_exportCast"
EXPORT_SMD_OPTVAR = "attachGun_exportSmd"
EXPORT_FBX_OPTVAR = "attachGun_exportFbx"
AUTO_SAFE_DROP_OPTVAR = "attachGun_autoSafeCastAnimationDrop"
DUAL_VIEWHANDS_OPTVAR = "attachGun_dualViewhandsPath"
DUAL_WEAPON_OPTVAR = "attachGun_dualWeaponPath"
DUAL_LEFT_ANIMATION_OPTVAR = "attachGun_dualLeftAnimationPath"
DUAL_RIGHT_ANIMATION_OPTVAR = "attachGun_dualRightAnimationPath"
DUAL_MODE_OPTVAR = "attachGun_dualAnimationMode"

VIEWHANDS_FIELD = "attachGun_viewhandsField"
WEAPON_FIELD = "attachGun_weaponField"
OUTPUT_DIR_FIELD = "attachGun_outputDirField"
MA_OUTPUT_DIR_FIELD = "attachGun_maOutputDirField"
CAST_OUTPUT_DIR_FIELD = "attachGun_castOutputDirField"
SMD_OUTPUT_DIR_FIELD = "attachGun_smdOutputDirField"
FBX_OUTPUT_DIR_FIELD = "attachGun_fbxOutputDirField"
SOURCE_JOINT_FIELD = "attachGun_sourceJointField"
TARGET_JOINT_FIELD = "attachGun_targetJointField"
PROTECT_TRANSLATION_CHECK = "attachGun_protectTranslationCheck"
EXPORT_MA_CHECK = "attachGun_exportMaCheck"
EXPORT_CAST_CHECK = "attachGun_exportCastCheck"
EXPORT_SMD_CHECK = "attachGun_exportSmdCheck"
EXPORT_FBX_CHECK = "attachGun_exportFbxCheck"
DUAL_VIEWHANDS_FIELD = "attachGun_dualViewhandsField"
DUAL_WEAPON_FIELD = "attachGun_dualWeaponField"
DUAL_LEFT_ANIMATION_FIELD = "attachGun_dualLeftAnimationField"
DUAL_RIGHT_ANIMATION_FIELD = "attachGun_dualRightAnimationField"
DUAL_MODE_MENU = "attachGun_dualModeMenu"
DUAL_LEFT_TARGET_FIELD = "attachGun_dualLeftTargetField"
DUAL_RIGHT_TARGET_FIELD = "attachGun_dualRightTargetField"

_LAST_RESULT = None
_CAST_BATCH_MODULE = None
_CAST_TRANSLATOR_FALLBACK_REGISTERED = False
_CAST_DROP_CALLBACK = None


@dataclass
class AttachOptions:
    """Options for one single-weapon attachment operation."""

    output_dir: str = DEFAULT_OUTPUT_DIR
    source_joint: str = DEFAULT_SOURCE_JOINT
    target_joint: str = DEFAULT_TARGET_JOINT
    force_new_scene: bool = False
    protect_translation: bool = True
    disable_import_ik: bool = True
    disable_import_constraints: bool = True
    save_scene: bool = True
    export_cast: bool = True
    export_smd: bool = False
    export_fbx: bool = False
    ma_output_dir: str = ""
    cast_output_dir: str = ""
    smd_output_dir: str = ""
    fbx_output_dir: str = ""


@dataclass
class DualWieldOptions(AttachOptions):
    """Options for one duplicated-weapon dual-wield result."""

    left_target_joint: str = DEFAULT_LEFT_TARGET_JOINT
    right_target_joint: str = DEFAULT_RIGHT_TARGET_JOINT
    left_prefix: str = LEFT_WEAPON_PREFIX
    right_prefix: str = RIGHT_WEAPON_PREFIX
    animation_mode: str = "simultaneous"
    shared_hands_source: str = "right"


@dataclass
class AttachResult:
    """Structured result shared by the UI, batch mode, and verification."""

    plugin_version: str
    cast_plugin_version: str
    created_at: str
    viewhands_path: str
    weapon_path: str
    viewhands_size: int
    weapon_size: int
    source_joint_name: str
    target_joint_name: str
    source_node: str
    target_node: str
    source_uuid: str
    target_uuid: str
    parent_node: str
    translation: tuple
    hands_namespace: str
    weapon_namespace: str
    hands_roots: list
    weapon_roots: list
    output_scene: str = ""
    output_cast: str = ""
    output_smd: str = ""
    output_fbx: str = ""
    output_manifest: str = ""
    animation_path: str = ""
    translation_protected: bool = True
    preflight: dict = field(default_factory=dict)
    cast_verification: dict = field(default_factory=dict)
    smd_verification: dict = field(default_factory=dict)
    fbx_verification: dict = field(default_factory=dict)
    requested_outputs: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


@dataclass
class DualWieldResult(AttachResult):
    """Structured result for a dual-wield build and animation composition."""

    right_source_node: str = ""
    right_target_node: str = ""
    right_source_uuid: str = ""
    right_target_uuid: str = ""
    right_parent_node: str = ""
    right_translation: tuple = ()
    right_weapon_namespace: str = ""
    right_weapon_roots: list = field(default_factory=list)
    left_animation_path: str = ""
    right_animation_path: str = ""
    animation_mode: str = "simultaneous"
    shared_hands_source: str = "right"
    left_prefix: str = LEFT_WEAPON_PREFIX
    right_prefix: str = RIGHT_WEAPON_PREFIX
    left_clip_range: tuple = ()
    right_clip_range: tuple = ()
    dual_state_node: str = ""
    dual_verification: dict = field(default_factory=dict)
    left_import_report: dict = field(default_factory=dict)
    right_import_report: dict = field(default_factory=dict)


def log(msg):
    print("[viewmodel_weapon_toolkit] " + str(msg))
    try:
        sys.stdout.flush()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Settings persistence.
# ---------------------------------------------------------------------------

def _load_string_option(name, default=""):
    if cmds.optionVar(exists=name):
        value = cmds.optionVar(query=name)
        if value:
            return str(value)
    return default


def _save_string_option(name, value):
    if value:
        cmds.optionVar(stringValue=(name, str(value)))
    elif cmds.optionVar(exists=name):
        cmds.optionVar(remove=name)


def _load_bool_option(name, default=False):
    if cmds.optionVar(exists=name):
        return bool(cmds.optionVar(query=name))
    return bool(default)


def _save_bool_option(name, value):
    cmds.optionVar(intValue=(name, int(bool(value))))


def load_viewhands_path():
    return _load_string_option(VIEWHANDS_OPTVAR)


def save_viewhands_path(path):
    _save_string_option(VIEWHANDS_OPTVAR, path)


def auto_safe_drop_enabled():
    """Return whether external animation CAST drops use the safe importer."""
    return _load_bool_option(AUTO_SAFE_DROP_OPTVAR, True)


def set_auto_safe_drop_enabled(enabled):
    _save_bool_option(AUTO_SAFE_DROP_OPTVAR, enabled)


def load_saved_options(force_new_scene=False):
    return AttachOptions(
        output_dir=_load_string_option(OUTPUT_DIR_OPTVAR, DEFAULT_OUTPUT_DIR),
        ma_output_dir=_load_string_option(MA_OUTPUT_DIR_OPTVAR),
        cast_output_dir=_load_string_option(CAST_OUTPUT_DIR_OPTVAR),
        smd_output_dir=_load_string_option(SMD_OUTPUT_DIR_OPTVAR),
        fbx_output_dir=_load_string_option(FBX_OUTPUT_DIR_OPTVAR),
        source_joint=_load_string_option(SOURCE_JOINT_OPTVAR, DEFAULT_SOURCE_JOINT),
        target_joint=_load_string_option(TARGET_JOINT_OPTVAR, DEFAULT_TARGET_JOINT),
        protect_translation=_load_bool_option(PROTECT_TRANSLATION_OPTVAR, True),
        save_scene=_load_bool_option(EXPORT_MA_OPTVAR, True),
        export_cast=_load_bool_option(EXPORT_CAST_OPTVAR, True),
        export_smd=_load_bool_option(EXPORT_SMD_OPTVAR, False),
        export_fbx=_load_bool_option(EXPORT_FBX_OPTVAR, False),
        force_new_scene=force_new_scene,
    )


def save_options(viewhands_path, options):
    save_viewhands_path(viewhands_path)
    _save_string_option(OUTPUT_DIR_OPTVAR, options.output_dir)
    _save_string_option(MA_OUTPUT_DIR_OPTVAR, options.ma_output_dir)
    _save_string_option(CAST_OUTPUT_DIR_OPTVAR, options.cast_output_dir)
    _save_string_option(SMD_OUTPUT_DIR_OPTVAR, options.smd_output_dir)
    _save_string_option(FBX_OUTPUT_DIR_OPTVAR, options.fbx_output_dir)
    _save_string_option(SOURCE_JOINT_OPTVAR, options.source_joint)
    _save_string_option(TARGET_JOINT_OPTVAR, options.target_joint)
    _save_bool_option(PROTECT_TRANSLATION_OPTVAR, options.protect_translation)
    _save_bool_option(EXPORT_MA_OPTVAR, options.save_scene)
    _save_bool_option(EXPORT_CAST_OPTVAR, options.export_cast)
    _save_bool_option(EXPORT_SMD_OPTVAR, options.export_smd)
    _save_bool_option(EXPORT_FBX_OPTVAR, options.export_fbx)


def clear_saved_settings():
    for name in (
            VIEWHANDS_OPTVAR,
            OUTPUT_DIR_OPTVAR,
            MA_OUTPUT_DIR_OPTVAR,
            CAST_OUTPUT_DIR_OPTVAR,
            SMD_OUTPUT_DIR_OPTVAR,
            FBX_OUTPUT_DIR_OPTVAR,
            SOURCE_JOINT_OPTVAR,
            TARGET_JOINT_OPTVAR,
            PROTECT_TRANSLATION_OPTVAR,
            EXPORT_MA_OPTVAR,
            EXPORT_CAST_OPTVAR,
            EXPORT_SMD_OPTVAR,
            EXPORT_FBX_OPTVAR,
            AUTO_SAFE_DROP_OPTVAR,
            DUAL_VIEWHANDS_OPTVAR,
            DUAL_WEAPON_OPTVAR,
            DUAL_LEFT_ANIMATION_OPTVAR,
            DUAL_RIGHT_ANIMATION_OPTVAR,
            DUAL_MODE_OPTVAR):
        if cmds.optionVar(exists=name):
            cmds.optionVar(remove=name)


# ---------------------------------------------------------------------------
# Cast plugin and non-mutating preflight.
# ---------------------------------------------------------------------------

def _validate_cast_path(path, label):
    if not path or not os.path.isfile(path):
        raise RuntimeError("%s file not found: %r" % (label, path))
    if os.path.splitext(path)[1].lower() != ".cast":
        raise RuntimeError("%s must be a .cast file: %s" % (label, path))
    return os.path.normpath(os.path.abspath(path))


def _is_plugin_loaded(name):
    try:
        return bool(cmds.pluginInfo(name, query=True, loaded=True))
    except Exception:
        return False


def _toolkit_registered_cast_translator():
    for plugin_name in (PLUGIN_BASENAME, LEGACY_PLUGIN_BASENAME):
        try:
            if not cmds.pluginInfo(plugin_name, query=True, loaded=True):
                continue
            translators = cmds.pluginInfo(
                plugin_name, query=True, translator=True) or []
            if isinstance(translators, str):
                translators = [translators]
            if any(str(name).lower() == "cast" for name in translators):
                return True
        except Exception:
            continue
    return False


def ensure_cast_plugin():
    """Load Maya's bundled Cast translator and retain the original error."""
    if _CAST_TRANSLATOR_FALLBACK_REGISTERED:
        return
    if _toolkit_registered_cast_translator():
        return
    for name in ("castplugin", "castplugin.py"):
        if _is_plugin_loaded(name):
            return

    if cmds.about(batch=True):
        raise RuntimeError(
            "The official Cast plugin cannot initialize its menu in Maya batch mode. Load "
            "%s as a Maya plugin so it can register the official "
            "Cast translator through its batch fallback." % PRODUCT_NAME)

    try:
        cmds.loadPlugin("castplugin.py", quiet=True)
    except Exception as exc:
        raise RuntimeError(
            "Maya's bundled castplugin.py failed to load: %s" % exc) from exc

    if not any(_is_plugin_loaded(name) for name in ("castplugin", "castplugin.py")):
        raise RuntimeError("castplugin.py loaded without registering as a Maya plugin")


def _cast_plugin_path():
    """Return the actual castplugin.py path registered with this Maya process."""
    for name in ("castplugin", "castplugin.py"):
        if not _is_plugin_loaded(name):
            continue
        try:
            path = cmds.pluginInfo(name, query=True, path=True)
        except Exception:
            path = ""
        if path and os.path.isfile(path):
            return os.path.normpath(os.path.abspath(path))

    plugin_dir = os.path.join(
        os.path.dirname(os.path.abspath(sys.executable)), "plug-ins")
    path = os.path.join(plugin_dir, "castplugin.py")
    if os.path.isfile(path):
        return os.path.normpath(os.path.abspath(path))
    raise RuntimeError("Maya Cast plugin file not found: %s" % path)


def _load_castplugin_module():
    """Load Cast Python code from Maya's registered plugin path."""
    global _CAST_BATCH_MODULE

    plugin_path = _cast_plugin_path()
    for existing in tuple(sys.modules.values()):
        existing_path = os.path.abspath(getattr(
            existing, "__file__", "") or "") if existing is not None else ""
        if (existing_path and os.path.normcase(existing_path)
                == os.path.normcase(plugin_path)
                and hasattr(existing, "sceneSettings")
                and hasattr(existing, "Cast")):
            _CAST_BATCH_MODULE = existing
            return existing

    plugin_dir = os.path.dirname(plugin_path)
    if not any(
            os.path.normcase(os.path.abspath(path or os.curdir))
            == os.path.normcase(plugin_dir)
            for path in sys.path):
        sys.path.insert(0, plugin_dir)

    spec = importlib.util.spec_from_file_location("castplugin", plugin_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Unable to create a Python module spec for: %s" % plugin_path)
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get("castplugin")
    sys.modules["castplugin"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if previous is None:
            sys.modules.pop("castplugin", None)
        else:
            sys.modules["castplugin"] = previous
        raise

    _CAST_BATCH_MODULE = module
    return module


def _import_cast_module_for_batch():
    """Import official Cast code for the batch translator fallback."""
    if _CAST_BATCH_MODULE is not None:
        return _CAST_BATCH_MODULE
    return _load_castplugin_module()


def _register_batch_cast_translator(plugin):
    """Register the official Cast reader under this plugin in batch mode."""
    global _CAST_TRANSLATOR_FALLBACK_REGISTERED
    module = _import_cast_module_for_batch()
    # The official plugin expects Maya UI progress controls that do not exist
    # in batch mode. Keep its importer/exporter implementation and replace only
    # the visual progress hooks for this headless process.
    module.utilityCreateProgress = lambda status="", maximum=0: None
    module.utilityStepProgress = lambda instance, status="": None
    module.utilityEndProgress = lambda instance: None
    module.utilityCreateMenu = lambda *args, **kwargs: None
    module.utilityRemoveMenu = lambda *args, **kwargs: None
    # A failed official batch initialization can leave a translator registered
    # even though pluginInfo reports the plugin as unloaded. Remove that stale
    # reader so Maya selects this patched official-module registration.
    try:
        plugin.deregisterFileTranslator("Cast")
    except RuntimeError:
        pass
    plugin.registerFileTranslator("Cast", None, module.createCastTranslator)
    _CAST_TRANSLATOR_FALLBACK_REGISTERED = True
    log("registered official Cast translator through batch fallback")


def _castplugin_module():
    ensure_cast_plugin()
    return _load_castplugin_module()


def _loaded_castplugin_modules():
    """Return every loaded Python module instance for the active translator."""
    ensure_cast_plugin()
    plugin_path = _cast_plugin_path()
    modules = []
    seen = set()
    for module in tuple(sys.modules.values()):
        module_path = os.path.abspath(getattr(
            module, "__file__", "") or "") if module is not None else ""
        if (not module_path or os.path.normcase(module_path)
                != os.path.normcase(plugin_path)):
            continue
        if not isinstance(getattr(module, "sceneSettings", None), dict):
            continue
        identity = id(module)
        if identity not in seen:
            seen.add(identity)
            modules.append(module)
    primary = _load_castplugin_module()
    if id(primary) not in seen:
        modules.append(primary)
    return modules


def cast_translator_name():
    """Return the exact translator name registered by the loaded plugin."""
    ensure_cast_plugin()
    for plugin_name in ("castplugin", "castplugin.py"):
        try:
            translators = cmds.pluginInfo(
                plugin_name, query=True, translator=True) or []
        except Exception:
            continue
        if isinstance(translators, str):
            translators = [translators]
        for translator in translators:
            if str(translator).lower() == "cast":
                return str(translator)
    return "Cast"


def cast_plugin_version():
    if _CAST_BATCH_MODULE is not None:
        return str(getattr(_CAST_BATCH_MODULE, "version", "unknown"))
    module = sys.modules.get("castplugin")
    if module is not None and hasattr(module, "version"):
        return str(module.version)
    for plugin_name in ("castplugin", "castplugin.py"):
        try:
            if _is_plugin_loaded(plugin_name):
                return str(cmds.pluginInfo(plugin_name, query=True, version=True))
        except Exception:
            pass
    return "unknown"


def _short_name(name):
    return str(name).split("|")[-1].split(":")[-1]


def _cast_bone_inventory(path):
    """Read skeleton and mesh health with cast.py; do not modify the scene."""
    module = _castplugin_module()
    cast_file = module.Cast.load(path)
    bone_names = []
    bone_records = []
    model_count = 0
    animation_count = 0
    skeleton_count = 0
    mesh_count = 0
    vertex_count = 0
    face_count = 0
    unused_vertex_count = 0
    invalid_face_index_count = 0
    uv_buffer_mismatch_count = 0
    mesh_warnings = []

    for root in cast_file.Roots():
        animation_count += len(root.ChildrenOfType(module.Animation))
        for model in root.ChildrenOfType(module.Model):
            model_count += 1
            skeleton = model.Skeleton()
            if skeleton is not None:
                skeleton_count += 1
                bones = list(skeleton.Bones())
                for bone_index, bone in enumerate(bones):
                    bone_name = str(bone.Name())
                    parent_index = int(bone.ParentIndex())
                    parent_name = None
                    if 0 <= parent_index < len(bones):
                        parent_name = str(bones[parent_index].Name())
                    bone_names.append(bone_name)
                    bone_records.append({
                        "name": bone_name,
                        "index": bone_index,
                        "parent_index": parent_index,
                        "parent_name": parent_name,
                    })

            for mesh_index, mesh in enumerate(model.Meshes()):
                mesh_count += 1
                mesh_vertex_count = int(mesh.VertexCount() or 0)
                mesh_faces = list(mesh.FaceBuffer() or [])
                mesh_face_count = int(len(mesh_faces) / 3)
                valid_indices = {
                    int(index) for index in mesh_faces
                    if 0 <= int(index) < mesh_vertex_count
                }
                mesh_invalid_indices = sum(
                    1 for index in mesh_faces
                    if int(index) < 0 or int(index) >= mesh_vertex_count
                )
                mesh_unused_vertices = max(
                    mesh_vertex_count - len(valid_indices), 0)
                uv_mismatches = []
                for uv_index in range(int(mesh.UVLayerCount() or 0)):
                    uv_values = mesh.VertexUVLayerBuffer(uv_index) or []
                    uv_vertex_count = int(len(uv_values) / 2)
                    if uv_vertex_count != mesh_vertex_count:
                        uv_mismatches.append({
                            "layer": uv_index,
                            "expected_vertices": mesh_vertex_count,
                            "actual_vertices": uv_vertex_count,
                        })

                vertex_count += mesh_vertex_count
                face_count += mesh_face_count
                unused_vertex_count += mesh_unused_vertices
                invalid_face_index_count += mesh_invalid_indices
                uv_buffer_mismatch_count += len(uv_mismatches)
                if (mesh_unused_vertices or mesh_invalid_indices
                        or uv_mismatches):
                    mesh_warnings.append({
                        "mesh_index": mesh_index,
                        "mesh_name": str(mesh.Name() or "mesh_%d" % mesh_index),
                        "vertex_count": mesh_vertex_count,
                        "face_count": mesh_face_count,
                        "unused_vertices": mesh_unused_vertices,
                        "invalid_face_indices": mesh_invalid_indices,
                        "uv_buffer_mismatches": uv_mismatches,
                    })

    return {
        "model_count": model_count,
        "animation_count": animation_count,
        "skeleton_count": skeleton_count,
        "bone_count": len(bone_names),
        "bone_names": bone_names,
        "bone_records": bone_records,
        "mesh_count": mesh_count,
        "vertex_count": vertex_count,
        "face_count": face_count,
        "unused_vertex_count": unused_vertex_count,
        "invalid_face_index_count": invalid_face_index_count,
        "uv_buffer_mismatch_count": uv_buffer_mismatch_count,
        "mesh_warnings": mesh_warnings,
    }


def _set_scene_framerate_from_animation(path):
    """Set Maya's time unit before file import can rescale Cast keyframes."""
    module = _castplugin_module()
    cast_file = module.Cast.load(path)
    animations = []
    for root in cast_file.Roots():
        animations.extend(root.ChildrenOfType(module.Animation))
    if not animations:
        raise RuntimeError("Cast file contains no animation: %s" % path)

    framerates = {float(animation.Framerate()) for animation in animations}
    if len(framerates) != 1:
        raise RuntimeError(
            "Cast file contains mixed animation framerates: %s"
            % sorted(framerates))
    framerate = framerates.pop()
    OpenMaya.MTime.setUIUnit(module.utilityFramerateToUnit(framerate))
    log("scene framerate set from animation: %s fps" % framerate)
    return framerate


def _preflight_one(path, expected_joint, label):
    inventory = _cast_bone_inventory(path)
    matches = [
        name for name in inventory["bone_names"]
        if _short_name(name) == expected_joint
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "%s must contain exactly one joint named %s; found %d. "
            "The single-weapon workflow requires one match. Use the "
            "Dual-Wield Builder for Akimbo inputs."
            % (label, expected_joint, len(matches)))

    if inventory["unused_vertex_count"]:
        log("WARNING %s source contains %d vertices not referenced by faces" %
            (label, inventory["unused_vertex_count"]))
    if inventory["invalid_face_index_count"]:
        raise RuntimeError(
            "%s contains %d out-of-range face indices"
            % (label, inventory["invalid_face_index_count"]))
    if inventory["uv_buffer_mismatch_count"]:
        log("WARNING %s source contains %d UV buffer length mismatches" %
            (label, inventory["uv_buffer_mismatch_count"]))

    result = dict(inventory)
    result.pop("bone_names", None)
    result.pop("bone_records", None)
    result["path"] = path
    result["expected_joint"] = expected_joint
    result["match"] = matches[0]
    return result


def preflight_inputs(viewhands_path, weapon_path,
                     source_joint=DEFAULT_SOURCE_JOINT,
                     target_joint=DEFAULT_TARGET_JOINT):
    """Validate both Cast files without changing the current Maya scene."""
    viewhands_path = _validate_cast_path(viewhands_path, "Viewhands")
    weapon_path = _validate_cast_path(weapon_path, "Weapon")
    if not source_joint.strip() or not target_joint.strip():
        raise RuntimeError("Source and target joint names cannot be empty")
    if source_joint.strip() == target_joint.strip():
        raise RuntimeError("Source and target joint names must be different")

    log("preflight viewhands: %s" % viewhands_path)
    viewhands = _preflight_one(viewhands_path, target_joint.strip(), "Viewhands")
    log("preflight weapon: %s" % weapon_path)
    weapon = _preflight_one(weapon_path, source_joint.strip(), "Weapon")
    return {
        "single_weapon_only": True,
        "mapping": "weapon:%s -> viewhands:%s" % (
            source_joint.strip(), target_joint.strip()),
        "viewhands": viewhands,
        "weapon": weapon,
    }


def _cast_animation_inventory(path):
    """Read animation tracks without changing the Maya scene."""
    module = _castplugin_module()
    cast_file = module.Cast.load(path)
    animations = []
    model_count = 0
    for root in cast_file.Roots():
        model_count += len(root.ChildrenOfType(module.Model))
        animations.extend(root.ChildrenOfType(module.Animation))
    if model_count:
        raise RuntimeError(
            "Animation input must not contain models: %s" % path)
    if len(animations) != 1:
        raise RuntimeError(
            "Animation input must contain exactly one animation; found %d: %s"
            % (len(animations), path))

    animation = animations[0]
    curve_records = []
    all_frames = []
    for curve in animation.Curves():
        frames = tuple(int(value) for value in curve.KeyFrameBuffer() or [])
        values = tuple(float(value) for value in curve.KeyValueBuffer() or [])
        all_frames.extend(frames)
        curve_records.append({
            "node": str(curve.NodeName()),
            "property": str(curve.KeyPropertyName()),
            "frames": frames,
            "values": values,
            "mode": str(curve.Mode() or "absolute"),
        })
    if not all_frames:
        raise RuntimeError("Animation contains no keyed curves: %s" % path)
    return {
        "path": path,
        "framerate": float(animation.Framerate()),
        "frame_range": [min(all_frames), max(all_frames)],
        "looping": bool(animation.Looping()),
        "curve_count": len(curve_records),
        "animated_node_count": len({
            record["node"] for record in curve_records}),
        "curve_records": curve_records,
    }


def _public_animation_inventory(inventory):
    result = dict(inventory)
    result.pop("curve_records", None)
    return result


def _dual_animation_side_signature(path):
    """Infer an Akimbo side from dynamic left/right hand-branch tracks."""
    inventory = _cast_animation_inventory(path)
    scores = {"left": 0, "right": 0}
    for record in inventory["curve_records"]:
        side = _side_from_joint_name(record["node"])
        if side not in scores:
            continue
        distinct_frames = len(set(record["frames"]))
        scores[side] += max(distinct_frames - 1, 0)
    if not scores["left"] and not scores["right"]:
        return None, scores
    high_side = max(scores, key=scores.get)
    low_side = "right" if high_side == "left" else "left"
    if scores[high_side] <= scores[low_side] * 1.2:
        return None, scores
    return high_side, scores


def _side_from_joint_name(name):
    """Classify conventional Cast viewhands joint suffixes."""
    lowered = str(name).lower()
    if re.search(r"(?:^|_)(?:le|left)(?:_|$)", lowered):
        return "left"
    if re.search(r"(?:^|_)(?:ri|right)(?:_|$)", lowered):
        return "right"
    return "shared"


def _curve_signature(record):
    return (
        record["frames"],
        record["values"],
        record["mode"],
    )


def preflight_dual_inputs(
        viewhands_path,
        weapon_path,
        left_animation_path,
        right_animation_path,
        animation_mode="simultaneous",
        source_joint=DEFAULT_SOURCE_JOINT,
        left_target_joint=DEFAULT_LEFT_TARGET_JOINT,
        right_target_joint=DEFAULT_RIGHT_TARGET_JOINT):
    """Validate a duplicated-weapon Akimbo build without changing the scene."""
    viewhands_path = _validate_cast_path(viewhands_path, "Viewhands")
    weapon_path = _validate_cast_path(weapon_path, "Weapon")
    left_animation_path = _validate_cast_path(
        left_animation_path, "Left animation")
    right_animation_path = _validate_cast_path(
        right_animation_path, "Right animation")
    if animation_mode not in DUAL_ANIMATION_MODES:
        raise RuntimeError(
            "Dual animation mode must be simultaneous or sequential")

    viewhands_full = _cast_bone_inventory(viewhands_path)
    weapon_full = _cast_bone_inventory(weapon_path)
    viewhands_names = list(viewhands_full["bone_names"])
    weapon_names = list(weapon_full["bone_names"])
    for joint_name in (left_target_joint, right_target_joint):
        matches = [name for name in viewhands_names
                   if _short_name(name) == joint_name]
        if len(matches) != 1:
            raise RuntimeError(
                "Viewhands must contain exactly one %s; found %d"
                % (joint_name, len(matches)))
    source_matches = [name for name in weapon_names
                      if _short_name(name) == source_joint]
    if len(source_matches) != 1:
        raise RuntimeError(
            "Weapon must contain exactly one %s; found %d"
            % (source_joint, len(source_matches)))
    duplicate_weapon_names = sorted({
        name for name in weapon_names if weapon_names.count(name) > 1})
    if duplicate_weapon_names:
        raise RuntimeError(
            "Weapon skeleton contains duplicate joint names: %s"
            % ", ".join(duplicate_weapon_names))
    overlaps = sorted(set(viewhands_names).intersection(weapon_names))
    unsupported_overlaps = [name for name in overlaps
                            if _short_name(name) != source_joint]
    if unsupported_overlaps:
        raise RuntimeError(
            "Viewhands and weapon share unsupported joint names: %s"
            % ", ".join(unsupported_overlaps))

    left_animation = _cast_animation_inventory(left_animation_path)
    right_animation = _cast_animation_inventory(right_animation_path)
    if abs(left_animation["framerate"] -
           right_animation["framerate"]) > 1e-6:
        raise RuntimeError(
            "Left/right animation framerates differ: %s != %s"
            % (left_animation["framerate"],
               right_animation["framerate"]))

    left_curves = {
        (record["node"], record["property"]): record
        for record in left_animation["curve_records"]}
    right_curves = {
        (record["node"], record["property"]): record
        for record in right_animation["curve_records"]}
    common_keys = set(left_curves).intersection(right_curves)
    conflicting_keys = sorted(
        key for key in common_keys
        if _curve_signature(left_curves[key]) !=
        _curve_signature(right_curves[key]))

    known_nodes = set(viewhands_names).union(weapon_names)
    animated_nodes = {
        record["node"]
        for animation in (left_animation, right_animation)
        for record in animation["curve_records"]
    }
    orphan_nodes = sorted(animated_nodes - known_nodes)
    side_counts = {"left": 0, "right": 0, "shared": 0}
    for name in viewhands_names:
        side_counts[_side_from_joint_name(name)] += 1

    def public_model_inventory(inventory):
        result = dict(inventory)
        result.pop("bone_names", None)
        result.pop("bone_records", None)
        return result

    warnings = []
    if orphan_nodes:
        warnings.append(
            "Animation curve nodes missing from both skeletons will be "
            "skipped: %s" % ", ".join(orphan_nodes))
    if conflicting_keys and animation_mode == "simultaneous":
        warnings.append(
            "%d same-named curve tracks differ; left/right hand branches "
            "are split and shared tracks use the selected master animation"
            % len(conflicting_keys))

    return {
        "dual_wield": True,
        "same_weapon_duplicated": True,
        "animation_mode": animation_mode,
        "mapping": {
            "left": "weapon:%s -> viewhands:%s" % (
                source_joint, left_target_joint),
            "right": "weapon:%s -> viewhands:%s" % (
                source_joint, right_target_joint),
        },
        "viewhands": public_model_inventory(viewhands_full),
        "weapon": public_model_inventory(weapon_full),
        "left_animation": _public_animation_inventory(left_animation),
        "right_animation": _public_animation_inventory(right_animation),
        "viewhands_side_counts": side_counts,
        "shared_curve_count": len(common_keys),
        "conflicting_shared_curve_count": len(conflicting_keys),
        "orphan_curve_nodes": orphan_nodes,
        "warnings": warnings,
    }


def verify_exported_cast(path,
                         source_joint=DEFAULT_SOURCE_JOINT,
                         target_joint=DEFAULT_TARGET_JOINT):
    """Re-read an exported Cast and verify model, skeleton, and key joints."""
    path = _validate_cast_path(path, "Exported Cast")
    inventory = _cast_bone_inventory(path)
    source_matches = [
        name for name in inventory["bone_names"]
        if _short_name(name) == source_joint
    ]
    target_matches = [
        name for name in inventory["bone_names"]
        if _short_name(name) == target_joint
    ]
    source_records = [
        record for record in inventory["bone_records"]
        if _short_name(record["name"]) == source_joint
    ]
    if inventory["model_count"] < 1:
        raise RuntimeError("Exported Cast contains no model: %s" % path)
    if inventory["skeleton_count"] < 1:
        raise RuntimeError("Exported Cast contains no skeleton: %s" % path)
    if inventory["animation_count"]:
        raise RuntimeError(
            "Exported Cast unexpectedly contains %d animation nodes: %s"
            % (inventory["animation_count"], path))
    if len(source_matches) != 1 or len(target_matches) != 1:
        raise RuntimeError(
            "Exported Cast joint verification failed: %s=%d, %s=%d"
            % (source_joint, len(source_matches),
               target_joint, len(target_matches)))
    source_parent = source_records[0]["parent_name"]
    if _short_name(source_parent or "") != target_joint:
        raise RuntimeError(
            "Exported Cast hierarchy verification failed: %s parent is %s, "
            "expected %s"
            % (source_joint, source_parent, target_joint))
    return {
        "path": path,
        "size": os.path.getsize(path),
        "model_count": inventory["model_count"],
        "animation_count": inventory["animation_count"],
        "skeleton_count": inventory["skeleton_count"],
        "bone_count": inventory["bone_count"],
        "mesh_count": inventory["mesh_count"],
        "vertex_count": inventory["vertex_count"],
        "face_count": inventory["face_count"],
        "unused_vertex_count": inventory["unused_vertex_count"],
        "invalid_face_index_count": inventory["invalid_face_index_count"],
        "uv_buffer_mismatch_count": inventory["uv_buffer_mismatch_count"],
        "source_match": source_matches[0],
        "target_match": target_matches[0],
        "source_parent": source_parent,
    }


def _smd_safe_name(value, fallback):
    value = str(value or fallback)
    return value.replace("\r", "_").replace("\n", "_").replace('"', "'")


def _cast_buffer_vector(values, index, width, default):
    if values is None:
        return default
    start = int(index) * int(width)
    end = start + int(width)
    if start < 0 or end > len(values):
        return default
    return tuple(float(value) for value in values[start:end])


def _cast_vertex_weights(mesh, vertex_index, bone_count):
    influence_count = int(mesh.MaximumWeightInfluence() or 0)
    bone_values = mesh.VertexWeightBoneBuffer() or []
    weight_values = mesh.VertexWeightValueBuffer() or []
    combined = {}
    for slot in range(influence_count):
        index = vertex_index * influence_count + slot
        if index >= len(bone_values) or index >= len(weight_values):
            break
        bone_index = int(bone_values[index])
        weight = float(weight_values[index])
        if 0 <= bone_index < bone_count and weight > 0.000001:
            combined[bone_index] = combined.get(bone_index, 0.0) + weight
    total = sum(combined.values())
    if total <= 0.0:
        return []
    return sorted(
        ((bone_index, weight / total)
         for bone_index, weight in combined.items()),
        key=lambda item: (-item[1], item[0]),
    )


def verify_exported_smd(path,
                        source_joint=DEFAULT_SOURCE_JOINT,
                        target_joint=DEFAULT_TARGET_JOINT):
    """Parse a model SMD and verify its skeleton hierarchy and triangles."""
    path = os.path.normpath(os.path.abspath(path))
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        raise RuntimeError("Exported SMD is missing or empty: %s" % path)

    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        lines = [line.rstrip("\r\n") for line in stream]
    if not lines or lines[0].strip() != "version 1":
        raise RuntimeError("Unsupported or invalid SMD header: %s" % path)

    nodes = {}
    section = ""
    triangle_lines = []
    skeleton_has_time_zero = False
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in ("nodes", "skeleton", "triangles"):
            section = stripped
            continue
        if stripped == "end":
            section = ""
            continue
        if not stripped:
            continue
        if section == "nodes":
            match = re.match(r'^(-?\d+)\s+"(.*)"\s+(-?\d+)$', stripped)
            if not match:
                raise RuntimeError("Invalid SMD node line: %s" % line)
            nodes[int(match.group(1))] = {
                "name": match.group(2),
                "parent_index": int(match.group(3)),
            }
        elif section == "skeleton" and stripped == "time 0":
            skeleton_has_time_zero = True
        elif section == "triangles":
            triangle_lines.append(stripped)

    if not skeleton_has_time_zero:
        raise RuntimeError("SMD contains no bind-pose time 0 section: %s" % path)
    if len(triangle_lines) % 4:
        raise RuntimeError(
            "SMD triangle section is incomplete (%d lines): %s"
            % (len(triangle_lines), path))

    source_ids = [index for index, node in nodes.items()
                  if _short_name(node["name"]) == source_joint]
    target_ids = [index for index, node in nodes.items()
                  if _short_name(node["name"]) == target_joint]
    if len(source_ids) != 1 or len(target_ids) != 1:
        raise RuntimeError(
            "SMD joint verification failed: %s=%d, %s=%d"
            % (source_joint, len(source_ids), target_joint, len(target_ids)))
    source_parent_index = nodes[source_ids[0]]["parent_index"]
    source_parent = nodes.get(source_parent_index, {}).get("name")
    if _short_name(source_parent or "") != target_joint:
        raise RuntimeError(
            "SMD hierarchy verification failed: %s parent is %s, expected %s"
            % (source_joint, source_parent, target_joint))

    weighted_vertex_records = 0
    for offset in range(0, len(triangle_lines), 4):
        for vertex_line in triangle_lines[offset + 1:offset + 4]:
            values = vertex_line.split()
            if len(values) < 9:
                raise RuntimeError("Invalid SMD vertex line: %s" % vertex_line)
            # SMD v1 permits a rigid vertex record with only the first nine
            # fields. Weighted records append a link count and bone/weight
            # pairs. Accept both so third-party Maya translators can be used.
            if len(values) == 9:
                continue
            try:
                link_count = int(values[9])
            except ValueError as exc:
                raise RuntimeError(
                    "Invalid SMD vertex link count: %s" % vertex_line) from exc
            if len(values) != 10 + link_count * 2:
                raise RuntimeError("Incomplete SMD vertex weights: %s" % vertex_line)
            if link_count:
                weighted_vertex_records += 1

    return {
        "path": path,
        "size": os.path.getsize(path),
        "version": 1,
        "bone_count": len(nodes),
        "triangle_count": int(len(triangle_lines) / 4),
        "weighted_vertex_records": weighted_vertex_records,
        "source_match": nodes[source_ids[0]]["name"],
        "target_match": nodes[target_ids[0]]["name"],
        "source_parent": source_parent,
    }


def export_smd_from_cast(cast_path, smd_path,
                         source_joint=DEFAULT_SOURCE_JOINT,
                         target_joint=DEFAULT_TARGET_JOINT):
    """Convert one model Cast to Source SMD v1 without external plugins."""
    cast_path = _validate_cast_path(cast_path, "SMD conversion Cast")
    smd_path = os.path.normpath(os.path.abspath(smd_path))
    module = _castplugin_module()
    cast_file = module.Cast.load(cast_path)
    models = [model for root in cast_file.Roots()
              for model in root.ChildrenOfType(module.Model)]
    if len(models) != 1:
        raise RuntimeError(
            "SMD conversion requires exactly one Cast model; found %d"
            % len(models))
    model = models[0]
    skeleton = model.Skeleton()
    if skeleton is None:
        raise RuntimeError("SMD conversion Cast contains no skeleton")
    bones = list(skeleton.Bones())
    if not bones:
        raise RuntimeError("SMD conversion Cast contains no bones")

    output_dir = os.path.dirname(smd_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(smd_path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write("version 1\n")
        stream.write("nodes\n")
        for index, bone in enumerate(bones):
            stream.write('%d "%s" %d\n' % (
                index,
                _smd_safe_name(bone.Name(), "bone_%d" % index),
                int(bone.ParentIndex()),
            ))
        stream.write("end\n")

        stream.write("skeleton\n")
        stream.write("time 0\n")
        for index, bone in enumerate(bones):
            position = tuple(bone.LocalPosition() or (0.0, 0.0, 0.0))
            rotation = tuple(bone.LocalRotation() or (0.0, 0.0, 0.0, 1.0))
            quaternion = OpenMaya.MQuaternion(
                float(rotation[0]), float(rotation[1]),
                float(rotation[2]), float(rotation[3]))
            euler = quaternion.asEulerRotation()
            stream.write(
                "%d %.9g %.9g %.9g %.9g %.9g %.9g\n" % (
                    index,
                    float(position[0]), float(position[1]), float(position[2]),
                    float(euler.x), float(euler.y), float(euler.z),
                ))
        stream.write("end\n")

        stream.write("triangles\n")
        triangle_count = 0
        for mesh_index, mesh in enumerate(model.Meshes()):
            positions = mesh.VertexPositionBuffer()
            normals = mesh.VertexNormalBuffer()
            uv_values = mesh.VertexUVLayerBuffer(0) \
                if int(mesh.UVLayerCount() or 0) else None
            faces = list(mesh.FaceBuffer() or [])
            material = mesh.Material()
            material_name = _smd_safe_name(
                material.Name() if material is not None else None,
                mesh.Name() or "material_%d" % mesh_index,
            )
            for face_offset in range(0, len(faces), 3):
                if face_offset + 2 >= len(faces):
                    raise RuntimeError(
                        "Cast mesh %d has an incomplete triangle buffer"
                        % mesh_index)
                vertex_indices = [int(value)
                                  for value in faces[face_offset:face_offset + 3]]
                stream.write(material_name + "\n")
                for vertex_index in vertex_indices:
                    position = _cast_buffer_vector(
                        positions, vertex_index, 3, (0.0, 0.0, 0.0))
                    normal = _cast_buffer_vector(
                        normals, vertex_index, 3, (0.0, 0.0, 1.0))
                    uv = _cast_buffer_vector(
                        uv_values, vertex_index, 2, (0.0, 0.0))
                    weights = _cast_vertex_weights(
                        mesh, vertex_index, len(bones))
                    parent_bone = weights[0][0] if weights else 0
                    values = [
                        str(parent_bone),
                        "%.9g" % position[0], "%.9g" % position[1],
                        "%.9g" % position[2], "%.9g" % normal[0],
                        "%.9g" % normal[1], "%.9g" % normal[2],
                        "%.9g" % uv[0], "%.9g" % uv[1],
                        str(len(weights)),
                    ]
                    for bone_index, weight in weights:
                        values.extend((str(bone_index), "%.9g" % weight))
                    stream.write(" ".join(values) + "\n")
                triangle_count += 1
        stream.write("end\n")

    report = verify_exported_smd(
        smd_path, source_joint=source_joint, target_joint=target_joint)
    if report["triangle_count"] != triangle_count:
        raise RuntimeError(
            "SMD triangle count changed during verification: %d != %d"
            % (report["triangle_count"], triangle_count))
    report["source"] = "builtin_cast_converter"
    report["cast_source"] = cast_path
    return report


def _ensure_fbx_exporter():
    """Load Maya's official FBX plugin and return its export translator."""
    if not _is_plugin_loaded("fbxmaya"):
        try:
            cmds.loadPlugin("fbxmaya", quiet=True)
        except Exception as exc:
            raise RuntimeError(
                "Maya FBX plugin failed to load: %s" % exc) from exc
    translators = cmds.translator(query=True, list=True) or []
    for translator in translators:
        if str(translator).lower() == "fbx export":
            return str(translator)
    raise RuntimeError("Maya FBX export translator is unavailable")


def _fbx_property_query(path):
    return mel.eval('FBXProperty "%s" -q' % path)


def _fbx_property_set(path, value):
    mel.eval('FBXProperty "%s" -v %s' % (
        path, "true" if bool(value) else "false"))


@contextmanager
def _temporary_fbx_model_settings():
    """Disable animation while retaining geometry, skeletons, and skinning."""
    properties = (
        "Export|IncludeGrp|Animation",
        "Export|IncludeGrp|Animation|Deformation",
        "Export|IncludeGrp|Animation|Deformation|Skins",
        "Export|IncludeGrp|Animation|Deformation|Shape",
    )
    requested = (False, True, True, True)
    original = {}
    try:
        for path, value in zip(properties, requested):
            original[path] = _fbx_property_query(path)
            _fbx_property_set(path, value)
        yield
    finally:
        for path in reversed(properties):
            if path in original:
                _fbx_property_set(path, original[path])


def verify_exported_fbx(path):
    """Verify that a non-empty output has an FBX binary or ASCII signature."""
    path = os.path.normpath(os.path.abspath(path))
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        raise RuntimeError("Exported FBX is missing or empty: %s" % path)
    with open(path, "rb") as stream:
        header = stream.read(32)
    if header.startswith(b"Kaydara FBX Binary"):
        file_format = "binary"
    elif header.lstrip().startswith(b"; FBX"):
        file_format = "ascii"
    else:
        raise RuntimeError("Exported file has no valid FBX signature: %s" % path)
    return {
        "path": path,
        "size": os.path.getsize(path),
        "format": file_format,
    }


def export_fbx_model(path):
    """Export the current scene as a static FBX model with skinning."""
    path = os.path.normpath(os.path.abspath(path))
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    translator = _ensure_fbx_exporter()
    animation_curve_count = len(cmds.ls(type="animCurve") or [])
    with _temporary_fbx_model_settings():
        cmds.file(
            path,
            force=True,
            type=translator,
            exportAll=True,
            options="v=0;",
        )
    report = verify_exported_fbx(path)
    report["translator"] = translator
    report["animation_included"] = False
    report["animation_curve_count"] = animation_curve_count
    return report


def _registered_smd_translator():
    """Return a registered SMD export translator, if Maya has one."""
    translators = cmds.translator(query=True, list=True) or []
    candidates = [str(value) for value in translators
                  if "smd" in str(value).lower()]
    for candidate in candidates:
        lowered = candidate.lower()
        if "export" in lowered or "source" in lowered:
            return candidate
    return candidates[0] if candidates else ""


def _try_registered_smd_export(path, source_joint, target_joint):
    """Try an installed SMD translator; return a report or an error string."""
    translator = _registered_smd_translator()
    if not translator:
        return None, ""
    try:
        cmds.file(
            path,
            force=True,
            type=translator,
            exportAll=True,
            options="exportType=0;",
        )
        report = verify_exported_smd(path, source_joint, target_joint)
        report["source"] = "maya_translator"
        report["translator"] = translator
        return report, ""
    except Exception as exc:
        return None, "%s: %s" % (translator, exc)


@contextmanager
def _temporary_cast_import_settings(options):
    """Disable imported IK/constraints without persisting setting changes."""
    settings_sets = [
        module.sceneSettings for module in _loaded_castplugin_modules()
        if isinstance(getattr(module, "sceneSettings", None), dict)
    ]
    if not settings_sets:
        yield
        return

    requested = {
        "importIK": not options.disable_import_ik,
        "importConstraints": not options.disable_import_constraints,
    }
    originals = []
    try:
        for settings in settings_sets:
            original = {}
            for name, value in requested.items():
                if name in settings:
                    original[name] = settings[name]
                    settings[name] = value
            originals.append((settings, original))
        yield
    finally:
        for settings, original in reversed(originals):
            for name, value in original.items():
                settings[name] = value


@contextmanager
def _temporary_cast_export_settings():
    """Export a model-only Cast without changing persistent user settings."""
    settings_sets = [
        module.sceneSettings for module in _loaded_castplugin_modules()
        if isinstance(getattr(module, "sceneSettings", None), dict)
    ]
    if not settings_sets:
        raise RuntimeError("Cast plugin sceneSettings are unavailable")
    requested = {
        "exportModel": True,
        "exportAnim": False,
        "bakeKeyframes": False,
    }
    originals = []
    try:
        for settings in settings_sets:
            original = {}
            for name, value in requested.items():
                if name in settings:
                    original[name] = settings[name]
                    settings[name] = value
            originals.append((settings, original))
        yield
    finally:
        for settings, original in reversed(originals):
            for name, value in original.items():
                settings[name] = value


# ---------------------------------------------------------------------------
# Import isolation and node identity.
# ---------------------------------------------------------------------------

def _unique_namespace(base):
    candidate = base
    index = 1
    while cmds.namespace(exists=candidate):
        candidate = "%s%d" % (base, index)
        index += 1
    return candidate


def _long_names(nodes):
    resolved = []
    seen = set()
    for node in nodes or []:
        try:
            matches = cmds.ls(node, long=True) or []
        except Exception:
            matches = []
        for match in matches:
            if match not in seen:
                seen.add(match)
                resolved.append(match)
    return resolved


def import_cast(path, namespace):
    """Import one Cast file and return only nodes created by that import."""
    namespace = _unique_namespace(namespace)
    before_roots = set(cmds.ls(assemblies=True, long=True) or [])
    log("importing into namespace %s: %s" % (namespace, path))
    settings = getattr(_castplugin_module(), "sceneSettings", {})
    translator_options = "importIK=%d;importConstraints=%d" % (
        int(bool(settings.get("importIK", True))),
        int(bool(settings.get("importConstraints", True))),
    )

    new_nodes = cmds.file(
        path,
        i=True,
        type=cast_translator_name(),
        namespace=namespace,
        mergeNamespacesOnClash=False,
        returnNewNodes=True,
        ra=True,
        groupReference=False,
        options=translator_options,
    ) or []

    resolved_nodes = _long_names(new_nodes)
    after_roots = set(cmds.ls(assemblies=True, long=True) or [])
    roots = sorted(after_roots - before_roots)
    if not resolved_nodes:
        raise RuntimeError("Cast import returned no new nodes: %s" % path)

    return {
        "requested_namespace": namespace,
        "nodes": resolved_nodes,
        "roots": roots,
    }


def _node_uuid(node):
    values = cmds.ls(node, uuid=True) or []
    if len(values) != 1:
        raise RuntimeError("Unable to resolve a unique UUID for node: %s" % node)
    return values[0]


def _node_from_uuid(node_uuid):
    try:
        matches = cmds.ls(node_uuid, long=True) or []
    except Exception:
        matches = []
    if len(matches) == 1:
        return matches[0]

    for node in cmds.ls(long=True) or []:
        try:
            if node_uuid in (cmds.ls(node, uuid=True) or []):
                return node
        except Exception:
            continue
    raise RuntimeError("Node disappeared (UUID %s)" % node_uuid)


def _unique_scene_leaf(base):
    """Return a root-namespace leaf name that is unused in the scene."""
    candidate = base
    index = 1
    while cmds.ls(candidate, long=True):
        candidate = "%s%d" % (base, index)
        index += 1
    return candidate


def _resolve_viewhands_animation_joint(
        source_joint, source_uuid, target_uuid):
    """Find the renamed viewhands joint that owns source_joint animation."""
    expected = "viewhands_%s" % source_joint
    target_node = _node_from_uuid(target_uuid)
    target_parts = target_node.split("|")
    if len(target_parts) < 2:
        raise RuntimeError(
            "Unable to resolve the viewhands hierarchy root from %s"
            % target_node)
    hands_root = "|" + target_parts[1]
    candidates = []
    for node in cmds.ls(type="joint", long=True) or []:
        if _short_name(node) != expected:
            continue
        if node != hands_root and not node.startswith(hands_root + "|"):
            continue
        if _node_uuid(node) == source_uuid:
            continue
        candidates.append(node)
    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one viewhands animation joint named %s; "
            "found %d (%s)"
            % (expected, len(candidates), ", ".join(candidates) or "none"))
    return candidates[0]


@contextmanager
def _route_viewhands_animation_name(source_uuid, hand_uuid, source_joint):
    """Make the viewhands marker the sole source_joint during Cast import."""
    source_node = _node_from_uuid(source_uuid)
    hand_node = _node_from_uuid(hand_uuid)
    source_leaf = source_node.split("|")[-1]
    hand_leaf = hand_node.split("|")[-1]
    temporary_leaf = _unique_scene_leaf(
        "__attach_weapon_%s__" % source_joint)

    cmds.rename(source_node, temporary_leaf)
    try:
        hand_node = _node_from_uuid(hand_uuid)
        cmds.rename(hand_node, source_joint)
        renamed_hand = _node_from_uuid(hand_uuid)
        if _short_name(renamed_hand) != source_joint:
            raise RuntimeError(
                "Unable to expose the viewhands animation joint as %s: %s"
                % (source_joint, renamed_hand))
        yield renamed_hand
    finally:
        restore_errors = []
        try:
            hand_node = _node_from_uuid(hand_uuid)
            cmds.rename(hand_node, hand_leaf)
        except Exception as exc:
            restore_errors.append("viewhands joint: %s" % exc)
        try:
            source_node = _node_from_uuid(source_uuid)
            cmds.rename(source_node, source_leaf)
        except Exception as exc:
            restore_errors.append("weapon joint: %s" % exc)
        if restore_errors:
            raise RuntimeError(
                "Failed to restore animation routing names (%s)"
                % "; ".join(restore_errors))


def _resolve_unique_joint(imported_nodes, short_name, label):
    candidates = _joint_candidates(imported_nodes, short_name)

    if len(candidates) != 1:
        details = ", ".join(sorted(candidates.values())) or "none"
        raise RuntimeError(
            "%s import must create exactly one joint named %s; found %d (%s)"
            % (label, short_name, len(candidates), details))
    return next(iter(candidates.values()))


def _joint_candidates(imported_nodes, short_name):
    """Return UUID-to-path matches scoped to one import's returned nodes."""
    candidates = {}
    for node in imported_nodes:
        if not cmds.objExists(node):
            continue
        try:
            if cmds.nodeType(node) != "joint":
                continue
        except Exception:
            continue
        for long_name in cmds.ls(node, long=True) or []:
            if _short_name(long_name) == short_name:
                candidates[_node_uuid(long_name)] = long_name
    return candidates


def _rename_viewhands_joint_collisions(imported_nodes, weapon_joint_name):
    """Preserve same-named viewhands joints without colliding with the weapon."""
    renamed = []
    candidates = _joint_candidates(imported_nodes, weapon_joint_name)
    for node_uuid, old_path in candidates.items():
        leaf = old_path.split("|")[-1]
        namespace = leaf.rsplit(":", 1)[0] if ":" in leaf else ""
        new_leaf = "viewhands_%s" % weapon_joint_name
        if namespace:
            new_leaf = "%s:%s" % (namespace, new_leaf)
        new_path = cmds.rename(old_path, new_leaf)
        new_path = _node_from_uuid(node_uuid)
        renamed.append({
            "uuid": node_uuid,
            "old_path": old_path,
            "new_path": new_path,
        })
        log("renamed conflicting viewhands joint %s -> %s" %
            (old_path, new_path))
    return renamed


def _imported_joint_uuid_map(imported_nodes):
    """Map original short joint names to stable UUIDs for one import."""
    result = {}
    duplicates = []
    for node in imported_nodes:
        if not cmds.objExists(node):
            continue
        try:
            if cmds.nodeType(node) != "joint":
                continue
        except Exception:
            continue
        for long_name in cmds.ls(node, long=True) or []:
            short_name = _short_name(long_name)
            if short_name in result:
                duplicates.append(short_name)
            result[short_name] = _node_uuid(long_name)
    if duplicates:
        raise RuntimeError(
            "Imported skeleton contains duplicate joint names: %s"
            % ", ".join(sorted(set(duplicates))))
    return result


def _prefix_imported_joints(imported_nodes, prefix):
    """Give every joint in a weapon import a persistent side-unique name."""
    if not prefix or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", prefix):
        raise RuntimeError("Invalid dual-wield joint prefix: %r" % prefix)
    joint_map = _imported_joint_uuid_map(imported_nodes)
    for original_name, node_uuid in joint_map.items():
        node = _node_from_uuid(node_uuid)
        cmds.rename(node, prefix + original_name)
    for original_name, node_uuid in joint_map.items():
        actual = _short_name(_node_from_uuid(node_uuid))
        expected = prefix + original_name
        if actual != expected:
            raise RuntimeError(
                "Unable to persist dual-wield joint name %s; got %s"
                % (expected, actual))
    return joint_map


def _rename_uuid(node_uuid, leaf_name):
    cmds.rename(_node_from_uuid(node_uuid), leaf_name)
    return _node_from_uuid(node_uuid)


@contextmanager
def _route_dual_animation_names(state, side, selected_hand_names):
    """Expose only one hand branch and one weapon copy to the Cast importer."""
    if side not in DUAL_SIDES:
        raise RuntimeError("Dual animation side must be left or right")
    hands = state["hands_joint_uuids"]
    weapon = state["%s_weapon_joint_uuids" % side]
    source_joint = state["source_joint"]
    persistent_prefix = state["%s_prefix" % side]
    selected_hand_names = set(selected_hand_names)
    restore = []

    def rename_temporarily(node_uuid, new_leaf):
        old_leaf = _node_from_uuid(node_uuid).split("|")[-1]
        _rename_uuid(node_uuid, new_leaf)
        restore.append((node_uuid, old_leaf))

    try:
        for index, (name, node_uuid) in enumerate(sorted(hands.items())):
            if name in selected_hand_names:
                continue
            temporary = _unique_scene_leaf(
                "__attach_skip_%s_%03d_%s__" % (side, index, name))
            rename_temporarily(node_uuid, temporary)

        if source_joint in selected_hand_names:
            hand_uuid = hands.get(source_joint)
            if not hand_uuid:
                raise RuntimeError(
                    "Viewhands animation marker is missing: %s" % source_joint)
            rename_temporarily(hand_uuid, source_joint)

        for original_name, node_uuid in sorted(weapon.items()):
            if original_name == source_joint:
                continue
            expected = persistent_prefix + original_name
            if _short_name(_node_from_uuid(node_uuid)) != expected:
                raise RuntimeError(
                    "Dual weapon joint name changed before import: %s"
                    % _node_from_uuid(node_uuid))
            rename_temporarily(node_uuid, original_name)
        yield
    finally:
        restore_errors = []
        for node_uuid, old_leaf in reversed(restore):
            try:
                _rename_uuid(node_uuid, old_leaf)
            except Exception as exc:
                restore_errors.append("%s: %s" % (old_leaf, exc))
        if restore_errors:
            raise RuntimeError(
                "Failed to restore dual animation routing names (%s)"
                % "; ".join(restore_errors))


@contextmanager
def _temporary_cast_animation_settings(import_at_time=False):
    settings_sets = [
        module.sceneSettings for module in _loaded_castplugin_modules()
        if isinstance(getattr(module, "sceneSettings", None), dict)
    ]
    if not settings_sets:
        yield
        return
    requested = {
        "importAtTime": bool(import_at_time),
        "importReset": False,
        "importLooping": False,
    }
    originals = []
    try:
        for settings in settings_sets:
            original = {}
            for name, value in requested.items():
                if name in settings:
                    original[name] = settings[name]
                    settings[name] = value
            originals.append((settings, original))
        yield
    finally:
        for settings, original in reversed(originals):
            for name, value in original.items():
                settings[name] = value


def _cast_animation_import_options(import_at_time=False):
    """Pin non-destructive animation behavior on the translator call itself."""
    return "importAtTime=%d;importReset=0;importLooping=0" % int(
        bool(import_at_time))


def _animation_curves_for_uuids(node_uuids):
    curves = set()
    for node_uuid in node_uuids:
        node = _node_from_uuid(node_uuid)
        for curve in cmds.listConnections(
                node, source=True, destination=False, type="animCurve") or []:
            curves.add(curve)
    return sorted(curves)


def _curve_time_range(curves):
    key_times = cmds.keyframe(curves, query=True, timeChange=True) or []
    if not key_times:
        return ()
    return (float(min(key_times)), float(max(key_times)))


def _import_dual_animation_side(
        state, side, animation_path, selected_hand_names, frame_offset=0.0):
    animation_path = _validate_cast_path(
        animation_path, "%s animation" % side.title())
    ensure_cast_plugin()
    framerate = _set_scene_framerate_from_animation(animation_path)
    selected_hand_names = set(selected_hand_names)
    selected_hand_uuids = [
        node_uuid for name, node_uuid in state["hands_joint_uuids"].items()
        if name in selected_hand_names]
    weapon_uuids = list(
        state["%s_weapon_joint_uuids" % side].values())
    source_uuid = state["%s_source_uuid" % side]
    routed_uuids = selected_hand_uuids + [
        value for value in weapon_uuids if value != source_uuid]

    cmds.currentTime(float(frame_offset), edit=True)
    log("importing %s dual animation at offset %s: %s" % (
        side, frame_offset, animation_path))
    import_at_time = abs(float(frame_offset)) > 1e-6
    with _temporary_cast_animation_settings(import_at_time=import_at_time):
        with _route_dual_animation_names(
                state, side, selected_hand_names):
            new_nodes = cmds.file(
                animation_path,
                i=True,
                type=cast_translator_name(),
                returnNewNodes=True,
                ra=True,
                groupReference=False,
                options=_cast_animation_import_options(import_at_time),
            ) or []

    curves = _animation_curves_for_uuids(routed_uuids)
    source_root = _node_from_uuid(source_uuid)
    _zero_translation(source_root, remove_animation=True)
    return {
        "side": side,
        "animation_path": animation_path,
        "framerate": framerate,
        "frame_offset": float(frame_offset),
        "selected_hand_joint_count": len(selected_hand_uuids),
        "weapon_joint_count": len(weapon_uuids),
        "new_node_count": len(new_nodes),
        "anim_curve_count": len(curves),
        "curve_range": _curve_time_range(curves),
    }


def _namespace_of(node):
    leaf = str(node).split("|")[-1]
    if ":" not in leaf:
        return ""
    return leaf.rsplit(":", 1)[0]


# ---------------------------------------------------------------------------
# Attachment, validation, and output.
# ---------------------------------------------------------------------------

def _incoming_plugs(attribute):
    return cmds.listConnections(
        attribute, source=True, destination=False, plugs=True) or []


def _zero_translation(node, remove_animation=False):
    for axis in "XYZ":
        attribute = "%s.translate%s" % (node, axis)
        if cmds.getAttr(attribute, lock=True):
            raise RuntimeError("Translation attribute is locked: %s" % attribute)

        incoming = _incoming_plugs(attribute)
        if incoming and remove_animation:
            for source_plug in list(incoming):
                source_node = source_plug.split(".", 1)[0]
                node_type = cmds.nodeType(source_node)
                if not node_type.startswith("animCurve"):
                    raise RuntimeError(
                        "Cannot protect %s; it is driven by %s (%s)"
                        % (attribute, source_node, node_type))
                cmds.disconnectAttr(source_plug, attribute)
                destinations = cmds.listConnections(
                    source_node, source=False, destination=True) or []
                if not destinations and cmds.objExists(source_node):
                    cmds.delete(source_node)
            incoming = _incoming_plugs(attribute)

        if incoming:
            raise RuntimeError(
                "Cannot zero %s; incoming connection(s): %s"
                % (attribute, ", ".join(incoming)))
        if not cmds.getAttr(attribute, settable=True):
            raise RuntimeError("Translation attribute is not settable: %s" % attribute)
        cmds.setAttr(attribute, 0)


def _find_current_attachment(source_joint, target_joint):
    pairs = []
    for source in cmds.ls(type="joint", long=True) or []:
        if _short_name(source) != source_joint:
            continue
        parent = cmds.listRelatives(source, parent=True, fullPath=True) or []
        if len(parent) != 1:
            continue
        if cmds.nodeType(parent[0]) != "joint":
            continue
        if _short_name(parent[0]) == target_joint:
            pairs.append((source, parent[0]))

    if len(pairs) != 1:
        raise RuntimeError(
            "Expected exactly one current attachment %s -> %s; found %d"
            % (source_joint, target_joint, len(pairs)))
    return pairs[0]


def validate_attachment(source_joint=DEFAULT_SOURCE_JOINT,
                        target_joint=DEFAULT_TARGET_JOINT,
                        source_node=None,
                        target_node=None):
    """Verify direct parenting and zero local translation."""
    if source_node is None or target_node is None:
        source_node, target_node = _find_current_attachment(
            source_joint, target_joint)
    else:
        source_node = _node_from_uuid(_node_uuid(source_node))
        target_node = _node_from_uuid(_node_uuid(target_node))

    parent = cmds.listRelatives(source_node, parent=True, fullPath=True) or []
    if len(parent) != 1:
        raise RuntimeError("Source joint does not have exactly one parent: %s" % source_node)
    if _node_uuid(parent[0]) != _node_uuid(target_node):
        raise RuntimeError(
            "Incorrect direct parent: expected %s, got %s"
            % (target_node, parent[0]))

    translation = tuple(float(value) for value in cmds.getAttr(
        source_node + ".translate")[0])
    if not all(abs(value) < 1e-6 for value in translation):
        raise RuntimeError("Translation is not zero: %s" % (translation,))

    return {
        "source_node": source_node,
        "target_node": target_node,
        "source_uuid": _node_uuid(source_node),
        "target_uuid": _node_uuid(target_node),
        "parent_node": parent[0],
        "translation": translation,
    }


def _safe_stem(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
    return stem or "weapon"


def selected_output_formats(options):
    """Return selected disk formats in stable UI/export order."""
    formats = []
    if options.save_scene:
        formats.append("ma")
    if options.export_cast:
        formats.append("cast")
    if options.export_smd:
        formats.append("smd")
    if options.export_fbx:
        formats.append("fbx")
    return tuple(formats)


def validate_output_options(options):
    """Reject a run that would produce no user-selected output file."""
    formats = selected_output_formats(options)
    if not formats:
        raise RuntimeError(
            "Select at least one output format: .ma, .cast, .smd, or .fbx")
    return formats


def resolved_output_directories(options, common_output_dir=None):
    """Resolve per-format directories, using the common folder as fallback."""
    common = common_output_dir or options.output_dir or DEFAULT_OUTPUT_DIR
    common = os.path.normpath(os.path.abspath(common))

    def resolve(value):
        return os.path.normpath(os.path.abspath(value or common))

    return {
        "manifest": common,
        "scene": resolve(options.ma_output_dir),
        "cast": resolve(options.cast_output_dir),
        "smd": resolve(options.smd_output_dir),
        "fbx": resolve(options.fbx_output_dir),
    }


def _versioned_output_paths(
        output_dir, weapon_path, options=None, base_prefix="attached"):
    options = options or AttachOptions()
    validate_output_options(options)
    directories = resolved_output_directories(options, output_dir)
    enabled = {
        "scene": bool(options.save_scene),
        "cast": bool(options.export_cast),
        "smd": bool(options.export_smd),
        "fbx": bool(options.export_fbx),
    }
    active_directories = {directories["manifest"]}
    active_directories.update(
        directories[name] for name, is_enabled in enabled.items()
        if is_enabled)
    for directory in active_directories:
        os.makedirs(directory, exist_ok=True)

    base = "%s_%s" % (base_prefix, _safe_stem(weapon_path))
    for version in range(1, 10000):
        versioned_stem = "%s_v%03d" % (base, version)
        possible_paths = {
            "scene": os.path.join(
                directories["scene"], versioned_stem + ".ma"),
            "cast": os.path.join(
                directories["cast"], versioned_stem + ".cast"),
            "smd": os.path.join(
                directories["smd"], versioned_stem + ".smd"),
            "fbx": os.path.join(
                directories["fbx"], versioned_stem + ".fbx"),
            "manifest": os.path.join(
                directories["manifest"], versioned_stem + ".json"),
        }
        occupied_paths = [possible_paths["manifest"]]
        occupied_paths.extend(
            possible_paths[name] for name, is_enabled in enabled.items()
            if is_enabled)
        if not any(os.path.exists(path) for path in occupied_paths):
            return {
                "scene": possible_paths["scene"] if options.save_scene else "",
                "cast": possible_paths["cast"] if options.export_cast else "",
                "smd": possible_paths["smd"] if options.export_smd else "",
                "fbx": possible_paths["fbx"] if options.export_fbx else "",
                "manifest": possible_paths["manifest"],
            }
    raise RuntimeError(
        "Unable to allocate a shared output version in: %s"
        % ", ".join(sorted(active_directories)))


def _write_manifest(result):
    if not result.output_manifest:
        return
    payload = asdict(result)
    payload["output_scene_exists"] = os.path.isfile(result.output_scene)
    payload["output_scene_size"] = (
        os.path.getsize(result.output_scene)
        if os.path.isfile(result.output_scene) else 0)
    payload["output_cast_exists"] = os.path.isfile(result.output_cast)
    payload["output_cast_size"] = (
        os.path.getsize(result.output_cast)
        if os.path.isfile(result.output_cast) else 0)
    payload["output_smd_exists"] = os.path.isfile(result.output_smd)
    payload["output_smd_size"] = (
        os.path.getsize(result.output_smd)
        if os.path.isfile(result.output_smd) else 0)
    payload["output_fbx_exists"] = os.path.isfile(result.output_fbx)
    payload["output_fbx_size"] = (
        os.path.getsize(result.output_fbx)
        if os.path.isfile(result.output_fbx) else 0)
    with open(result.output_manifest, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)


def _require_cast_model_export_version():
    try:
        version_parts = tuple(
            int(part) for part in cast_plugin_version().split(".")[:2])
    except Exception:
        version_parts = (0, 0)
    if version_parts < (1, 99):
        raise RuntimeError(
            "Model export requires Cast plugin v1.99 or newer; loaded "
            "version is %s" % cast_plugin_version())


def _export_model_cast(path, result, verify=True):
    """Export the current scene as a model-only Cast."""
    _require_cast_model_export_version()
    log("exporting combined model Cast: %s" % path)
    with _temporary_cast_export_settings():
        cmds.file(
            path,
            force=True,
            type=cast_translator_name(),
            exportAll=True,
            options="exportModel=1;exportAnim=0;bakeKeyframes=0",
        )
    if not os.path.isfile(path) or os.path.getsize(path) <= 0:
        raise RuntimeError("Combined Cast was not written correctly: %s" % path)
    if verify:
        left_report = verify_exported_cast(
            path, result.source_joint_name, result.target_joint_name)
        if isinstance(result, DualWieldResult):
            right_report = verify_exported_cast(
                path,
                _short_name(result.right_source_node),
                _short_name(result.right_target_node),
            )
            return {
                "path": path,
                "size": left_report["size"],
                "model_count": left_report["model_count"],
                "animation_count": left_report["animation_count"],
                "skeleton_count": left_report["skeleton_count"],
                "bone_count": left_report["bone_count"],
                "mesh_count": left_report["mesh_count"],
                "left": left_report,
                "right": right_report,
            }
        return left_report
    return {}


def _allocate_result_output_paths(result, output_dir, options):
    base_prefix = (
        "dual_attached" if isinstance(result, DualWieldResult)
        else "attached")
    paths = _versioned_output_paths(
        output_dir,
        result.weapon_path,
        options,
        base_prefix=base_prefix,
    )
    result.output_scene = paths["scene"]
    result.output_cast = paths["cast"]
    result.output_smd = paths["smd"]
    result.output_fbx = paths["fbx"]
    result.output_manifest = paths["manifest"]
    result.requested_outputs = {
        "ma": bool(options.save_scene),
        "cast": bool(options.export_cast),
        "smd": bool(options.export_smd),
        "fbx": bool(options.export_fbx),
    }


def _export_result_smd(result):
    """Export SMD through Maya when available, otherwise via model Cast."""
    report, translator_error = _try_registered_smd_export(
        result.output_smd,
        result.source_joint_name,
        result.target_joint_name,
    )
    if report:
        if isinstance(result, DualWieldResult):
            report = {
                "left": report,
                "right": verify_exported_smd(
                    result.output_smd,
                    _short_name(result.right_source_node),
                    _short_name(result.right_target_node),
                ),
                "bone_count": report["bone_count"],
                "triangle_count": report["triangle_count"],
                "source": report.get("source", "maya_translator"),
            }
        return report
    if translator_error:
        warning = (
            "Installed SMD translator failed; used the built-in Cast-to-SMD "
            "converter instead (%s)" % translator_error)
        result.warnings.append(warning)
        log("WARNING: %s" % warning)

    temporary_cast = ""
    cast_source = result.output_cast
    try:
        if not cast_source:
            output_dir = os.path.dirname(result.output_smd)
            descriptor, temporary_cast = tempfile.mkstemp(
                prefix="viewmodel_weapon_toolkit_smd_",
                suffix=".cast", dir=output_dir)
            os.close(descriptor)
            _export_model_cast(temporary_cast, result, verify=False)
            cast_source = temporary_cast
        log("exporting Source model SMD: %s" % result.output_smd)
        report = export_smd_from_cast(
            cast_source,
            result.output_smd,
            result.source_joint_name,
            result.target_joint_name,
        )
        report["cast_source_temporary"] = bool(temporary_cast)
        if isinstance(result, DualWieldResult):
            left_report = report
            report = {
                "left": left_report,
                "right": verify_exported_smd(
                    result.output_smd,
                    _short_name(result.right_source_node),
                    _short_name(result.right_target_node),
                ),
                "bone_count": left_report["bone_count"],
                "triangle_count": left_report["triangle_count"],
                "source": left_report.get("source", "builtin_cast_converter"),
                "cast_source_temporary": bool(temporary_cast),
            }
        return report
    finally:
        if temporary_cast and os.path.isfile(temporary_cast):
            os.remove(temporary_cast)


def _write_result_outputs(result, options, allocate=True):
    """Write every selected output using one shared versioned basename."""
    validate_output_options(options)
    if allocate:
        _allocate_result_output_paths(result, options.output_dir, options)

    if options.save_scene:
        if not result.output_scene:
            raise RuntimeError("Maya ASCII output path was not allocated")
        log("saving Maya ASCII: %s" % result.output_scene)
        cmds.file(rename=result.output_scene)
        cmds.file(save=True, type="mayaAscii", force=True)
        if (not os.path.isfile(result.output_scene)
                or os.path.getsize(result.output_scene) <= 0):
            raise RuntimeError(
                "Maya scene was not written correctly: %s"
                % result.output_scene)

    if options.export_cast:
        if not result.output_cast:
            raise RuntimeError("Cast output path was not allocated")
        result.cast_verification = _export_model_cast(
            result.output_cast, result, verify=True)

    if options.export_smd:
        if not result.output_smd:
            raise RuntimeError("SMD output path was not allocated")
        result.smd_verification = _export_result_smd(result)

    if options.export_fbx:
        if not result.output_fbx:
            raise RuntimeError("FBX output path was not allocated")
        log("exporting static model FBX: %s" % result.output_fbx)
        result.fbx_verification = export_fbx_model(result.output_fbx)

    _write_manifest(result)


def attach_gun(viewhands_path, weapon_path, options=None):
    """Attach one weapon and write the selected versioned outputs."""
    global _LAST_RESULT

    options = options or AttachOptions()
    options.source_joint = options.source_joint.strip()
    options.target_joint = options.target_joint.strip()
    options.output_dir = os.path.normpath(os.path.abspath(
        options.output_dir or DEFAULT_OUTPUT_DIR))
    validate_output_options(options)

    viewhands_path = _validate_cast_path(viewhands_path, "Viewhands")
    weapon_path = _validate_cast_path(weapon_path, "Weapon")
    preflight = preflight_inputs(
        viewhands_path,
        weapon_path,
        source_joint=options.source_joint,
        target_joint=options.target_joint,
    )

    if cmds.file(query=True, modified=True) and not options.force_new_scene:
        raise RuntimeError(
            "Current Maya scene has unsaved changes. Save it or explicitly "
            "approve discarding it before running %s." % PRODUCT_NAME)

    log("=== %s v%s start ===" % (PRODUCT_NAME, VERSION))
    log("mapping weapon:%s -> viewhands:%s" % (
        options.source_joint, options.target_joint))
    warnings = []

    with _temporary_cast_import_settings(options):
        cmds.file(new=True, force=options.force_new_scene)

        hands_import = import_cast(viewhands_path, HANDS_NAMESPACE)
        target_node = _resolve_unique_joint(
            hands_import["nodes"], options.target_joint, "Viewhands")
        target_uuid = _node_uuid(target_node)
        renamed_collisions = _rename_viewhands_joint_collisions(
            hands_import["nodes"], options.source_joint)
        for collision in renamed_collisions:
            warnings.append(
                "Renamed the viewhands joint that collided with the weapon "
                "joint: %s -> %s"
                % (collision["old_path"], collision["new_path"]))

        weapon_import = import_cast(weapon_path, WEAPON_NAMESPACE)
        source_node = _resolve_unique_joint(
            weapon_import["nodes"], options.source_joint, "Weapon")
        source_uuid = _node_uuid(source_node)

    target_node = _node_from_uuid(target_uuid)
    source_node = _node_from_uuid(source_uuid)
    hands_namespace = _namespace_of(target_node)
    weapon_namespace = _namespace_of(source_node)
    if not hands_namespace:
        warnings.append("Cast translator ignored the requested hands namespace")
    if not weapon_namespace:
        warnings.append("Cast translator ignored the requested weapon namespace")
    for label, report in (("Viewhands", preflight["viewhands"]),
                          ("Weapon", preflight["weapon"])):
        if report["unused_vertex_count"]:
            warnings.append(
                "%s source contains %d vertices not referenced by faces; "
                "they are preserved and receive safe default UVs if Maya "
                "cannot expose their original UV assignment"
                % (label, report["unused_vertex_count"]))

    log("parenting %s under %s" % (source_node, target_node))
    cmds.parent(source_node, target_node, absolute=True)
    source_node = _node_from_uuid(source_uuid)
    target_node = _node_from_uuid(target_uuid)

    _zero_translation(source_node, remove_animation=False)
    verification = validate_attachment(
        options.source_joint,
        options.target_joint,
        source_node=source_node,
        target_node=target_node,
    )

    result = AttachResult(
        plugin_version=VERSION,
        cast_plugin_version=cast_plugin_version(),
        created_at=datetime.datetime.now().astimezone().isoformat(),
        viewhands_path=viewhands_path,
        weapon_path=weapon_path,
        viewhands_size=os.path.getsize(viewhands_path),
        weapon_size=os.path.getsize(weapon_path),
        source_joint_name=options.source_joint,
        target_joint_name=options.target_joint,
        source_node=verification["source_node"],
        target_node=verification["target_node"],
        source_uuid=verification["source_uuid"],
        target_uuid=verification["target_uuid"],
        parent_node=verification["parent_node"],
        translation=verification["translation"],
        hands_namespace=hands_namespace,
        weapon_namespace=weapon_namespace,
        hands_roots=hands_import["roots"],
        weapon_roots=weapon_import["roots"],
        translation_protected=options.protect_translation,
        preflight=preflight,
        warnings=warnings,
    )

    _write_result_outputs(result, options, allocate=True)

    _LAST_RESULT = result
    log("VERIFY parent=%s" % result.parent_node)
    log("VERIFY translation=%s" % (result.translation,))
    for label, path in (
            ("ma", result.output_scene),
            ("cast", result.output_cast),
            ("smd", result.output_smd),
            ("fbx", result.output_fbx),
            ("manifest", result.output_manifest)):
        if path:
            log("OUTPUT %s=%s" % (label, path))
    log("=== %s done ===" % PRODUCT_NAME)
    return result


def _create_dual_state(state):
    existing = cmds.ls(DUAL_STATE_NODE, type="network") or []
    if existing:
        raise RuntimeError(
            "A dual-wield state node already exists: %s" % existing[0])
    node = cmds.createNode("network", name=DUAL_STATE_NODE)
    cmds.addAttr(node, longName="attachGunDualJson", dataType="string")
    cmds.setAttr(
        node + ".attachGunDualJson",
        json.dumps(state, ensure_ascii=False, sort_keys=True),
        type="string",
    )
    return node


def _read_dual_state():
    nodes = cmds.ls(DUAL_STATE_NODE, type="network") or []
    if len(nodes) != 1:
        raise RuntimeError(
            "Expected exactly one %s metadata node; found %d"
            % (DUAL_STATE_NODE, len(nodes)))
    attribute = nodes[0] + ".attachGunDualJson"
    if not cmds.objExists(attribute):
        raise RuntimeError("Dual-wield metadata attribute is missing")
    try:
        state = json.loads(cmds.getAttr(attribute) or "")
    except Exception as exc:
        raise RuntimeError("Dual-wield metadata is invalid: %s" % exc)
    if state.get("schema_version") != 1:
        raise RuntimeError(
            "Unsupported dual-wield metadata schema: %r"
            % state.get("schema_version"))
    required = (
        "animation_mode",
        "shared_hands_source",
        "source_joint",
        "left_target_joint",
        "right_target_joint",
        "left_prefix",
        "right_prefix",
        "hands_joint_uuids",
        "left_weapon_joint_uuids",
        "right_weapon_joint_uuids",
        "left_source_uuid",
        "right_source_uuid",
        "left_target_uuid",
        "right_target_uuid",
        "left_clip_range",
        "right_clip_range",
        "playback_range",
        "framerate",
        "viewhands_path",
        "weapon_path",
        "left_animation_path",
        "right_animation_path",
        "expected_joint_count",
        "expected_mesh_count",
    )
    missing = [name for name in required if name not in state]
    if missing:
        raise RuntimeError(
            "Dual-wield metadata is missing: %s" % ", ".join(missing))
    # Output bookkeeping was written after the first validation in 3.0/3.0.1.
    # Recover an interrupted build far enough to report its real rig or
    # animation problem, while keeping structural metadata strict above.
    output_keys = {
        "ma": "output_scene",
        "cast": "output_cast",
        "smd": "output_smd",
        "fbx": "output_fbx",
    }
    for state_key in tuple(output_keys.values()) + ("output_manifest",):
        state.setdefault(state_key, "")
    state.setdefault("requested_outputs", {
        output: bool(state[state_key])
        for output, state_key in output_keys.items()
    })
    return nodes[0], state


def _write_dual_state(node, state):
    cmds.setAttr(
        node + ".attachGunDualJson",
        json.dumps(state, ensure_ascii=False, sort_keys=True),
        type="string",
    )


def _validate_dual_side(state, side):
    source_uuid = state["%s_source_uuid" % side]
    target_uuid = state["%s_target_uuid" % side]
    source_node = _node_from_uuid(source_uuid)
    target_node = _node_from_uuid(target_uuid)
    verification = validate_attachment(
        state["%s_prefix" % side] + state["source_joint"],
        state["%s_target_joint" % side],
        source_node=source_node,
        target_node=target_node,
    )
    expected_name = state["%s_prefix" % side] + state["source_joint"]
    if _short_name(source_node) != expected_name:
        raise RuntimeError(
            "%s weapon root name changed: expected %s, got %s"
            % (side.title(), expected_name, _short_name(source_node)))
    root_curves = _animation_curves_for_uuids([source_uuid])
    if root_curves:
        raise RuntimeError(
            "%s weapon root received animation curves: %s"
            % (side.title(), ", ".join(root_curves)))
    weapon_uuids = [
        node_uuid
        for node_uuid in state[
            "%s_weapon_joint_uuids" % side].values()
        if node_uuid != source_uuid]
    weapon_curves = _animation_curves_for_uuids(weapon_uuids)
    if not weapon_curves:
        raise RuntimeError(
            "%s weapon contains no imported animation curves" % side.title())
    expected_range = tuple(
        float(value) for value in state["%s_clip_range" % side])
    actual_range = _curve_time_range(weapon_curves)
    if len(actual_range) != 2 or any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(actual_range, expected_range)):
        raise RuntimeError(
            "%s weapon curve range is %s; expected %s"
            % (side.title(), actual_range, expected_range))
    verification["anim_curve_count"] = len(weapon_curves)
    verification["curve_range"] = actual_range
    return verification


def validate_dual_wield():
    """Validate a persisted Dual-Wield Builder scene after save/reopen."""
    state_node, state = _read_dual_state()
    if state.get("shared_hands_source") != "right":
        raise RuntimeError(
            "Dual-wield shared hands tracks must use the right animation")
    temporary_names = [
        node for node in cmds.ls(long=True) or []
        if "__attach_skip_" in node or "__attach_weapon_" in node]
    if temporary_names:
        raise RuntimeError(
            "Temporary animation routing names remain: %s"
            % ", ".join(temporary_names))
    left = _validate_dual_side(state, "left")
    right = _validate_dual_side(state, "right")
    playback_range = (
        float(cmds.playbackOptions(query=True, minTime=True)),
        float(cmds.playbackOptions(query=True, maxTime=True)),
    )
    expected_range = tuple(float(value) for value in state["playback_range"])
    if any(abs(actual - expected) > 1e-6
           for actual, expected in zip(playback_range, expected_range)):
        raise RuntimeError(
            "Dual playback range changed: expected %s, got %s"
            % (expected_range, playback_range))
    actual_joint_count = len(cmds.ls(type="joint") or [])
    actual_mesh_count = len([
        node for node in cmds.ls(type="mesh", long=True) or []
        if not cmds.getAttr(node + ".intermediateObject")])
    if actual_joint_count != int(state["expected_joint_count"]):
        raise RuntimeError(
            "Dual joint count changed: expected %s, got %s"
            % (state["expected_joint_count"], actual_joint_count))
    if actual_mesh_count != int(state["expected_mesh_count"]):
        raise RuntimeError(
            "Dual mesh count changed: expected %s, got %s"
            % (state["expected_mesh_count"], actual_mesh_count))

    if state["animation_mode"] == "simultaneous":
        for side in DUAL_SIDES:
            hand_names = {
                name for name in state["hands_joint_uuids"]
                if _side_from_joint_name(name) == side}
            hand_curves = _animation_curves_for_uuids(
                state["hands_joint_uuids"][name]
                for name in hand_names)
            hand_range = _curve_time_range(hand_curves)
            expected = tuple(
                float(value)
                for value in state["%s_clip_range" % side])
            if not hand_curves or len(hand_range) != 2 or any(
                    abs(actual - wanted) > 1e-6
                    for actual, wanted in zip(hand_range, expected)):
                raise RuntimeError(
                    "%s hands branch curve range is %s; expected %s"
                    % (side.title(), hand_range, expected))
        shared_uuids = [
            node_uuid
            for name, node_uuid in state["hands_joint_uuids"].items()
            if _side_from_joint_name(name) == "shared"]
        shared_curves = _animation_curves_for_uuids(shared_uuids)
        shared_range = _curve_time_range(shared_curves)
        expected_shared_range = tuple(
            float(value) for value in state["right_clip_range"])
        if not shared_curves or len(shared_range) != 2 or any(
                abs(actual - wanted) > 1e-6
                for actual, wanted in zip(
                    shared_range, expected_shared_range)):
            raise RuntimeError(
                "Shared hands curve range is %s; expected right clip %s"
                % (shared_range, expected_shared_range))
    else:
        shared_uuids = [
            node_uuid
            for name, node_uuid in state["hands_joint_uuids"].items()
            if _side_from_joint_name(name) == "shared"]
        shared_curves = _animation_curves_for_uuids(shared_uuids)
        shared_times = cmds.keyframe(
            shared_curves, query=True, timeChange=True) or []
        for side in DUAL_SIDES:
            clip_range = tuple(
                float(value)
                for value in state["%s_clip_range" % side])
            if not any(clip_range[0] <= float(time) <= clip_range[1]
                       for time in shared_times):
                raise RuntimeError(
                    "Shared hands tracks contain no keys in the %s clip"
                    % side)
    return {
        "state_node": state_node,
        "animation_mode": state["animation_mode"],
        "shared_hands_source": state["shared_hands_source"],
        "playback_range": playback_range,
        "left_clip_range": tuple(state["left_clip_range"]),
        "right_clip_range": tuple(state["right_clip_range"]),
        "left": left,
        "right": right,
        "joint_count": actual_joint_count,
        "mesh_count": actual_mesh_count,
        "warnings": list(state.get("warnings", [])),
    }


def _dual_selected_hand_names(hands_joint_uuids, side, mode, master):
    if mode == "sequential":
        return set(hands_joint_uuids)
    selected = {
        name for name in hands_joint_uuids
        if _side_from_joint_name(name) == side}
    if side == master:
        selected.update(
            name for name in hands_joint_uuids
            if _side_from_joint_name(name) == "shared")
    return selected


def attach_dual_wield(
        viewhands_path,
        weapon_path,
        left_animation_path,
        right_animation_path,
        options=None):
    """Build two copies of one weapon and compose both Akimbo animations."""
    global _LAST_RESULT

    options = options or DualWieldOptions()
    options.source_joint = options.source_joint.strip()
    options.left_target_joint = options.left_target_joint.strip()
    options.right_target_joint = options.right_target_joint.strip()
    options.left_prefix = options.left_prefix.strip()
    options.right_prefix = options.right_prefix.strip()
    options.output_dir = os.path.normpath(os.path.abspath(
        options.output_dir or DEFAULT_OUTPUT_DIR))
    if options.animation_mode not in DUAL_ANIMATION_MODES:
        raise RuntimeError(
            "Dual animation mode must be simultaneous or sequential")
    if options.shared_hands_source != "right":
        raise RuntimeError(
            "Simultaneous shared hands tracks must use the right animation")
    if options.left_prefix == options.right_prefix:
        raise RuntimeError("Left and right weapon prefixes must differ")
    validate_output_options(options)

    preflight = preflight_dual_inputs(
        viewhands_path,
        weapon_path,
        left_animation_path,
        right_animation_path,
        animation_mode=options.animation_mode,
        source_joint=options.source_joint,
        left_target_joint=options.left_target_joint,
        right_target_joint=options.right_target_joint,
    )
    viewhands_path = _validate_cast_path(viewhands_path, "Viewhands")
    weapon_path = _validate_cast_path(weapon_path, "Weapon")
    left_animation_path = _validate_cast_path(
        left_animation_path, "Left animation")
    right_animation_path = _validate_cast_path(
        right_animation_path, "Right animation")
    if cmds.file(query=True, modified=True) and not options.force_new_scene:
        raise RuntimeError(
            "Current Maya scene has unsaved changes. Save it or explicitly "
            "approve discarding it before building Dual-Wield.")

    log("=== attach_dual_wield v%s start ===" % VERSION)
    warnings = list(preflight["warnings"])
    structural_warnings = []
    with _temporary_cast_import_settings(options):
        cmds.file(new=True, force=options.force_new_scene)
        hands_import = import_cast(viewhands_path, HANDS_NAMESPACE)
        hands_joint_uuids = _imported_joint_uuid_map(hands_import["nodes"])
        left_target = _resolve_unique_joint(
            hands_import["nodes"], options.left_target_joint, "Viewhands")
        right_target = _resolve_unique_joint(
            hands_import["nodes"], options.right_target_joint, "Viewhands")
        left_target_uuid = _node_uuid(left_target)
        right_target_uuid = _node_uuid(right_target)
        renamed_collisions = _rename_viewhands_joint_collisions(
            hands_import["nodes"], options.source_joint)
        for collision in renamed_collisions:
            warning = "Renamed the viewhands animation marker: %s -> %s" % (
                collision["old_path"], collision["new_path"])
            structural_warnings.append(warning)
            warnings.append(warning)

        left_import = import_cast(weapon_path, LEFT_WEAPON_NAMESPACE)
        left_weapon_joint_uuids = _prefix_imported_joints(
            left_import["nodes"], options.left_prefix)
        right_import = import_cast(weapon_path, RIGHT_WEAPON_NAMESPACE)
        right_weapon_joint_uuids = _prefix_imported_joints(
            right_import["nodes"], options.right_prefix)

    left_source_uuid = left_weapon_joint_uuids[options.source_joint]
    right_source_uuid = right_weapon_joint_uuids[options.source_joint]
    left_source = _node_from_uuid(left_source_uuid)
    right_source = _node_from_uuid(right_source_uuid)
    left_target = _node_from_uuid(left_target_uuid)
    right_target = _node_from_uuid(right_target_uuid)

    log("parenting %s under %s" % (left_source, left_target))
    cmds.parent(left_source, left_target, absolute=True)
    left_source = _node_from_uuid(left_source_uuid)
    _zero_translation(left_source, remove_animation=False)
    log("parenting %s under %s" % (right_source, right_target))
    cmds.parent(right_source, right_target, absolute=True)
    right_source = _node_from_uuid(right_source_uuid)
    _zero_translation(right_source, remove_animation=False)

    left_source_range = preflight["left_animation"]["frame_range"]
    right_source_range = preflight["right_animation"]["frame_range"]
    if options.animation_mode == "simultaneous":
        left_offset = 0.0
        right_offset = 0.0
    else:
        left_offset = -float(left_source_range[0])
        left_duration = float(left_source_range[1] - left_source_range[0])
        right_offset = left_duration + 1.0 - float(right_source_range[0])
    left_clip_range = (
        float(left_source_range[0]) + left_offset,
        float(left_source_range[1]) + left_offset,
    )
    right_clip_range = (
        float(right_source_range[0]) + right_offset,
        float(right_source_range[1]) + right_offset,
    )
    playback_range = (
        min(left_clip_range[0], right_clip_range[0]),
        max(left_clip_range[1], right_clip_range[1]),
    )

    state = {
        "schema_version": 1,
        "plugin_version": VERSION,
        "animation_mode": options.animation_mode,
        "shared_hands_source": options.shared_hands_source,
        "source_joint": options.source_joint,
        "left_target_joint": options.left_target_joint,
        "right_target_joint": options.right_target_joint,
        "left_prefix": options.left_prefix,
        "right_prefix": options.right_prefix,
        "hands_joint_uuids": hands_joint_uuids,
        "left_weapon_joint_uuids": left_weapon_joint_uuids,
        "right_weapon_joint_uuids": right_weapon_joint_uuids,
        "left_source_uuid": left_source_uuid,
        "right_source_uuid": right_source_uuid,
        "left_target_uuid": left_target_uuid,
        "right_target_uuid": right_target_uuid,
        "viewhands_path": viewhands_path,
        "weapon_path": weapon_path,
        "left_animation_path": left_animation_path,
        "right_animation_path": right_animation_path,
        "left_clip_range": left_clip_range,
        "right_clip_range": right_clip_range,
        "playback_range": playback_range,
        "framerate": preflight["left_animation"]["framerate"],
        "expected_joint_count": (
            preflight["viewhands"]["bone_count"] +
            (2 * preflight["weapon"]["bone_count"])),
        "expected_mesh_count": (
            preflight["viewhands"]["mesh_count"] +
            (2 * preflight["weapon"]["mesh_count"])),
        "preflight": preflight,
        "structural_warnings": structural_warnings,
        "warnings": warnings,
    }

    left_selected = _dual_selected_hand_names(
        hands_joint_uuids,
        "left",
        options.animation_mode,
        options.shared_hands_source,
    )
    right_selected = _dual_selected_hand_names(
        hands_joint_uuids,
        "right",
        options.animation_mode,
        options.shared_hands_source,
    )
    left_import_report = _import_dual_animation_side(
        state,
        "left",
        left_animation_path,
        left_selected,
        left_offset,
    )
    right_import_report = _import_dual_animation_side(
        state,
        "right",
        right_animation_path,
        right_selected,
        right_offset,
    )
    state["left_import_report"] = left_import_report
    state["right_import_report"] = right_import_report
    cmds.playbackOptions(
        animationStartTime=playback_range[0],
        minTime=playback_range[0],
        animationEndTime=playback_range[1],
        maxTime=playback_range[1],
        loop="once",
    )
    cmds.currentTime(playback_range[0], edit=True)
    left_verification = _validate_dual_side(state, "left")
    right_verification = _validate_dual_side(state, "right")
    result = DualWieldResult(
        plugin_version=VERSION,
        cast_plugin_version=cast_plugin_version(),
        created_at=datetime.datetime.now().astimezone().isoformat(),
        viewhands_path=viewhands_path,
        weapon_path=weapon_path,
        viewhands_size=os.path.getsize(viewhands_path),
        weapon_size=os.path.getsize(weapon_path),
        source_joint_name=options.left_prefix + options.source_joint,
        target_joint_name=options.left_target_joint,
        source_node=left_verification["source_node"],
        target_node=left_verification["target_node"],
        source_uuid=left_verification["source_uuid"],
        target_uuid=left_verification["target_uuid"],
        parent_node=left_verification["parent_node"],
        translation=left_verification["translation"],
        hands_namespace=_namespace_of(left_target),
        weapon_namespace=_namespace_of(left_source),
        hands_roots=hands_import["roots"],
        weapon_roots=left_import["roots"],
        right_source_node=right_verification["source_node"],
        right_target_node=right_verification["target_node"],
        right_source_uuid=right_verification["source_uuid"],
        right_target_uuid=right_verification["target_uuid"],
        right_parent_node=right_verification["parent_node"],
        right_translation=right_verification["translation"],
        right_weapon_namespace=_namespace_of(right_source),
        right_weapon_roots=right_import["roots"],
        left_animation_path=left_animation_path,
        right_animation_path=right_animation_path,
        animation_mode=options.animation_mode,
        shared_hands_source=options.shared_hands_source,
        left_prefix=options.left_prefix,
        right_prefix=options.right_prefix,
        left_clip_range=left_clip_range,
        right_clip_range=right_clip_range,
        dual_state_node="",
        translation_protected=True,
        preflight=preflight,
        left_import_report=left_import_report,
        right_import_report=right_import_report,
        warnings=warnings,
    )
    _allocate_result_output_paths(result, options.output_dir, options)
    state["output_scene"] = result.output_scene
    state["output_cast"] = result.output_cast
    state["output_smd"] = result.output_smd
    state["output_fbx"] = result.output_fbx
    state["output_manifest"] = result.output_manifest
    state["requested_outputs"] = dict(result.requested_outputs)
    state_node = _create_dual_state(state)
    result.dual_state_node = state_node
    result.dual_verification = validate_dual_wield()
    _write_result_outputs(result, options, allocate=False)
    _LAST_RESULT = result
    log("=== attach_dual_wield done ===")
    return result


def _dual_routed_uuids(state, side, selected_hand_names):
    hand_uuids = [
        node_uuid for name, node_uuid in state["hands_joint_uuids"].items()
        if name in selected_hand_names]
    source_uuid = state["%s_source_uuid" % side]
    weapon_uuids = [
        node_uuid
        for node_uuid in state[
            "%s_weapon_joint_uuids" % side].values()
        if node_uuid != source_uuid]
    return hand_uuids + weapon_uuids


def _cut_dual_keys(state, side, selected_hand_names, frame_range):
    nodes = [
        _node_from_uuid(node_uuid)
        for node_uuid in _dual_routed_uuids(
            state, side, selected_hand_names)]
    if nodes:
        cmds.cutKey(
            nodes,
            time=(float(frame_range[0]), float(frame_range[1])),
            clear=True,
        )


def replace_dual_animation(side, animation_path):
    """Replace one side of an existing dual-wield scene in-place."""
    global _LAST_RESULT

    side = str(side).lower().strip()
    if side not in DUAL_SIDES:
        raise RuntimeError("Replacement side must be left or right")
    state_node, state = _read_dual_state()
    validate_dual_wield()
    inventory = _cast_animation_inventory(
        _validate_cast_path(animation_path, "%s animation" % side.title()))
    if abs(float(inventory["framerate"]) -
           float(state["framerate"])) > 1e-6:
        raise RuntimeError(
            "Replacement framerate %s does not match scene framerate %s"
            % (inventory["framerate"], state["framerate"]))

    old_range = tuple(state["%s_clip_range" % side])
    source_range = tuple(inventory["frame_range"])
    if state["animation_mode"] == "sequential":
        old_duration = float(old_range[1] - old_range[0])
        new_duration = float(source_range[1] - source_range[0])
        if abs(old_duration - new_duration) > 1e-6:
            raise RuntimeError(
                "Sequential replacement must keep the existing %s-frame "
                "duration; replacement has %s frames"
                % (old_duration, new_duration))
        frame_offset = float(old_range[0]) - float(source_range[0])
    else:
        frame_offset = 0.0
    new_range = (
        float(source_range[0]) + frame_offset,
        float(source_range[1]) + frame_offset,
    )
    selected_hand_names = _dual_selected_hand_names(
        state["hands_joint_uuids"],
        side,
        state["animation_mode"],
        state["shared_hands_source"],
    )

    undo_enabled = bool(cmds.undoInfo(query=True, state=True))
    chunk_open = False
    try:
        if undo_enabled:
            cmds.undoInfo(
                openChunk=True,
                chunkName="ViewmodelWeaponToolkitReplaceDualAnimation")
            chunk_open = True
        _cut_dual_keys(state, side, selected_hand_names, old_range)
        report = _import_dual_animation_side(
            state,
            side,
            animation_path,
            selected_hand_names,
            frame_offset,
        )
        state["%s_animation_path" % side] = os.path.normpath(
            os.path.abspath(animation_path))
        state["%s_clip_range" % side] = new_range
        other_side = "right" if side == "left" else "left"
        other_range = tuple(state["%s_clip_range" % other_side])
        playback_range = (
            min(new_range[0], float(other_range[0])),
            max(new_range[1], float(other_range[1])),
        )
        state["playback_range"] = playback_range
        state["%s_import_report" % side] = report
        updated_preflight = preflight_dual_inputs(
            state["viewhands_path"],
            state["weapon_path"],
            state["left_animation_path"],
            state["right_animation_path"],
            animation_mode=state["animation_mode"],
            source_joint=state["source_joint"],
            left_target_joint=state["left_target_joint"],
            right_target_joint=state["right_target_joint"],
        )
        state["preflight"] = updated_preflight
        state["warnings"] = (
            list(state.get("structural_warnings", [])) +
            list(updated_preflight["warnings"]))
        _write_dual_state(state_node, state)
        cmds.playbackOptions(
            animationStartTime=playback_range[0],
            minTime=playback_range[0],
            animationEndTime=playback_range[1],
            maxTime=playback_range[1],
            loop="once",
        )
        cmds.currentTime(playback_range[0], edit=True)
        validation = validate_dual_wield()
        if isinstance(_LAST_RESULT, DualWieldResult):
            setattr(_LAST_RESULT, "%s_animation_path" % side,
                    state["%s_animation_path" % side])
            setattr(_LAST_RESULT, "%s_clip_range" % side, new_range)
            setattr(_LAST_RESULT, "%s_import_report" % side, report)
            _LAST_RESULT.preflight = updated_preflight
            _LAST_RESULT.warnings = list(state["warnings"])
            _LAST_RESULT.dual_verification = validation
        report = dict(report)
        report["playback_range"] = playback_range
        report["verification"] = validation
        return report
    except Exception:
        if chunk_open:
            cmds.undoInfo(closeChunk=True)
            chunk_open = False
            cmds.undo()
        raise
    finally:
        if chunk_open:
            cmds.undoInfo(closeChunk=True)


def run(viewhands_path, weapon_path, options=None):
    return attach_gun(viewhands_path, weapon_path, options)


def batch_attach(viewhands_path, weapon_paths, options=None):
    """Process several weapons independently, one result set per weapon."""
    options = options or AttachOptions()
    validate_output_options(options)
    successes = []
    errors = []
    for weapon_path in weapon_paths:
        try:
            successes.append(attach_gun(
                viewhands_path,
                weapon_path,
                replace(options, force_new_scene=True),
            ))
        except Exception as exc:
            errors.append({"weapon_path": weapon_path, "error": str(exc)})
            log("BATCH ERROR %s: %s" % (weapon_path, exc))
            log(traceback.format_exc())
    return successes, errors


# ---------------------------------------------------------------------------
# Current-scene result tools and animation protection.
# ---------------------------------------------------------------------------

def protect_current_attachment_translation(
        source_joint=DEFAULT_SOURCE_JOINT,
        target_joint=DEFAULT_TARGET_JOINT):
    source_node, target_node = _find_current_attachment(
        source_joint, target_joint)
    _zero_translation(source_node, remove_animation=True)
    return validate_attachment(
        source_joint,
        target_joint,
        source_node=source_node,
        target_node=target_node,
    )


def _set_playback_range_from_curves(curves):
    key_times = cmds.keyframe(
        curves, query=True, timeChange=True) or []
    if not key_times:
        raise RuntimeError(
            "Imported animation created no usable keyframes")
    start = float(min(key_times))
    end = float(max(key_times))
    cmds.playbackOptions(
        animationStartTime=start,
        minTime=start,
        animationEndTime=end,
        maxTime=end,
    )
    cmds.currentTime(start, edit=True)
    return (start, end)


def import_animation_file(animation_path,
                          protect_translation=True,
                          source_joint=DEFAULT_SOURCE_JOINT,
                          target_joint=DEFAULT_TARGET_JOINT):
    global _LAST_RESULT

    animation_path = _validate_cast_path(animation_path, "Animation")
    current = validate_attachment(source_joint, target_joint)
    source_uuid = current["source_uuid"]
    target_uuid = current["target_uuid"]
    hand_node = _resolve_viewhands_animation_joint(
        source_joint, source_uuid, target_uuid)
    hand_uuid = _node_uuid(hand_node)
    ensure_cast_plugin()
    framerate = _set_scene_framerate_from_animation(animation_path)
    log("safely importing animation: %s" % animation_path)
    log("routing %s tracks to %s (UUID %s)" % (
        source_joint, hand_node, hand_uuid))
    with _temporary_cast_animation_settings(import_at_time=False):
        with _route_viewhands_animation_name(
                source_uuid, hand_uuid, source_joint):
            new_nodes = cmds.file(
                animation_path,
                i=True,
                type=cast_translator_name(),
                returnNewNodes=True,
                ra=True,
                groupReference=False,
                options=_cast_animation_import_options(False),
            ) or []

    if protect_translation:
        source_node = _node_from_uuid(source_uuid)
        _zero_translation(source_node, remove_animation=True)
        current = validate_attachment(
            source_joint,
            target_joint,
            source_node=source_node,
            target_node=_node_from_uuid(target_uuid),
        )

    anim_curves = []
    for node in _long_names(new_nodes):
        try:
            if cmds.nodeType(node).startswith("animCurve"):
                anim_curves.append(node)
        except Exception:
            pass
    playback_range = _set_playback_range_from_curves(anim_curves)

    if _LAST_RESULT and _LAST_RESULT.source_uuid == source_uuid:
        _LAST_RESULT.animation_path = animation_path
        _LAST_RESULT.translation_protected = bool(protect_translation)
        _LAST_RESULT.source_node = current["source_node"]
        _LAST_RESULT.target_node = current["target_node"]
        _LAST_RESULT.parent_node = current["parent_node"]
        _LAST_RESULT.translation = current["translation"]

    return {
        "animation_path": animation_path,
        "framerate": framerate,
        "new_node_count": len(new_nodes),
        "anim_curve_count": len(anim_curves),
        "playback_range": playback_range,
        "translation_protected": bool(protect_translation),
        "routed_hand_node": _node_from_uuid(hand_uuid),
        "routed_hand_uuid": hand_uuid,
        "verification": current,
    }


def _cast_content_counts(path):
    """Return lightweight top-level model/animation counts for one CAST."""
    module = _castplugin_module()
    cast_file = module.Cast.load(path)
    models = 0
    animations = 0
    for root in cast_file.Roots():
        models += len(root.ChildrenOfType(module.Model))
        animations += len(root.ChildrenOfType(module.Animation))
    return {"models": models, "animations": animations}


def _local_path_from_drop_url(value):
    """Convert one Maya external-drop URL to a normalized local path."""
    raw = str(value).strip()
    parsed = urlparse(raw)
    if parsed.scheme and parsed.scheme.lower() != "file":
        return None
    if parsed.scheme.lower() == "file":
        path = unquote(parsed.path)
        if parsed.netloc and parsed.netloc.lower() != "localhost":
            path = "//%s%s" % (parsed.netloc, path)
        elif re.match(r"^/[A-Za-z]:", path):
            path = path[1:]
    else:
        path = unquote(raw)
    return os.path.normpath(path) if path else None


def _external_drop_paths(data):
    if not data or not data.hasUrls():
        return []
    return [path for path in (
        _local_path_from_drop_url(value) for value in data.urls()) if path]


def _has_attachment_drop_evidence(
        source_joint=DEFAULT_SOURCE_JOINT,
        target_joint=DEFAULT_TARGET_JOINT):
    """Detect a scene that appears to be a toolkit result."""
    hand_name = "viewhands_%s" % source_joint
    if any(_short_name(node) == hand_name
           for node in cmds.ls(type="joint", long=True) or []):
        return True
    for node in cmds.ls(type="joint", long=True) or []:
        if _short_name(node) != source_joint:
            continue
        parent = cmds.listRelatives(node, parent=True, fullPath=True) or []
        if len(parent) == 1 and _short_name(parent[0]) == target_joint:
            return True
    return False


def _animation_drop_attachment_state(
        source_joint=DEFAULT_SOURCE_JOINT,
        target_joint=DEFAULT_TARGET_JOINT):
    """Return valid/absent/invalid without guessing between scene joints."""
    evidence = _has_attachment_drop_evidence(source_joint, target_joint)
    try:
        current = validate_attachment(source_joint, target_joint)
        _resolve_viewhands_animation_joint(
            source_joint, current["source_uuid"], current["target_uuid"])
    except Exception as exc:
        if evidence:
            return "invalid", str(exc)
        return "absent", str(exc)
    return "valid", ""


def _report_drop_error(path, message):
    text = "Safe CAST animation drop rejected for %s: %s" % (
        os.path.basename(path), message)
    log(text)
    try:
        OpenMaya.MGlobal.displayError(text)
    except Exception:
        pass


def _import_dropped_animation(path):
    """Import a dropped animation as one undoable operation."""
    undo_enabled = bool(cmds.undoInfo(query=True, state=True))
    if not undo_enabled:
        raise RuntimeError(
            "Maya Undo is disabled. Enable Undo before dropping an animation "
            "CAST so a failed import can be rolled back safely.")
    chunk_open = False
    try:
        if undo_enabled:
            cmds.undoInfo(
                openChunk=True, chunkName="ViewmodelWeaponToolkitSafeCastDrop")
            chunk_open = True
        return import_animation_file(path, protect_translation=True)
    except Exception:
        if chunk_open:
            cmds.undoInfo(closeChunk=True)
            chunk_open = False
            try:
                cmds.undo()
            except Exception as undo_exc:
                log("unable to undo failed dropped animation: %s" % undo_exc)
        raise
    finally:
        if chunk_open:
            cmds.undoInfo(closeChunk=True)


def handle_external_cast_drop(data, do_drop):
    """Handle one external drop and return an MExternalDropCallback status."""
    default = OpenMayaUI.MExternalDropCallback.kMayaDefault
    if not do_drop or not auto_safe_drop_enabled():
        return default

    paths = _external_drop_paths(data)
    if len(paths) != 1:
        return default
    path = paths[0]
    if os.path.splitext(path)[1].lower() != ".cast" or not os.path.isfile(path):
        return default

    try:
        contents = _cast_content_counts(path)
    except Exception as exc:
        try:
            attachment_evidence = _has_attachment_drop_evidence()
        except Exception as evidence_exc:
            _report_drop_error(
                path,
                "Unable to inspect CAST or validate the current scene (%s; %s)"
                % (exc, evidence_exc),
            )
            return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
        if attachment_evidence:
            _report_drop_error(path, "Unable to inspect CAST contents: %s" % exc)
            return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
        log("unable to inspect dropped CAST; using Maya default: %s" % exc)
        return default
    if contents["animations"] < 1 or contents["models"]:
        return default

    dual_state_nodes = cmds.ls(DUAL_STATE_NODE, type="network") or []
    dual_scene = bool(dual_state_nodes)
    if dual_scene:
        try:
            _read_dual_state()
        except Exception as exc:
            _report_drop_error(
                path, "Current dual-wield metadata is invalid: %s" % exc)
            return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
    if dual_scene:
        lowered = os.path.basename(path).lower()
        if "_akimbo_l_" in lowered:
            filename_side = "left"
        elif "_akimbo_r_" in lowered:
            filename_side = "right"
        else:
            filename_side = None
        try:
            signature_side, signature_scores = \
                _dual_animation_side_signature(path)
        except Exception as exc:
            _report_drop_error(
                path, "Unable to identify the Akimbo track side: %s" % exc)
            return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
        if (filename_side and signature_side
                and filename_side != signature_side):
            log(
                "WARNING dropped animation filename indicates %s while "
                "track signature suggests %s (left score %d, right score %d); "
                "using the explicit filename"
                % (filename_side, signature_side,
                   signature_scores["left"], signature_scores["right"]))
        side = filename_side or signature_side
        if side is None:
            _report_drop_error(
                path,
                "Unable to infer left/right from either the filename or "
                "the animation track signature",
            )
            return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
        try:
            report = replace_dual_animation(side, path)
        except Exception as exc:
            _report_drop_error(path, str(exc))
            log(traceback.format_exc())
            return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept
        log("safe dual CAST drop replaced %s animation (%d curves)" % (
            side, report["anim_curve_count"]))
        return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndAccept

    state, reason = _animation_drop_attachment_state()
    if state == "absent":
        return default
    if state == "invalid":
        _report_drop_error(path, reason)
        return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept

    try:
        report = _import_dropped_animation(path)
    except Exception as exc:
        _report_drop_error(path, str(exc))
        log(traceback.format_exc())
        return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndNoAccept

    log("safe CAST drop imported %s (%d curves, frames %s-%s)" % (
        path,
        report["anim_curve_count"],
        report["playback_range"][0],
        report["playback_range"][1],
    ))
    return OpenMayaUI.MExternalDropCallback.kNoMayaDefaultAndAccept


def _refresh_persisted_dual_manifest(state, validation):
    """Refresh animation metadata after a reopened dual scene is edited."""
    manifest_path = state.get("output_manifest", "")
    if not manifest_path or not os.path.isfile(manifest_path):
        return
    try:
        with open(manifest_path, "r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except Exception as exc:
        raise RuntimeError(
            "Unable to read the persisted dual manifest: %s" % exc)
    payload.update({
        "plugin_version": VERSION,
        "left_animation_path": state["left_animation_path"],
        "right_animation_path": state["right_animation_path"],
        "left_clip_range": list(state["left_clip_range"]),
        "right_clip_range": list(state["right_clip_range"]),
        "animation_mode": state["animation_mode"],
        "shared_hands_source": state["shared_hands_source"],
        "dual_verification": validation,
        "preflight": state.get("preflight", payload.get("preflight", {})),
        "left_import_report": state.get("left_import_report", {}),
        "right_import_report": state.get("right_import_report", {}),
        "warnings": list(state.get("warnings", [])),
    })
    for key, state_key in (
            ("scene", "output_scene"),
            ("cast", "output_cast"),
            ("smd", "output_smd"),
            ("fbx", "output_fbx")):
        path = state.get(state_key, "")
        payload["output_%s" % key] = path
        payload["output_%s_exists" % key] = os.path.isfile(path)
        payload["output_%s_size" % key] = (
            os.path.getsize(path) if os.path.isfile(path) else 0)
    payload["output_manifest"] = manifest_path
    with open(manifest_path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)


def save_current_result():
    global _LAST_RESULT

    if not _LAST_RESULT:
        if not (cmds.ls(DUAL_STATE_NODE, type="network") or []):
            raise RuntimeError(
                "No %s result is active. Build a weapon scene first."
                % PRODUCT_NAME)
        state_node, state = _read_dual_state()
        validation = validate_dual_wield()
        scene_path = cmds.file(query=True, sceneName=True)
        if not scene_path:
            raise RuntimeError(
                "The reopened dual-wield scene has no Maya file path")
        state["output_scene"] = scene_path
        _write_dual_state(state_node, state)
        cmds.file(save=True, type="mayaAscii", force=True)
        _refresh_persisted_dual_manifest(state, validation)
        return scene_path

    if isinstance(_LAST_RESULT, DualWieldResult):
        dual = validate_dual_wield()
        left = dual["left"]
        right = dual["right"]
        _LAST_RESULT.source_node = left["source_node"]
        _LAST_RESULT.target_node = left["target_node"]
        _LAST_RESULT.source_uuid = left["source_uuid"]
        _LAST_RESULT.target_uuid = left["target_uuid"]
        _LAST_RESULT.parent_node = left["parent_node"]
        _LAST_RESULT.translation = left["translation"]
        _LAST_RESULT.right_source_node = right["source_node"]
        _LAST_RESULT.right_target_node = right["target_node"]
        _LAST_RESULT.right_source_uuid = right["source_uuid"]
        _LAST_RESULT.right_target_uuid = right["target_uuid"]
        _LAST_RESULT.right_parent_node = right["parent_node"]
        _LAST_RESULT.right_translation = right["translation"]
        _LAST_RESULT.dual_verification = dual
    else:
        verification = validate_attachment(
            _LAST_RESULT.source_joint_name,
            _LAST_RESULT.target_joint_name,
        )
        _LAST_RESULT.source_node = verification["source_node"]
        _LAST_RESULT.target_node = verification["target_node"]
        _LAST_RESULT.source_uuid = verification["source_uuid"]
        _LAST_RESULT.target_uuid = verification["target_uuid"]
        _LAST_RESULT.parent_node = verification["parent_node"]
        _LAST_RESULT.translation = verification["translation"]

    requested = _LAST_RESULT.requested_outputs or {
        "ma": bool(_LAST_RESULT.output_scene),
        "cast": bool(_LAST_RESULT.output_cast),
        "smd": bool(_LAST_RESULT.output_smd),
        "fbx": bool(_LAST_RESULT.output_fbx),
    }
    options = AttachOptions(
        output_dir=os.path.dirname(_LAST_RESULT.output_manifest),
        source_joint=_LAST_RESULT.source_joint_name,
        target_joint=_LAST_RESULT.target_joint_name,
        save_scene=bool(requested.get("ma")),
        export_cast=bool(requested.get("cast")),
        export_smd=bool(requested.get("smd")),
        export_fbx=bool(requested.get("fbx")),
    )
    _write_result_outputs(_LAST_RESULT, options, allocate=False)
    return _LAST_RESULT.output_scene or _LAST_RESULT.output_manifest


# ---------------------------------------------------------------------------
# UI helpers.
# ---------------------------------------------------------------------------

def _show_error(title, exc):
    log("ERROR: %s" % exc)
    log(traceback.format_exc())
    cmds.confirmDialog(
        title=title,
        message="Failed:\n%s" % exc,
        button=["OK"],
        defaultButton="OK",
    )


def _field_text(name, default=""):
    try:
        if cmds.textField(name, exists=True):
            return cmds.textField(name, query=True, text=True).strip()
    except Exception:
        pass
    return default


def _protect_translation_ui_value(default=True):
    try:
        if cmds.checkBox(PROTECT_TRANSLATION_CHECK, exists=True):
            return bool(cmds.checkBox(
                PROTECT_TRANSLATION_CHECK, query=True, value=True))
    except Exception:
        pass
    return bool(default)


def _check_box_value(name, default=False):
    try:
        if cmds.checkBox(name, exists=True):
            return bool(cmds.checkBox(name, query=True, value=True))
    except Exception:
        pass
    return bool(default)


def _dialog_options(force_new_scene=False):
    saved = load_saved_options(force_new_scene=force_new_scene)
    return AttachOptions(
        output_dir=_field_text(OUTPUT_DIR_FIELD, saved.output_dir),
        ma_output_dir=_field_text(
            MA_OUTPUT_DIR_FIELD, saved.ma_output_dir),
        cast_output_dir=_field_text(
            CAST_OUTPUT_DIR_FIELD, saved.cast_output_dir),
        smd_output_dir=_field_text(
            SMD_OUTPUT_DIR_FIELD, saved.smd_output_dir),
        fbx_output_dir=_field_text(
            FBX_OUTPUT_DIR_FIELD, saved.fbx_output_dir),
        source_joint=_field_text(SOURCE_JOINT_FIELD, saved.source_joint),
        target_joint=_field_text(TARGET_JOINT_FIELD, saved.target_joint),
        protect_translation=_protect_translation_ui_value(
            saved.protect_translation),
        save_scene=_check_box_value(EXPORT_MA_CHECK, saved.save_scene),
        export_cast=_check_box_value(EXPORT_CAST_CHECK, saved.export_cast),
        export_smd=_check_box_value(EXPORT_SMD_CHECK, saved.export_smd),
        export_fbx=_check_box_value(EXPORT_FBX_CHECK, saved.export_fbx),
        force_new_scene=force_new_scene,
    )


def _browse_cast(target_field):
    current = _field_text(target_field)
    start_dir = os.path.dirname(current) if current else ""
    if not os.path.isdir(start_dir):
        start_dir = ""
    kwargs = dict(
        fileMode=1,
        fileFilter="Cast (*.cast)",
        dialogStyle=2,
        okCaption="Select",
        caption="Select .cast file",
    )
    if start_dir:
        kwargs["startingDirectory"] = start_dir
    try:
        result = cmds.fileDialog2(**kwargs) or []
    except Exception as exc:
        _show_error("%s - File Browser" % PRODUCT_SHORT_NAME, exc)
        return
    if result:
        chosen = result[0]
        cmds.textField(target_field, edit=True, text=chosen)
        if target_field == VIEWHANDS_FIELD:
            save_viewhands_path(chosen)


def _browse_output_dir(target_field=OUTPUT_DIR_FIELD, label="output"):
    fallback = _field_text(OUTPUT_DIR_FIELD, DEFAULT_OUTPUT_DIR)
    current = _field_text(target_field, fallback)
    kwargs = dict(
        fileMode=3,
        dialogStyle=2,
        okCaption="Select",
        caption="Select %s folder" % label,
    )
    if os.path.isdir(current):
        kwargs["startingDirectory"] = current
    result = cmds.fileDialog2(**kwargs) or []
    if result:
        cmds.textField(target_field, edit=True, text=result[0])


def _confirm_scene_reset():
    if not cmds.file(query=True, modified=True):
        return True

    choice = cmds.confirmDialog(
        title="%s - Unsaved Scene" % PRODUCT_SHORT_NAME,
        message=("The current scene has unsaved changes. The toolkit needs a "
                 "new scene. Save, discard, or cancel?"),
        button=["Save", "Discard", "Cancel"],
        defaultButton="Save",
        cancelButton="Cancel",
        dismissString="Cancel",
    )
    if choice == "Cancel":
        return False
    if choice == "Discard":
        return True

    try:
        if cmds.file(query=True, sceneName=True):
            cmds.file(save=True)
        else:
            mel.eval("SaveScene")
    except Exception as exc:
        _show_error("%s - Save Scene" % PRODUCT_SHORT_NAME, exc)
        return False
    return not cmds.file(query=True, modified=True)


def _require_dialog_paths(require_weapon=True):
    viewhands = _field_text(VIEWHANDS_FIELD)
    weapon = _field_text(WEAPON_FIELD)
    if not viewhands:
        raise RuntimeError("Please pick a viewhands (.cast) file")
    if require_weapon and not weapon:
        raise RuntimeError("Please pick one weapon (.cast) file")
    return viewhands, weapon


def _preflight_from_dialog():
    try:
        viewhands, weapon = _require_dialog_paths(require_weapon=True)
        options = _dialog_options()
        formats = validate_output_options(options)
        output_dirs = resolved_output_directories(options)
        output_lines = [
            "  JSON: %s" % output_dirs["manifest"],
        ]
        for key, label in (
                ("scene", "MA"),
                ("cast", "Cast"),
                ("smd", "SMD"),
                ("fbx", "FBX")):
            if key == "scene":
                enabled = options.save_scene
            else:
                enabled = getattr(options, "export_" + key)
            if enabled:
                output_lines.append("  %s: %s" % (label, output_dirs[key]))
        report = preflight_inputs(
            viewhands,
            weapon,
            options.source_joint,
            options.target_joint,
        )
        save_options(viewhands, options)
        cmds.confirmDialog(
            title="%s - Preflight Passed" % PRODUCT_SHORT_NAME,
            message=("Preflight passed without changing the scene.\n\n"
                     "%s\n"
                     "Viewhands: %d bones, %d meshes, match %s\n"
                     "  Unused source vertices: %d\n"
                     "Weapon: %d bones, %d meshes, match %s\n"
                     "  Unused source vertices: %d\n\n"
                     "Outputs: %s + JSON manifest\n%s\n"
                     "This dialog builds the single-weapon workflow."
                     % (
                         report["mapping"],
                         report["viewhands"]["bone_count"],
                         report["viewhands"]["mesh_count"],
                         report["viewhands"]["match"],
                         report["viewhands"]["unused_vertex_count"],
                         report["weapon"]["bone_count"],
                         report["weapon"]["mesh_count"],
                         report["weapon"]["match"],
                         report["weapon"]["unused_vertex_count"],
                         ", ".join("." + value for value in formats),
                         "\n".join(output_lines),
                     )),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Preflight" % PRODUCT_SHORT_NAME, exc)


def _run_from_dialog():
    try:
        viewhands, weapon = _require_dialog_paths(require_weapon=True)
        options = _dialog_options(force_new_scene=True)
        validate_output_options(options)
        save_options(viewhands, options)
        if not _confirm_scene_reset():
            return
        result = attach_gun(viewhands, weapon, options)
        cmds.confirmDialog(
            title="%s - Done" % PRODUCT_SHORT_NAME,
            message=("Done. weapon:%s -> viewhands:%s\n"
                     "Translation: %s\n\n"
                     "MA: %s\nCast: %s\nSMD: %s\nFBX: %s\n"
                     "Manifest: %s\n\n"
                     "Use Dual-Wield Builder for an Akimbo result."
                     % (
                         options.source_joint,
                         options.target_joint,
                         result.translation,
                         result.output_scene or "disabled",
                         result.output_cast or "disabled",
                         result.output_smd or "disabled",
                         result.output_fbx or "disabled",
                         result.output_manifest,
                     )),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Error" % PRODUCT_SHORT_NAME, exc)


def _batch_from_dialog():
    try:
        viewhands, _ = _require_dialog_paths(require_weapon=False)
        options = _dialog_options(force_new_scene=True)
        validate_output_options(options)
        start_dir = os.path.dirname(_field_text(WEAPON_FIELD))
        kwargs = dict(
            fileMode=4,
            fileFilter="Cast (*.cast)",
            dialogStyle=2,
            okCaption="Select",
            caption="Select weapon .cast files (one output set per weapon)",
        )
        if os.path.isdir(start_dir):
            kwargs["startingDirectory"] = start_dir
        weapon_paths = cmds.fileDialog2(**kwargs) or []
        if not weapon_paths:
            return
        save_options(viewhands, options)
        if not _confirm_scene_reset():
            return

        successes = []
        errors = []
        cancelled = False
        cmds.progressWindow(
            title="%s Batch" % PRODUCT_SHORT_NAME,
            progress=0,
            maxValue=len(weapon_paths),
            status="Starting...",
            isInterruptable=True,
        )
        try:
            for index, weapon_path in enumerate(weapon_paths, 1):
                if cmds.progressWindow(query=True, isCancelled=True):
                    cancelled = True
                    break
                cmds.progressWindow(
                    edit=True,
                    progress=index - 1,
                    status="%d/%d  %s" % (
                        index, len(weapon_paths), os.path.basename(weapon_path)),
                )
                try:
                    successes.append(attach_gun(
                        viewhands,
                        weapon_path,
                        replace(options, force_new_scene=True),
                    ))
                except Exception as exc:
                    errors.append((weapon_path, str(exc)))
                    log("BATCH ERROR %s: %s" % (weapon_path, exc))
                    log(traceback.format_exc())
                cmds.progressWindow(edit=True, progress=index)
        finally:
            cmds.progressWindow(endProgress=True)

        error_text = "\n".join(
            "%s: %s" % (os.path.basename(path), error)
            for path, error in errors[:5])
        message = (
            "Batch complete. One output set was produced per weapon.\n"
            "Succeeded: %d\nFailed: %d\nCancelled: %s\n\n%s"
            % (len(successes), len(errors), cancelled, error_text))
        cmds.confirmDialog(
            title="%s - Batch Result" % PRODUCT_SHORT_NAME,
            message=message,
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Batch Error" % PRODUCT_SHORT_NAME, exc)


def quick_attach():
    viewhands = load_viewhands_path()
    if not viewhands or not os.path.isfile(viewhands):
        cmds.confirmDialog(
            title=PRODUCT_SHORT_NAME,
            message=("No valid saved viewhands path. Use Single-Weapon Builder "
                     "to pick one first."),
            button=["OK"],
            defaultButton="OK",
        )
        return

    kwargs = dict(
        fileMode=1,
        fileFilter="Cast (*.cast)",
        dialogStyle=2,
        okCaption="Select",
        caption="Select one weapon .cast for the single-weapon workflow",
    )
    result = cmds.fileDialog2(**kwargs) or []
    if not result:
        return
    try:
        options = load_saved_options(force_new_scene=True)
        validate_output_options(options)
        if not _confirm_scene_reset():
            return
        attached = attach_gun(viewhands, result[0], options)
        formats = [key for key, enabled in attached.requested_outputs.items()
                   if enabled]
        cmds.confirmDialog(
            title="%s - Done" % PRODUCT_SHORT_NAME,
            message=("Saved formats: %s\nManifest:\n%s"
                     % (", ".join("." + value for value in formats),
                        attached.output_manifest)),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Quick Attach" % PRODUCT_SHORT_NAME, exc)


def import_animation():
    kwargs = dict(
        fileMode=1,
        fileFilter="Cast (*.cast)",
        dialogStyle=2,
        okCaption="Select",
        caption="Select .cast animation",
    )
    result = cmds.fileDialog2(**kwargs) or []
    if not result:
        return
    options = _dialog_options() if cmds.window(WINDOW_NAME, exists=True) \
        else load_saved_options()
    try:
        report = import_animation_file(
            result[0],
            protect_translation=options.protect_translation,
            source_joint=options.source_joint,
            target_joint=options.target_joint,
        )
        cmds.confirmDialog(
            title="%s - Animation Imported" % PRODUCT_SHORT_NAME,
            message=("Animation imported.\nNew animation curves: %d\n"
                     "Attachment translation protected: %s\n\n"
                     "Use Save Current Result to persist the animation."
                     % (report["anim_curve_count"],
                        report["translation_protected"])),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Animation Error" % PRODUCT_SHORT_NAME, exc)


def _validate_current_ui():
    options = _dialog_options() if cmds.window(WINDOW_NAME, exists=True) \
        else load_saved_options()
    try:
        result = validate_attachment(
            options.source_joint, options.target_joint)
        cmds.confirmDialog(
            title="%s - Validation Passed" % PRODUCT_SHORT_NAME,
            message="Parent: %s\nTranslation: %s" % (
                result["parent_node"], result["translation"]),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Validation Failed" % PRODUCT_SHORT_NAME, exc)


def _select_attachment_ui():
    options = _dialog_options() if cmds.window(WINDOW_NAME, exists=True) \
        else load_saved_options()
    try:
        source_node, target_node = _find_current_attachment(
            options.source_joint, options.target_joint)
        cmds.select([target_node, source_node], replace=True)
    except Exception as exc:
        _show_error("%s - Select Attachment" % PRODUCT_SHORT_NAME, exc)


def _save_current_ui():
    try:
        path = save_current_result()
        cmds.confirmDialog(
            title="%s - Saved" % PRODUCT_SHORT_NAME,
            message="Saved current result:\n%s" % path,
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Save Result" % PRODUCT_SHORT_NAME, exc)


def _open_output_dir_ui():
    options = _dialog_options() if cmds.window(WINDOW_NAME, exists=True) \
        else load_saved_options()
    directories = resolved_output_directories(options)
    selected = [directories["manifest"]]
    for key, enabled in (
            ("scene", options.save_scene),
            ("cast", options.export_cast),
            ("smd", options.export_smd),
            ("fbx", options.export_fbx)):
        if enabled:
            selected.append(directories[key])
    try:
        opened = set()
        for directory in selected:
            identity = os.path.normcase(directory)
            if identity in opened:
                continue
            opened.add(identity)
            os.makedirs(directory, exist_ok=True)
            os.startfile(directory)
    except Exception as exc:
        _show_error("%s - Open Output Folders" % PRODUCT_SHORT_NAME, exc)


def _dual_mode_ui_value():
    try:
        if cmds.optionMenu(DUAL_MODE_MENU, exists=True):
            return cmds.optionMenu(
                DUAL_MODE_MENU, query=True, value=True)
    except Exception:
        pass
    return _load_string_option(DUAL_MODE_OPTVAR, "simultaneous")


def _dual_dialog_options(force_new_scene=False):
    saved = load_saved_options(force_new_scene=force_new_scene)
    return DualWieldOptions(
        output_dir=_field_text(OUTPUT_DIR_FIELD, saved.output_dir),
        ma_output_dir=_field_text(MA_OUTPUT_DIR_FIELD, saved.ma_output_dir),
        cast_output_dir=_field_text(
            CAST_OUTPUT_DIR_FIELD, saved.cast_output_dir),
        smd_output_dir=_field_text(SMD_OUTPUT_DIR_FIELD, saved.smd_output_dir),
        fbx_output_dir=_field_text(FBX_OUTPUT_DIR_FIELD, saved.fbx_output_dir),
        source_joint=_field_text(SOURCE_JOINT_FIELD, DEFAULT_SOURCE_JOINT),
        left_target_joint=_field_text(
            DUAL_LEFT_TARGET_FIELD, DEFAULT_LEFT_TARGET_JOINT),
        right_target_joint=_field_text(
            DUAL_RIGHT_TARGET_FIELD, DEFAULT_RIGHT_TARGET_JOINT),
        protect_translation=True,
        save_scene=_check_box_value(EXPORT_MA_CHECK, saved.save_scene),
        export_cast=_check_box_value(EXPORT_CAST_CHECK, saved.export_cast),
        export_smd=_check_box_value(EXPORT_SMD_CHECK, saved.export_smd),
        export_fbx=_check_box_value(EXPORT_FBX_CHECK, saved.export_fbx),
        animation_mode=_dual_mode_ui_value(),
        shared_hands_source="right",
        force_new_scene=force_new_scene,
    )


def _dual_dialog_paths():
    paths = (
        _field_text(DUAL_VIEWHANDS_FIELD),
        _field_text(DUAL_WEAPON_FIELD),
        _field_text(DUAL_LEFT_ANIMATION_FIELD),
        _field_text(DUAL_RIGHT_ANIMATION_FIELD),
    )
    labels = ("Viewhands", "Weapon", "Left animation", "Right animation")
    for label, path in zip(labels, paths):
        _validate_cast_path(path, label)
    return paths


def _save_dual_dialog_settings(paths, options):
    viewhands, weapon, left_animation, right_animation = paths
    _save_string_option(DUAL_VIEWHANDS_OPTVAR, viewhands)
    _save_string_option(DUAL_WEAPON_OPTVAR, weapon)
    _save_string_option(DUAL_LEFT_ANIMATION_OPTVAR, left_animation)
    _save_string_option(DUAL_RIGHT_ANIMATION_OPTVAR, right_animation)
    _save_string_option(DUAL_MODE_OPTVAR, options.animation_mode)
    save_options(viewhands, options)


def _preflight_dual_from_dialog():
    try:
        paths = _dual_dialog_paths()
        options = _dual_dialog_options()
        report = preflight_dual_inputs(
            *paths,
            animation_mode=options.animation_mode,
            source_joint=options.source_joint,
            left_target_joint=options.left_target_joint,
            right_target_joint=options.right_target_joint,
        )
        _save_dual_dialog_settings(paths, options)
        cmds.confirmDialog(
            title="%s - Dual Preflight Passed" % PRODUCT_SHORT_NAME,
            message=(
                "Preflight passed without changing the scene.\n\n"
                "Mode: %s\nFramerate: %s fps\n"
                "Left frames: %s\nRight frames: %s\n"
                "Differing shared tracks: %d\nOrphan nodes: %s"
                % (
                    report["animation_mode"],
                    report["left_animation"]["framerate"],
                    report["left_animation"]["frame_range"],
                    report["right_animation"]["frame_range"],
                    report["conflicting_shared_curve_count"],
                    ", ".join(report["orphan_curve_nodes"]) or "none",
                )),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Dual Preflight" % PRODUCT_SHORT_NAME, exc)


def _run_dual_from_dialog():
    try:
        paths = _dual_dialog_paths()
        options = _dual_dialog_options(force_new_scene=True)
        validate_output_options(options)
        _save_dual_dialog_settings(paths, options)
        if not _confirm_scene_reset():
            return
        result = attach_dual_wield(*paths, options=options)
        cmds.confirmDialog(
            title="%s - Dual-Wield Done" % PRODUCT_SHORT_NAME,
            message=(
                "Dual-wield scene built.\n"
                "Left: %s -> %s\nRight: %s -> %s\n"
                "Mode: %s\nLeft frames: %s\nRight frames: %s\n\n"
                "MA: %s\nCast: %s\nSMD: %s\nFBX: %s\nManifest: %s"
                % (
                    _short_name(result.source_node),
                    _short_name(result.target_node),
                    _short_name(result.right_source_node),
                    _short_name(result.right_target_node),
                    result.animation_mode,
                    result.left_clip_range,
                    result.right_clip_range,
                    result.output_scene or "disabled",
                    result.output_cast or "disabled",
                    result.output_smd or "disabled",
                    result.output_fbx or "disabled",
                    result.output_manifest,
                )),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Dual-Wield Error" % PRODUCT_SHORT_NAME, exc)


def _replace_dual_animation_ui(side):
    result = cmds.fileDialog2(
        fileMode=1,
        fileFilter="Cast (*.cast)",
        dialogStyle=2,
        okCaption="Select",
        caption="Select replacement %s animation" % side,
    ) or []
    if not result:
        return
    try:
        report = replace_dual_animation(side, result[0])
        cmds.confirmDialog(
            title="%s - Dual Animation Replaced" % PRODUCT_SHORT_NAME,
            message=(
                "%s animation replaced.\nCurves: %d\nFrames: %s"
                % (side.title(), report["anim_curve_count"],
                   report["playback_range"])),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Replace Dual Animation" % PRODUCT_SHORT_NAME, exc)


def _validate_dual_ui():
    try:
        report = validate_dual_wield()
        cmds.confirmDialog(
            title="%s - Dual Validation Passed" % PRODUCT_SHORT_NAME,
            message=(
                "Mode: %s\nPlayback: %s\nJoints: %d\nMeshes: %d\n"
                "Left parent: %s\nRight parent: %s"
                % (
                    report["animation_mode"],
                    report["playback_range"],
                    report["joint_count"],
                    report["mesh_count"],
                    report["left"]["parent_node"],
                    report["right"]["parent_node"],
                )),
            button=["OK"],
            defaultButton="OK",
        )
    except Exception as exc:
        _show_error("%s - Dual Validation Failed" % PRODUCT_SHORT_NAME, exc)


def show_dual_dialog():
    """Build and show the duplicated-weapon Dual-Wield Builder."""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    if cmds.window(DUAL_WINDOW_NAME, exists=True):
        cmds.deleteUI(DUAL_WINDOW_NAME)
    saved = load_saved_options()
    win = cmds.window(
        DUAL_WINDOW_NAME,
        title="%s v%s - Dual-Wield Builder" % (PRODUCT_SHORT_NAME, VERSION),
        widthHeight=(880, 650),
        resizeToFitChildren=True,
    )
    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=7, columnOffset=("both", 10))
    cmds.text(
        label=(
            "Duplicates one weapon: left j_gun -> tag_weapon_left; "
            "right j_gun -> tag_weapon_right."),
        align="left",
    )
    cmds.text(
        label=(
            "Simultaneous mode splits hand branches and uses the right "
            "animation for shared torso/root tracks."),
        align="left",
    )
    cmds.separator(height=5, style="in")

    def add_path_row(label, field_name, value, browse_callback=None):
        cmds.rowLayout(
            numberOfColumns=3,
            columnWidth3=(125, 665, 75),
            adjustableColumn=2,
        )
        cmds.text(label=label, align="left")
        cmds.textField(field_name, text=value)
        cmds.button(
            label="Browse...",
            command=(browse_callback or
                     (lambda *_: _browse_cast(field_name))))
        cmds.setParent("..")

    add_path_row(
        "Viewhands:",
        DUAL_VIEWHANDS_FIELD,
        _load_string_option(DUAL_VIEWHANDS_OPTVAR, load_viewhands_path()),
    )
    add_path_row(
        "Weapon:",
        DUAL_WEAPON_FIELD,
        _load_string_option(DUAL_WEAPON_OPTVAR, ""),
    )
    add_path_row(
        "Left animation:",
        DUAL_LEFT_ANIMATION_FIELD,
        _load_string_option(DUAL_LEFT_ANIMATION_OPTVAR, ""),
    )
    add_path_row(
        "Right animation:",
        DUAL_RIGHT_ANIMATION_FIELD,
        _load_string_option(DUAL_RIGHT_ANIMATION_OPTVAR, ""),
    )
    add_path_row(
        "Manifest/default:",
        OUTPUT_DIR_FIELD,
        saved.output_dir,
        lambda *_: _browse_output_dir(
            OUTPUT_DIR_FIELD, "manifest/default output"),
    )

    cmds.rowLayout(
        numberOfColumns=6,
        columnWidth6=(85, 130, 85, 150, 90, 170),
    )
    cmds.text(label="Weapon root:", align="left")
    cmds.textField(SOURCE_JOINT_FIELD, text=DEFAULT_SOURCE_JOINT)
    cmds.text(label="Left target:", align="left")
    cmds.textField(
        DUAL_LEFT_TARGET_FIELD, text=DEFAULT_LEFT_TARGET_JOINT)
    cmds.text(label="Right target:", align="left")
    cmds.textField(
        DUAL_RIGHT_TARGET_FIELD, text=DEFAULT_RIGHT_TARGET_JOINT)
    cmds.setParent("..")

    cmds.rowLayout(numberOfColumns=2, columnWidth2=(125, 280))
    cmds.text(label="Animation mode:", align="left")
    cmds.optionMenu(DUAL_MODE_MENU)
    cmds.menuItem(label="simultaneous")
    cmds.menuItem(label="sequential")
    saved_mode = _load_string_option(DUAL_MODE_OPTVAR, "simultaneous")
    if saved_mode in ("simultaneous", "sequential"):
        cmds.optionMenu(DUAL_MODE_MENU, edit=True, value=saved_mode)
    cmds.setParent("..")

    cmds.text(
        label=(
            "Output formats and folders (blank folder uses "
            "Manifest/default; Cast/SMD/FBX are static model outputs):"),
        align="left",
    )

    def add_output_row(check_name, label, enabled, field_name, value):
        cmds.rowLayout(
            numberOfColumns=3,
            columnWidth3=(220, 570, 75),
            adjustableColumn=2,
        )
        cmds.checkBox(check_name, label=label, value=enabled)
        cmds.textField(field_name, text=value)
        cmds.button(
            label="Browse...",
            command=lambda *_: _browse_output_dir(field_name, label),
        )
        cmds.setParent("..")

    add_output_row(
        EXPORT_MA_CHECK, "Maya ASCII scene + animation (.ma)",
        saved.save_scene, MA_OUTPUT_DIR_FIELD, saved.ma_output_dir)
    add_output_row(
        EXPORT_CAST_CHECK, "Static combined model Cast (.cast)",
        saved.export_cast, CAST_OUTPUT_DIR_FIELD, saved.cast_output_dir)
    add_output_row(
        EXPORT_SMD_CHECK, "Static Source model (.smd)",
        saved.export_smd, SMD_OUTPUT_DIR_FIELD, saved.smd_output_dir)
    add_output_row(
        EXPORT_FBX_CHECK, "Static model with skinning (.fbx)",
        saved.export_fbx, FBX_OUTPUT_DIR_FIELD, saved.fbx_output_dir)

    cmds.separator(height=5, style="in")
    cmds.rowLayout(numberOfColumns=3, columnWidth3=(220, 220, 220))
    cmds.button(
        label="Preflight Dual", height=30,
        command=lambda *_: _preflight_dual_from_dialog())
    cmds.button(
        label="Build + Import Both", height=30,
        command=lambda *_: _run_dual_from_dialog())
    cmds.button(
        label="Validate Dual", height=30,
        command=lambda *_: _validate_dual_ui())
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=4, columnWidth4=(165, 165, 165, 165))
    cmds.button(
        label="Replace Left Clip...",
        command=lambda *_: _replace_dual_animation_ui("left"))
    cmds.button(
        label="Replace Right Clip...",
        command=lambda *_: _replace_dual_animation_ui("right"))
    cmds.button(
        label="Save Current Result",
        command=lambda *_: _save_current_ui())
    cmds.button(
        label="Close",
        command=lambda *_: cmds.deleteUI(DUAL_WINDOW_NAME))
    cmds.setParent("..")
    cmds.showWindow(win)


def show_dialog():
    """Build and show the single-weapon dialog."""
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    if cmds.window(DUAL_WINDOW_NAME, exists=True):
        cmds.deleteUI(DUAL_WINDOW_NAME)

    saved = load_saved_options()
    win = cmds.window(
        WINDOW_NAME,
        title="%s v%s - Single Weapon" % (PRODUCT_SHORT_NAME, VERSION),
        widthHeight=(820, 540),
        resizeToFitChildren=True,
    )
    cmds.columnLayout(
        adjustableColumn=True,
        rowSpacing=7,
        columnOffset=("both", 10),
    )
    cmds.text(
        label=("Single mode - weapon:j_gun -> viewhands:tag_weapon. "
               "Use Dual-Wield Builder for Akimbo scenes."),
        align="left",
    )
    cmds.separator(height=5, style="in")

    def add_path_row(label, field_name, value, callback):
        cmds.rowLayout(
            numberOfColumns=3,
            columnWidth3=(120, 600, 75),
            adjustableColumn=2,
        )
        cmds.text(label=label, align="left")
        cmds.textField(field_name, text=value)
        cmds.button(label="Browse...", command=callback)
        cmds.setParent("..")

    add_path_row(
        "Viewhands:", VIEWHANDS_FIELD, load_viewhands_path(),
        lambda *_: _browse_cast(VIEWHANDS_FIELD))
    add_path_row(
        "Weapon:", WEAPON_FIELD, "",
        lambda *_: _browse_cast(WEAPON_FIELD))
    add_path_row(
        "Manifest/default:", OUTPUT_DIR_FIELD, saved.output_dir,
        lambda *_: _browse_output_dir(
            OUTPUT_DIR_FIELD, "manifest/default output"))

    cmds.rowLayout(
        numberOfColumns=4,
        columnWidth4=(105, 215, 105, 215),
        adjustableColumn=4,
    )
    cmds.text(label="Weapon joint:", align="left")
    cmds.textField(SOURCE_JOINT_FIELD, text=saved.source_joint)
    cmds.text(label="Viewhands tag:", align="left")
    cmds.textField(TARGET_JOINT_FIELD, text=saved.target_joint)
    cmds.setParent("..")

    cmds.checkBox(
        PROTECT_TRANSLATION_CHECK,
        label="Protect weapon joint translation when importing animation",
        value=saved.protect_translation,
    )
    cmds.text(
        label=("Output formats and folders (select at least one; blank folder "
               "uses Manifest/default):"),
        align="left",
    )

    def add_output_row(check_name, label, enabled, field_name, value):
        cmds.rowLayout(
            numberOfColumns=3,
            columnWidth3=(215, 505, 75),
            adjustableColumn=2,
        )
        cmds.checkBox(check_name, label=label, value=enabled)
        cmds.textField(field_name, text=value)
        cmds.button(
            label="Browse...",
            command=lambda *_: _browse_output_dir(field_name, label),
        )
        cmds.setParent("..")

    add_output_row(
        EXPORT_MA_CHECK, "Maya ASCII scene (.ma)", saved.save_scene,
        MA_OUTPUT_DIR_FIELD, saved.ma_output_dir)
    add_output_row(
        EXPORT_CAST_CHECK, "Combined model Cast (.cast)", saved.export_cast,
        CAST_OUTPUT_DIR_FIELD, saved.cast_output_dir)
    add_output_row(
        EXPORT_SMD_CHECK, "Source model (.smd)", saved.export_smd,
        SMD_OUTPUT_DIR_FIELD, saved.smd_output_dir)
    add_output_row(
        EXPORT_FBX_CHECK, "Static model with skinning (.fbx)",
        saved.export_fbx, FBX_OUTPUT_DIR_FIELD, saved.fbx_output_dir)
    cmds.text(
        label=(".cast/.smd model export uses bundled/compatible Cast v1.99; "
               ".fbx excludes animation."),
        align="left",
    )
    cmds.separator(height=5, style="in")

    cmds.rowLayout(
        numberOfColumns=4,
        columnWidth4=(165, 165, 165, 165),
    )
    cmds.button(label="Preflight", height=30,
                command=lambda *_: _preflight_from_dialog())
    cmds.button(label="Attach && Export", height=30,
                command=lambda *_: _run_from_dialog())
    cmds.button(label="Batch Weapons...", height=30,
                command=lambda *_: _batch_from_dialog())
    cmds.button(label="Import Animation Safely...", height=30,
                command=lambda *_: import_animation())
    cmds.setParent("..")

    cmds.rowLayout(
        numberOfColumns=5,
        columnWidth5=(130, 130, 130, 130, 130),
    )
    cmds.button(label="Validate Current",
                command=lambda *_: _validate_current_ui())
    cmds.button(label="Select Attachment",
                command=lambda *_: _select_attachment_ui())
    cmds.button(label="Save Current Result",
                command=lambda *_: _save_current_ui())
    cmds.button(label="Open Output Folders",
                command=lambda *_: _open_output_dir_ui())
    cmds.button(label="Close",
                command=lambda *_: cmds.deleteUI(WINDOW_NAME))
    cmds.setParent("..")
    cmds.showWindow(win)


# ---------------------------------------------------------------------------
# Maya command, menu, and plugin entry points.
# ---------------------------------------------------------------------------

class CastDropCallback(OpenMayaUI.MExternalDropCallback):
    """Route supported external CAST drops before Maya's default handler."""

    def __init__(self):
        OpenMayaUI.MExternalDropCallback.__init__(self)

    def externalDropCallback(self, do_drop, control_name, data):
        return handle_external_cast_drop(data, do_drop)


def _install_cast_drop_callback():
    global _CAST_DROP_CALLBACK
    if _CAST_DROP_CALLBACK is None:
        callback = CastDropCallback()
        OpenMayaUI.MExternalDropCallback.addCallback(callback, 0)
        _CAST_DROP_CALLBACK = callback
        log("registered safe external CAST animation drop callback")
    return _CAST_DROP_CALLBACK


def _remove_cast_drop_callback():
    global _CAST_DROP_CALLBACK
    callback = _CAST_DROP_CALLBACK
    if callback is None:
        return
    OpenMayaUI.MExternalDropCallback.removeCallback(callback)
    _CAST_DROP_CALLBACK = None
    log("removed safe external CAST animation drop callback")


class ViewmodelWeaponToolkitCmd(OpenMayaMPx.MPxCommand):
    def __init__(self):
        OpenMayaMPx.MPxCommand.__init__(self)

    def doIt(self, args):
        show_dialog()

    def isUndoable(self):
        return False


def cmdCreator():
    return OpenMayaMPx.asMPxPtr(ViewmodelWeaponToolkitCmd())


def remove_menu():
    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME, menu=True)


def _show_about():
    cmds.confirmDialog(
        title="About %s" % PRODUCT_SHORT_NAME,
        message=("%s v%s\n\n"
                 "weapon:j_gun -> viewhands:tag_weapon\n"
                 "Dual mode duplicates one weapon onto tag_weapon_left/right.\n"
                 "It does not combine two different weapon skeletons.\n"
                 "Optional versioned .ma, .cast, .smd, and static .fbx outputs.\n"
                  "Each format can use an independent output folder.\n"
                  "A JSON verification manifest is always written.\n"
                  "Pure animation CAST drops are safely routed by default.\n"
                  "Uses Maya's Cast translator for imports."
                  % (PRODUCT_NAME, VERSION)),
        button=["OK"],
        defaultButton="OK",
    )


def create_menu():
    remove_menu()
    cmds.setParent(mel.eval("$tmp = $gMainWindow"))
    cmds.menu(MENU_NAME, label=PRODUCT_SHORT_NAME, tearOff=True)
    cmds.menuItem(
        label="Quick Attach (Single Weapon)...",
        annotation="Use saved settings and pick one weapon file.",
        command=lambda *_: quick_attach(),
    )
    cmds.menuItem(
        label="Single-Weapon Builder...",
        annotation="Preflight, attach, batch, save, and validation tools.",
        command=lambda *_: show_dialog(),
    )
    cmds.menuItem(
        label="Dual-Wield Builder...",
        annotation=(
            "Duplicate one weapon and compose left/right Akimbo animations."),
        command=lambda *_: show_dual_dialog(),
    )
    cmds.menuItem(divider=True)
    cmds.menuItem(label="Import Animation Safely...",
                  command=lambda *_: import_animation())
    cmds.menuItem(
        label="Auto-Safe Dropped CAST Animations",
        annotation=("Safely route pure animation CAST files dropped onto "
                    "a Viewmodel Weapon Toolkit scene."),
        checkBox=auto_safe_drop_enabled(),
        command=lambda enabled, *_: set_auto_safe_drop_enabled(enabled),
    )
    cmds.menuItem(label="Validate Current Attachment",
                  command=lambda *_: _validate_current_ui())
    cmds.menuItem(label="Select Current Attachment",
                  command=lambda *_: _select_attachment_ui())
    cmds.menuItem(label="Save Current Result",
                  command=lambda *_: _save_current_ui())
    cmds.menuItem(label="Open Output Folders",
                  command=lambda *_: _open_output_dir_ui())
    cmds.menuItem(divider=True)
    cmds.menuItem(
        label="Clear Saved Settings",
        command=lambda *_: (
            clear_saved_settings(),
            cmds.confirmDialog(
                title=PRODUCT_SHORT_NAME,
                message="Saved Viewmodel Weapon Toolkit settings cleared.",
                button=["OK"],
                defaultButton="OK",
            ),
        ),
    )
    cmds.menuItem(divider=True)
    cmds.menuItem(label="About", command=lambda *_: _show_about())


def initializePlugin(m_object):
    global _CAST_TRANSLATOR_FALLBACK_REGISTERED
    plugin = OpenMayaMPx.MFnPlugin(m_object, "OpenCode", VERSION, "Any")
    plugin.registerCommand(COMMAND_NAME, cmdCreator)
    try:
        plugin.registerCommand(LEGACY_COMMAND_NAME, cmdCreator)
    except Exception:
        plugin.deregisterCommand(COMMAND_NAME)
        raise
    try:
        cmds.pluginInfo(plugin.name(), edit=True, autoload=True)
        cmds.pluginInfo(savePluginPrefs=True)
    except RuntimeError as exc:
        log("could not persist %s auto-load preference: %s" % (
            PRODUCT_SHORT_NAME, exc))
    if cmds.about(batch=True):
        try:
            ensure_cast_plugin()
        except Exception as exc:
            log("official Cast batch load unavailable; using fallback: %s" % exc)
            _register_batch_cast_translator(plugin)
    else:
        ensure_cast_plugin()
        _install_cast_drop_callback()
        cmds.evalDeferred(create_menu)


def uninitializePlugin(m_object):
    global _CAST_TRANSLATOR_FALLBACK_REGISTERED
    plugin = OpenMayaMPx.MFnPlugin(m_object)
    _remove_cast_drop_callback()
    if cmds.window(WINDOW_NAME, exists=True):
        cmds.deleteUI(WINDOW_NAME)
    if cmds.window(DUAL_WINDOW_NAME, exists=True):
        cmds.deleteUI(DUAL_WINDOW_NAME)
    remove_menu()
    if _CAST_TRANSLATOR_FALLBACK_REGISTERED:
        try:
            plugin.deregisterFileTranslator("Cast")
        except RuntimeError as exc:
            log("Cast translator was already unavailable during unload: %s" % exc)
        finally:
            _CAST_TRANSLATOR_FALLBACK_REGISTERED = False
    for command_name in (LEGACY_COMMAND_NAME, COMMAND_NAME):
        try:
            plugin.deregisterCommand(command_name)
        except RuntimeError as exc:
            log("command %s was already unavailable during unload: %s" % (
                command_name, exc))
