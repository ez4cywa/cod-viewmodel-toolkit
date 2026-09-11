r"""CoD Viewmodel Toolkit plugin for Maya 2022 and newer.

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

Dual builds may optionally use a compatible reference-viewhands model to
compensate relative/additive weapon-tag translation tracks when the active
viewhands file has a different local rest pose.

Output formats and their folders are independently selectable: Maya ASCII
(``.ma``), combined model Cast (``.cast``), Source model (``.smd``), and FBX
(``.fbx``). A JSON verification manifest is always written to the common
output folder. Release packages include a project-patched Maya Cast plugin
based on official v2.00; a compatible v1.99 or newer translator can also be
used.

Single/dual animation queues export selected animated formats with DQS
skinning. Animated CAST keeps the assembled rest model, and SMD exports
skeletal frames only. Each queue item is isolated from previous animation.

Load this file through Maya's Plug-in Manager. A ``CoD Viewmodel Toolkit``
menu appears in the main menu bar. The legacy ``attach_gun.py`` loader and
``attachGun`` command remain supported for existing installations.
"""

import datetime
import copy
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
import maya.api.OpenMaya as OpenMaya2


# ---------------------------------------------------------------------------
# Constants.
# ---------------------------------------------------------------------------

DEFAULT_SOURCE_JOINT = "j_gun"
DEFAULT_TARGET_JOINT = "tag_weapon"
DEFAULT_LEFT_TARGET_JOINT = "tag_weapon_left"
DEFAULT_RIGHT_TARGET_JOINT = "tag_weapon_right"
PRODUCT_NAME = "CoD Viewmodel Toolkit"
PRODUCT_SHORT_NAME = "CoD Viewmodel Toolkit"
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
VERSION = "3.4.0"

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
OUTPUT_UNIT_OPTVAR = "codViewmodel_outputUnit"
AUTO_SAFE_DROP_OPTVAR = "attachGun_autoSafeCastAnimationDrop"
DUAL_VIEWHANDS_OPTVAR = "attachGun_dualViewhandsPath"
DUAL_WEAPON_OPTVAR = "attachGun_dualWeaponPath"
DUAL_LEFT_ANIMATION_OPTVAR = "attachGun_dualLeftAnimationPath"
DUAL_RIGHT_ANIMATION_OPTVAR = "attachGun_dualRightAnimationPath"
DUAL_REFERENCE_POSE_OPTVAR = "attachGun_dualReferencePosePath"
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
OUTPUT_UNIT_MENU = "codViewmodel_outputUnitMenu"
DUAL_VIEWHANDS_FIELD = "attachGun_dualViewhandsField"
DUAL_WEAPON_FIELD = "attachGun_dualWeaponField"
DUAL_LEFT_ANIMATION_FIELD = "attachGun_dualLeftAnimationField"
DUAL_RIGHT_ANIMATION_FIELD = "attachGun_dualRightAnimationField"
DUAL_REFERENCE_POSE_FIELD = "attachGun_dualReferencePoseField"
DUAL_MODE_MENU = "attachGun_dualModeMenu"
DUAL_LEFT_TARGET_FIELD = "attachGun_dualLeftTargetField"
DUAL_RIGHT_TARGET_FIELD = "attachGun_dualRightTargetField"
BATCH_ANIMATION_LIST = "attachGun_batchAnimationList"
BATCH_ANIMATION_PROGRESS = "attachGun_batchAnimationProgress"
BATCH_ANIMATION_STATUS = "attachGun_batchAnimationStatus"

_LAST_RESULT = None
_CAST_BATCH_MODULE = None
_CAST_TRANSLATOR_FALLBACK_REGISTERED = False
_CAST_DROP_CALLBACK = None
_TOOLKIT_PLUGIN_PATH = ""
_UNITS_MODULE = None
_OUTPUT_IN_METERS = False


def _units_module():
    global _UNITS_MODULE
    if _UNITS_MODULE is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cod_viewmodel_units.py")
        spec = importlib.util.spec_from_file_location(__name__ + "_units", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _UNITS_MODULE = module
    return _UNITS_MODULE


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
    export_animation: bool = False
    output_unit: str = "original"


@dataclass
class DualWieldOptions(AttachOptions):
    """Options for one duplicated-weapon dual-wield result."""

    left_target_joint: str = DEFAULT_LEFT_TARGET_JOINT
    right_target_joint: str = DEFAULT_RIGHT_TARGET_JOINT
    left_prefix: str = LEFT_WEAPON_PREFIX
    right_prefix: str = RIGHT_WEAPON_PREFIX
    animation_mode: str = "simultaneous"
    shared_hands_source: str = "right"
    reference_pose_path: str = ""


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
    animated_outputs: bool = False
    frame_range: tuple = ()
    framerate: float = 0.0
    animation_verification: dict = field(default_factory=dict)
    output_errors: dict = field(default_factory=dict)
    skinning_method: str = ""
    unit_conversion: dict = field(default_factory=dict)


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
    reference_pose_path: str = ""
    reference_pose_compensation: dict = field(default_factory=dict)


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
        output_unit=_load_string_option(OUTPUT_UNIT_OPTVAR, "original"),
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
    _save_string_option(OUTPUT_UNIT_OPTVAR, options.output_unit)


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
            OUTPUT_UNIT_OPTVAR,
            AUTO_SAFE_DROP_OPTVAR,
            DUAL_VIEWHANDS_OPTVAR,
            DUAL_WEAPON_OPTVAR,
            DUAL_LEFT_ANIMATION_OPTVAR,
            DUAL_RIGHT_ANIMATION_OPTVAR,
            DUAL_REFERENCE_POSE_OPTVAR,
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

    candidate = _bundled_cast_plugin_path() or "castplugin.py"
    try:
        cmds.loadPlugin(candidate, quiet=True)
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

    bundled = _bundled_cast_plugin_path()
    if bundled:
        return bundled

    plugin_dir = os.path.join(
        os.path.dirname(os.path.abspath(sys.executable)), "plug-ins")
    path = os.path.join(plugin_dir, "castplugin.py")
    if os.path.isfile(path):
        return os.path.normpath(os.path.abspath(path))
    raise RuntimeError("Maya Cast plugin file not found: %s" % path)


def _toolkit_module_dir():
    """Resolve this plugin's directory even when Maya omits ``__file__``."""
    path = _TOOLKIT_PLUGIN_PATH or globals().get("__file__", "")
    if path:
        return os.path.dirname(os.path.abspath(path))
    return ""


def _bundled_cast_plugin_path():
    """Resolve release-adjacent or source-checkout CAST before Maya's copy."""
    directory = _toolkit_module_dir()
    if not directory:
        return ""
    for path in (
            os.path.join(directory, "castplugin.py"),
            os.path.join(os.path.dirname(directory), "third_party",
                         "cast", "castplugin.py")):
        if os.path.isfile(path):
            return os.path.normpath(os.path.abspath(path))
    return ""


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


def _cast_import_name(module, name):
    """Mirror the active translator's name normalization during preflight."""
    sanitize = getattr(module, "utilitySanitize", None)
    return str(sanitize(name) or "") if sanitize else str(name or "")


def _cast_bone_inventory(path):
    """Read skeleton and mesh health with cast.py; do not modify the scene."""
    module = _castplugin_module()
    cast_file = module.Cast.load(path)
    bone_names = []
    bone_records = []
    imported_name_sources = {}
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
                    bone_name = _cast_import_name(module, bone.Name())
                    source_name = str(bone.Name() or "")
                    if not bone_name:
                        raise RuntimeError("CAST skeleton contains an empty joint name")
                    previous = imported_name_sources.setdefault(bone_name, source_name)
                    if previous != source_name:
                        raise RuntimeError(
                            "CAST joint names %r and %r both import as %r"
                            % (previous, source_name, bone_name))
                    parent_index = int(bone.ParentIndex())
                    parent_name = None
                    ancestor_names = []
                    local_position = bone.LocalPosition()
                    if 0 <= parent_index < len(bones):
                        parent_name = _cast_import_name(
                            module, bones[parent_index].Name())
                    visited = set()
                    ancestor_index = parent_index
                    while (0 <= ancestor_index < len(bones)
                           and ancestor_index not in visited):
                        visited.add(ancestor_index)
                        ancestor = bones[ancestor_index]
                        ancestor_names.append(_cast_import_name(
                            module, ancestor.Name()))
                        ancestor_index = int(ancestor.ParentIndex())
                    ancestor_names.reverse()
                    bone_names.append(bone_name)
                    bone_records.append({
                        "name": bone_name,
                        "source_name": str(bone.Name()),
                        "index": bone_index,
                        "parent_index": parent_index,
                        "parent_name": parent_name,
                        "ancestor_names": ancestor_names,
                        "local_position": (
                            [float(value) for value in local_position]
                            if local_position is not None else None
                        ),
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


def _cast_animation_inventory(path, allow_models=False):
    """Read animation tracks without changing the Maya scene."""
    module = _castplugin_module()
    cast_file = module.Cast.load(path)
    animations = []
    model_count = 0
    for root in cast_file.Roots():
        model_count += len(root.ChildrenOfType(module.Model))
        animations.extend(root.ChildrenOfType(module.Animation))
    if model_count and not allow_models:
        raise RuntimeError(
            "Animation input must not contain models: %s" % path)
    if len(animations) != 1:
        raise RuntimeError(
            "Animation input must contain exactly one animation; found %d: %s"
            % (len(animations), path))

    animation = animations[0]
    curve_mode_overrides = [
        {
            "node": _cast_import_name(module, override.NodeName()),
            "mode": str(override.Mode() or "absolute"),
            "translation": bool(override.OverrideTranslationCurves()),
            "rotation": bool(override.OverrideRotationCurves()),
            "scale": bool(override.OverrideScaleCurves()),
        }
        for override in animation.CurveModeOverrides()
    ]
    curve_records = []
    all_frames = []
    for curve in animation.Curves():
        frames = tuple(int(value) for value in curve.KeyFrameBuffer() or [])
        values = tuple(float(value) for value in curve.KeyValueBuffer() or [])
        all_frames.extend(frames)
        curve_records.append({
            "node": _cast_import_name(module, curve.NodeName()),
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
        "curve_mode_overrides": curve_mode_overrides,
        "curve_records": curve_records,
    }


_TRANSLATION_PROPERTIES = (
    ("tx", "translateX", 0),
    ("ty", "translateY", 1),
    ("tz", "translateZ", 2),
)


def _inventory_bone_record(inventory, joint_name, label):
    matches = [
        record for record in inventory.get("bone_records", [])
        if _short_name(record.get("name", "")) == joint_name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "%s must contain exactly one %s rest-pose joint; found %d"
            % (label, joint_name, len(matches)))
    record = matches[0]
    position = record.get("local_position")
    if position is None or len(position) != 3:
        raise RuntimeError(
            "%s joint %s has no local rest position"
            % (label, joint_name))
    return record


def _effective_translation_curve_mode(
        curve_record, animation_inventory, ancestor_names):
    """Resolve CAST translation overrides exactly as the importer does."""
    mode = str(curve_record.get("mode") or "absolute").lower()
    for ancestor_name in ancestor_names:
        for override in animation_inventory.get("curve_mode_overrides", []):
            if not override.get("translation"):
                continue
            if _short_name(override.get("node", "")) == \
                    _short_name(ancestor_name):
                return str(override.get("mode") or "absolute").lower()
    return mode


def _reference_pose_side_for_animation(side_data, animation_inventory):
    """Select rest-offset axes whose animation is relative or additive."""
    result = dict(side_data)
    target_joint = result["target_joint"]
    records_by_property = {}
    for record in animation_inventory.get("curve_records", []):
        if _short_name(record.get("node", "")) != target_joint:
            continue
        prop = str(record.get("property", "")).lower()
        if prop not in ("tx", "ty", "tz"):
            continue
        if prop in records_by_property:
            raise RuntimeError(
                "Animation contains duplicate %s.%s tracks"
                % (target_joint, prop))
        records_by_property[prop] = record

    curve_modes = {}
    attribute_offsets = {}
    translation_offset = result["translation_offset"]
    ancestor_names = result.get("ancestor_joints", [])
    for prop, attribute, index in _TRANSLATION_PROPERTIES:
        record = records_by_property.get(prop)
        mode = _effective_translation_curve_mode(
            record, animation_inventory, ancestor_names) if record else None
        curve_modes[prop] = mode
        offset = float(translation_offset[index])
        if mode in ("relative", "additive") and abs(offset) > 1e-9:
            attribute_offsets[attribute] = offset
    result["curve_modes"] = curve_modes
    result["attribute_offsets"] = attribute_offsets
    result["applied_attributes"] = sorted(attribute_offsets)
    return result


def _build_reference_pose_compensation(
        current_inventory,
        reference_inventory,
        animation_inventories,
        left_target_joint,
        right_target_joint,
        reference_path=""):
    """Build per-side local translation offsets from a reference skeleton."""
    base_sides = {}
    sides = {}
    warnings = []
    for side, target_joint in (
            ("left", left_target_joint), ("right", right_target_joint)):
        current = _inventory_bone_record(
            current_inventory, target_joint, "Viewhands")
        reference = _inventory_bone_record(
            reference_inventory, target_joint, "Reference pose")
        current_parent = _short_name(current.get("parent_name") or "")
        reference_parent = _short_name(reference.get("parent_name") or "")
        if current_parent != reference_parent:
            raise RuntimeError(
                "Reference pose parent mismatch for %s: %s != %s"
                % (target_joint, reference_parent or "<root>",
                   current_parent or "<root>"))

        current_position = [
            float(value) for value in current["local_position"]]
        reference_position = [
            float(value) for value in reference["local_position"]]
        translation_offset = [
            reference_position[index] - current_position[index]
            for index in range(3)
        ]
        magnitude = sum(
            value * value for value in translation_offset) ** 0.5
        side_data = {
            "side": side,
            "target_joint": target_joint,
            "parent_joint": current_parent,
            "ancestor_joints": list(current.get("ancestor_names", (
                [current_parent] if current_parent else []))),
            "current_rest_translation": current_position,
            "reference_rest_translation": reference_position,
            "translation_offset": translation_offset,
            "translation_offset_magnitude": magnitude,
        }
        base_sides[side] = side_data
        side_data = _reference_pose_side_for_animation(
            side_data, animation_inventories[side])
        if magnitude > 1e-6 and not side_data["attribute_offsets"]:
            warnings.append(
                "%s reference-pose offset is non-zero, but %s has no "
                "relative/additive target translation tracks"
                % (side.title(), target_joint))
        sides[side] = side_data

    clips = {}
    for clip_side, animation_inventory in animation_inventories.items():
        clips[clip_side] = {
            "targets": {
                target_side: _reference_pose_side_for_animation(
                    side_data, animation_inventory)
                for target_side, side_data in base_sides.items()
            }
        }

    return {
        "enabled": True,
        "reference_pose_path": reference_path,
        "sides": sides,
        "clips": clips,
        "warnings": warnings,
    }


def _disabled_reference_pose_compensation():
    return {
        "enabled": False,
        "reference_pose_path": "",
        "sides": {},
        "clips": {},
        "warnings": [],
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
        right_target_joint=DEFAULT_RIGHT_TARGET_JOINT,
        reference_pose_path=""):
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

    reference_pose = _disabled_reference_pose_compensation()
    if str(reference_pose_path or "").strip():
        reference_pose_path = _validate_cast_path(
            reference_pose_path, "Reference pose")
        reference_full = _cast_bone_inventory(reference_pose_path)
        reference_pose = _build_reference_pose_compensation(
            viewhands_full,
            reference_full,
            {"left": left_animation, "right": right_animation},
            left_target_joint,
            right_target_joint,
            reference_path=reference_pose_path,
        )
        reference_pose["reference_viewhands"] = public_model_inventory(
            reference_full)
        warnings.extend(reference_pose["warnings"])

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
        "reference_pose_compensation": reference_pose,
        "viewhands_side_counts": side_counts,
        "shared_curve_count": len(common_keys),
        "conflicting_shared_curve_count": len(conflicting_keys),
        "orphan_curve_nodes": orphan_nodes,
        "warnings": warnings,
    }


def verify_exported_cast(path,
                         source_joint=DEFAULT_SOURCE_JOINT,
                         target_joint=DEFAULT_TARGET_JOINT,
                         allow_animation=False):
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
    if inventory["animation_count"] and not allow_animation:
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
        **({"distance_conversion": "ft_to_m", "fbx_storage_unit": "cm",
            "physical_size_preserved": True} if _OUTPUT_IN_METERS else {}),
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
def _temporary_cast_settings(requested, required=False):
    """Scope translator preferences to one operation, including failure paths."""
    settings_sets = [
        module.sceneSettings for module in _loaded_castplugin_modules()
        if isinstance(getattr(module, "sceneSettings", None), dict)
    ]
    if required and not settings_sets:
        raise RuntimeError("Cast plugin sceneSettings are unavailable")
    originals = []
    try:
        for settings in settings_sets:
            original = {name: settings[name] for name in requested
                        if name in settings}
            originals.append((settings, original))
            settings.update({name: requested[name] for name in original})
        yield
    finally:
        for settings, original in reversed(originals):
            settings.update(original)


def _temporary_cast_import_settings(options):
    """Disable imported IK/constraints without persisting setting changes."""
    return _temporary_cast_settings({
        "importIK": not options.disable_import_ik,
        "importConstraints": not options.disable_import_constraints,
    })


def _temporary_cast_export_settings(
        animation=False, model=True, bake_keyframes=None):
    """Set model/animation export flags without persisting user settings."""
    return _temporary_cast_settings({
        "exportModel": bool(model),
        "exportAnim": bool(animation),
        "bakeKeyframes": bool(animation if bake_keyframes is None
                              else bake_keyframes),
    }, required=True)


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
    restored, seen = [], set()
    with _temporary_cast_settings({"importAtTime": bool(import_at_time),
                                   "importReset": False, "importLooping": False}):
        try:
            if _units_module().scene_is_metric():
                for module in _loaded_castplugin_modules():
                    runtime = getattr(module, "runtimeSettings", None)
                    if runtime is not None and id(runtime) not in seen:
                        seen.add(id(runtime))
                        old = runtime.get("retargetScale", 1.0)
                        restored.append((runtime, old))
                        runtime["retargetScale"] = old * 30.48
            yield
        finally:
            for runtime, old in restored:
                runtime["retargetScale"] = old


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
    if not curves:
        return ()
    key_times = cmds.keyframe(curves, query=True, timeChange=True) or []
    if not key_times:
        return ()
    return (float(min(key_times)), float(max(key_times)))


def _combined_frame_range(*frame_ranges):
    """Return the content range covered by one or more animation clips."""
    if not frame_ranges:
        raise RuntimeError("At least one animation frame range is required")
    normalized = []
    for frame_range in frame_ranges:
        if len(frame_range) != 2:
            raise RuntimeError("Animation frame ranges need a start and end")
        start, end = (float(value) for value in frame_range)
        if end < start:
            raise RuntimeError("Animation frame range ends before it starts")
        normalized.append((start, end))
    return (
        min(frame_range[0] for frame_range in normalized),
        max(frame_range[1] for frame_range in normalized),
    )


def _visible_playback_range(content_range):
    """Return a legal Maya time-slider range for an animation content range."""
    start, end = _combined_frame_range(content_range)
    if end == start:
        end = start + 1.0
    return (start, end)


def _set_scene_animation_range(content_range):
    """Give Maya a legal range while callers retain exact content bounds."""
    content_range = _combined_frame_range(content_range)
    playback_range = _visible_playback_range(content_range)
    cmds.playbackOptions(
        animationStartTime=playback_range[0],
        animationEndTime=playback_range[1],
        minTime=playback_range[0],
        maxTime=playback_range[1],
        loop="once",
    )
    cmds.currentTime(content_range[0], edit=True)
    return playback_range


def _apply_reference_pose_compensation(
        target_node, side_compensation, frame_range):
    """Shift imported target translation keys within one clip range."""
    attribute_offsets = dict(
        side_compensation.get("attribute_offsets", {}))
    if _units_module().scene_is_metric():
        factor = OpenMaya.MDistance(30.48, OpenMaya.MDistance.kCentimeters).asUnits(
            OpenMaya.MDistance.uiUnit())
        attribute_offsets = {name: value * factor for name, value in attribute_offsets.items()}
    report = {
        "enabled": bool(attribute_offsets),
        "target_node": target_node,
        "frame_range": [float(frame_range[0]), float(frame_range[1])],
        "translation_offset": list(
            side_compensation.get("translation_offset", (0.0, 0.0, 0.0))),
        "attribute_offsets": attribute_offsets,
        "applied_curves": [],
        "applied_curve_count": 0,
    }
    for attribute, offset in sorted(attribute_offsets.items()):
        plug = "%s.%s" % (target_node, attribute)
        curves = sorted(set(cmds.listConnections(
            plug,
            source=True,
            destination=False,
            type="animCurve",
        ) or []))
        if len(curves) != 1:
            raise RuntimeError(
                "Reference-pose compensation expected one animation curve "
                "on %s; found %d" % (plug, len(curves)))
        curve = curves[0]
        key_times = cmds.keyframe(
            curve,
            query=True,
            time=(float(frame_range[0]), float(frame_range[1])),
            timeChange=True,
        ) or []
        if not key_times:
            raise RuntimeError(
                "Reference-pose compensation found no keys on %s in %s"
                % (plug, frame_range))
        cmds.keyframe(
            curve,
            edit=True,
            relative=True,
            valueChange=float(offset),
            time=(float(frame_range[0]), float(frame_range[1])),
        )
        report["applied_curves"].append({
            "attribute": attribute,
            "curve": curve,
            "offset": float(offset),
            "key_count": len(key_times),
        })
    report["applied_curve_count"] = len(report["applied_curves"])
    return report


def _apply_clip_reference_pose_compensation(
        reference_pose, clip_side, target_nodes, frame_range,
        animation_mode):
    """Apply one imported clip's correction to its routed target joints."""
    if not reference_pose.get("enabled"):
        return {
            "enabled": False,
            "clip_side": clip_side,
            "targets": {},
            "applied_curve_count": 0,
        }
    target_sides = DUAL_SIDES if animation_mode == "sequential" \
        else (clip_side,)
    clip = reference_pose.get("clips", {}).get(clip_side, {})
    compensation_by_target = clip.get("targets", {})
    reports = {}
    for target_side in target_sides:
        reports[target_side] = _apply_reference_pose_compensation(
            target_nodes[target_side],
            compensation_by_target.get(target_side, {}),
            frame_range,
        )
    return {
        "enabled": True,
        "clip_side": clip_side,
        "targets": reports,
        "applied_curve_count": sum(
            report["applied_curve_count"] for report in reports.values()),
    }


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
    if options.output_unit not in ("original", "m"):
        raise RuntimeError("Output unit must be original or m")
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


def _update_output_file_stats(payload, output_paths):
    """Write consistent path, existence, and size fields for every output."""
    for name, path in output_paths.items():
        exists = os.path.isfile(path)
        payload["output_%s" % name] = path
        payload["output_%s_exists" % name] = exists
        payload["output_%s_size" % name] = (
            os.path.getsize(path) if exists else 0)


def _write_manifest(result):
    if not result.output_manifest:
        return
    payload = asdict(result)
    _update_output_file_stats(payload, {
        "scene": result.output_scene,
        "cast": result.output_cast,
        "smd": result.output_smd,
        "fbx": result.output_fbx,
    })
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
    if _OUTPUT_IN_METERS:
        serializer = sys.modules[_castplugin_module().Cast.__module__]
        document = serializer.Cast.load(path)
        _units_module().scale_cast(document, serializer, model_factor=0.01).save(path)
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
    naming_path = result.weapon_path
    if result.animated_outputs:
        base_prefix = "animation"
        naming_path = result.animation_path
        if isinstance(result, DualWieldResult):
            base_prefix = "dual_animation_%s" % result.animation_mode
            naming_path = result.left_animation_path
    paths = _versioned_output_paths(
        output_dir,
        naming_path,
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
    report, translator_error = (None, "") if _OUTPUT_IN_METERS else _try_registered_smd_export(
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
    if options.output_unit == "m":
        return _units_module().export_copy(sys.modules[__name__], result, options, allocate)
    if result.animated_outputs:
        return _write_animation_outputs(result, options, allocate=allocate)
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


def _build_single_attachment(viewhands_path, weapon_path, options=None):
    """Build and validate a clean single-weapon scene, without exporting."""
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

    if options.export_animation:
        _use_dqs_skinning()
        result.skinning_method = "dualQuaternion"
        if options.export_cast:
            try:
                result._cast_bind_model = _capture_cast_bind_model()
            except Exception as exc:
                result._cast_bind_error = str(exc)
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


def attach_gun(viewhands_path, weapon_path, options=None):
    """Attach one weapon and write the selected versioned outputs."""
    options = options or AttachOptions()
    result = _build_single_attachment(viewhands_path, weapon_path, options)
    _write_result_outputs(result, options, allocate=True)
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
    state.setdefault("reference_pose_path", "")
    state.setdefault(
        "reference_pose_compensation",
        _disabled_reference_pose_compensation())
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
    scene_animation_range = (
        float(cmds.playbackOptions(query=True, animationStartTime=True)),
        float(cmds.playbackOptions(query=True, animationEndTime=True)),
    )
    content_range = _combined_frame_range(
        state["left_clip_range"], state["right_clip_range"])
    expected_playback_range = _visible_playback_range(content_range)
    stored_playback_range = tuple(
        float(value) for value in state["playback_range"])

    def ranges_match(actual, expected):
        return all(abs(value - wanted) <= 1e-6
                   for value, wanted in zip(actual, expected))

    legacy_single_frame = (
        content_range[0] == content_range[1] and
        ranges_match(stored_playback_range, content_range))
    if not (ranges_match(stored_playback_range, expected_playback_range) or
            legacy_single_frame):
        raise RuntimeError(
            "Dual playback metadata %s does not match clip range %s"
            % (stored_playback_range, content_range))
    allowed_playback_ranges = [expected_playback_range]
    if legacy_single_frame:
        # Maya 2025 coerced the old min=max setting to (frame - 1, frame).
        allowed_playback_ranges.extend((
            content_range,
            (content_range[0] - 1.0, content_range[1]),
        ))
    if not any(ranges_match(playback_range, expected)
               for expected in allowed_playback_ranges):
        raise RuntimeError(
            "Dual playback range changed: expected %s, got %s"
            % (expected_playback_range, playback_range))
    if not any(ranges_match(scene_animation_range, expected)
               for expected in allowed_playback_ranges):
        raise RuntimeError(
            "Dual animation range changed: expected %s, got %s"
            % (expected_playback_range, scene_animation_range))
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
        "scene_animation_range": scene_animation_range,
        "content_range": content_range,
        "left_clip_range": tuple(state["left_clip_range"]),
        "right_clip_range": tuple(state["right_clip_range"]),
        "left": left,
        "right": right,
        "joint_count": actual_joint_count,
        "mesh_count": actual_mesh_count,
        "reference_pose_compensation": state.get(
            "reference_pose_compensation",
            _disabled_reference_pose_compensation()),
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
    options.reference_pose_path = str(
        options.reference_pose_path or "").strip()
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
        reference_pose_path=options.reference_pose_path,
    )
    viewhands_path = _validate_cast_path(viewhands_path, "Viewhands")
    weapon_path = _validate_cast_path(weapon_path, "Weapon")
    left_animation_path = _validate_cast_path(
        left_animation_path, "Left animation")
    right_animation_path = _validate_cast_path(
        right_animation_path, "Right animation")
    reference_pose = preflight["reference_pose_compensation"]
    options.reference_pose_path = reference_pose.get(
        "reference_pose_path", "")
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

    cast_bind_model = None
    cast_bind_error = ""
    if options.export_animation:
        _use_dqs_skinning()
        if options.export_cast:
            try:
                cast_bind_model = _capture_cast_bind_model()
            except Exception as exc:
                cast_bind_error = str(exc)

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
    animation_range = _combined_frame_range(
        left_clip_range, right_clip_range)
    playback_range = _visible_playback_range(animation_range)

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
        "reference_pose_path": options.reference_pose_path,
        "reference_pose_compensation": reference_pose,
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
    target_nodes = {
        "left": _node_from_uuid(left_target_uuid),
        "right": _node_from_uuid(right_target_uuid),
    }
    left_import_report["reference_pose_compensation"] = \
        _apply_clip_reference_pose_compensation(
            reference_pose,
            "left",
            target_nodes,
            left_clip_range,
            options.animation_mode,
        )
    right_import_report["reference_pose_compensation"] = \
        _apply_clip_reference_pose_compensation(
            reference_pose,
            "right",
            target_nodes,
            right_clip_range,
            options.animation_mode,
        )
    state["left_import_report"] = left_import_report
    state["right_import_report"] = right_import_report
    _set_scene_animation_range(animation_range)
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
        reference_pose_path=options.reference_pose_path,
        reference_pose_compensation=reference_pose,
        animated_outputs=options.export_animation,
        skinning_method="dualQuaternion" if options.export_animation else "",
        frame_range=animation_range,
        framerate=preflight["left_animation"]["framerate"],
        warnings=warnings,
    )
    _allocate_result_output_paths(result, options.output_dir, options)
    if cast_bind_model is not None:
        result._cast_bind_model = cast_bind_model
    if cast_bind_error:
        result._cast_bind_error = cast_bind_error
    state["output_scene"] = result.output_scene
    state["output_cast"] = result.output_cast
    state["output_smd"] = result.output_smd
    state["output_fbx"] = result.output_fbx
    state["output_manifest"] = result.output_manifest
    state["requested_outputs"] = dict(result.requested_outputs)
    state["animated_outputs"] = result.animated_outputs
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
        reference_pose = dict(state.get(
            "reference_pose_compensation",
            _disabled_reference_pose_compensation()))
        if reference_pose.get("enabled"):
            reference_pose["clips"] = dict(reference_pose.get("clips", {}))
            reference_pose["clips"][side] = {
                "targets": {
                    target_side: _reference_pose_side_for_animation(
                        reference_pose["sides"][target_side], inventory)
                    for target_side in DUAL_SIDES
                }
            }
        report["reference_pose_compensation"] = \
            _apply_clip_reference_pose_compensation(
                reference_pose,
                side,
                {
                    target_side: _node_from_uuid(
                        state["%s_target_uuid" % target_side])
                    for target_side in DUAL_SIDES
                },
                new_range,
                state["animation_mode"],
            )
        state["%s_animation_path" % side] = os.path.normpath(
            os.path.abspath(animation_path))
        state["%s_clip_range" % side] = new_range
        other_side = "right" if side == "left" else "left"
        other_range = tuple(state["%s_clip_range" % other_side])
        animation_range = _combined_frame_range(new_range, other_range)
        playback_range = _visible_playback_range(animation_range)
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
            reference_pose_path=state.get("reference_pose_path", ""),
        )
        state["preflight"] = updated_preflight
        state["reference_pose_compensation"] = updated_preflight[
            "reference_pose_compensation"]
        state["warnings"] = (
            list(state.get("structural_warnings", [])) +
            list(updated_preflight["warnings"]))
        _write_dual_state(state_node, state)
        _set_scene_animation_range(animation_range)
        validation = validate_dual_wield()
        if isinstance(_LAST_RESULT, DualWieldResult):
            setattr(_LAST_RESULT, "%s_animation_path" % side,
                    state["%s_animation_path" % side])
            setattr(_LAST_RESULT, "%s_clip_range" % side, new_range)
            setattr(_LAST_RESULT, "%s_import_report" % side, report)
            _LAST_RESULT.preflight = updated_preflight
            _LAST_RESULT.reference_pose_path = state.get(
                "reference_pose_path", "")
            _LAST_RESULT.reference_pose_compensation = state[
                "reference_pose_compensation"]
            _LAST_RESULT.warnings = list(state["warnings"])
            _LAST_RESULT.frame_range = animation_range
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
# Animated outputs and single/dual animation queues.
# ---------------------------------------------------------------------------

def _animation_export_range(content_range=()):
    values = tuple(content_range) if content_range else (
        float(cmds.playbackOptions(query=True, animationStartTime=True)),
        float(cmds.playbackOptions(query=True, animationEndTime=True)),
    )
    if values[0] < 0 or values[1] < values[0] or any(
            value != int(value) for value in values):
        raise RuntimeError("Animation export requires non-negative whole frames")
    return tuple(int(value) for value in values)


def _use_dqs_skinning():
    for cluster in cmds.ls(type="skinCluster") or []:
        cmds.setAttr(cluster + ".skinningMethod", 1)


def _capture_cast_bind_model():
    """Capture the assembled rest model before animation changes skin binding.

    CAST rebinds the exported geometry against the stored skeleton. Exporting
    a posed mesh would change multi-influence deformation on subsequent frames.
    Keep this object in memory only, never in the JSON result dataclass.
    """
    _require_cast_model_export_version()
    serializer = sys.modules[_castplugin_module().Cast.__module__]
    with tempfile.TemporaryDirectory(prefix="vwt_bind_model_") as directory:
        path = os.path.join(directory, "bind.cast")
        with _temporary_cast_export_settings():
            cmds.file(path, force=True, type=cast_translator_name(), exportAll=True,
                      options="exportModel=1;exportAnim=0;bakeKeyframes=0")
        model_cast = serializer.Cast.load(path)

        def absolutize_files(node):
            for child in node.childNodes:
                if isinstance(child, serializer.File):
                    value = child.Path()
                    if value and not os.path.isabs(value):
                        child.SetPath(os.path.normpath(os.path.join(directory, value)))
                absolutize_files(child)

        for root in model_cast.Roots():
            absolutize_files(root)
            for model in root.ChildrenOfType(serializer.Model):
                for mesh in model.Meshes():
                    if mesh.MaximumWeightInfluence() > 0:
                        mesh.SetSkinningMethod("quaternion")
        return model_cast


def export_cast_animation(path, result):
    """Combine the unchanged rest model with the writer's baked animation."""
    _require_cast_model_export_version()
    bind_model = getattr(result, "_cast_bind_model", None)
    if bind_model is None:
        raise RuntimeError(getattr(result, "_cast_bind_error", "") or
                           "Animation CAST export needs its original assembled bind model")
    bake_keyframes = result.frame_range[1] > result.frame_range[0]
    with _temporary_cast_export_settings(
            animation=True, model=False, bake_keyframes=bake_keyframes):
        with _temporary_baked_joint_animation(result.frame_range):
            cmds.file(
                path, force=True, type=cast_translator_name(), exportAll=True,
                options="exportModel=0;exportAnim=1;bakeKeyframes=%d"
                % int(bake_keyframes))
    combined = _castplugin_module().Cast.load(path)
    serializer = sys.modules[_castplugin_module().Cast.__module__]
    root = combined.Roots()[0]
    for bind_root in bind_model.Roots():
        for model in bind_root.ChildrenOfType(serializer.Model):
            root.CreateChild(copy.deepcopy(model))
    combined.save(path)
    model_report = verify_exported_cast(
        path, result.source_joint_name, result.target_joint_name,
        allow_animation=True)
    if isinstance(result, DualWieldResult):
        verify_exported_cast(
            path, _short_name(result.right_source_node),
            _short_name(result.right_target_node), allow_animation=True)
    animation = _cast_animation_inventory(path, allow_models=True)
    if tuple(animation["frame_range"]) != tuple(result.frame_range):
        raise RuntimeError("CAST output has an incorrect animation frame range")
    if abs(animation["framerate"] - result.framerate) > 1e-5:
        raise RuntimeError("CAST output has an incorrect animation frame rate")
    model_report["animation"] = _public_animation_inventory(animation)
    model_report["skinning_method"] = "dualQuaternion"
    model_report["bind_pose_preserved"] = True
    return model_report


@contextmanager
def _temporary_baked_joint_animation(frame_range):
    """Sample scene evaluation before conversion, then restore original curves."""
    joints = cmds.ls(type="joint", long=True) or []
    if not joints:
        raise RuntimeError("Animation export has no joints")
    original_time = cmds.currentTime(query=True)
    undo_enabled = cmds.undoInfo(query=True, state=True)
    if not undo_enabled:
        cmds.undoInfo(stateWithoutFlush=True)
    cmds.undoInfo(openChunk=True, chunkName="ViewmodelAnimationExportBake")
    try:
        # Guarantee the chunk is nonempty even if the bake command fails.
        marker = cmds.createNode("network", name="__vwt_export_bake_marker")
        cmds.delete(marker)
        cmds.bakeResults(
            joints, time=frame_range, sampleBy=1, simulation=True,
            sparseAnimCurveBake=False, preserveOutsideKeys=True,
            attribute=["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"])
        yield
    finally:
        cmds.undoInfo(closeChunk=True)
        try:
            cmds.undo()
        finally:
            if not undo_enabled:
                cmds.undoInfo(stateWithoutFlush=False)
            cmds.currentTime(original_time, edit=True)


def export_fbx_animation(path, frame_range):
    """Export skinned geometry and baked animation; restore FBX preferences."""
    translator = _ensure_fbx_exporter()
    settings = (
        ("FBXExportBakeComplexAnimation", "true"),
        ("FBXExportBakeComplexStart", str(int(frame_range[0]))),
        ("FBXExportBakeComplexEnd", str(int(frame_range[1]))),
        ("FBXExportBakeComplexStep", "1"),
        ("FBXExportBakeResampleAnimation", "true"),
        ("FBXExportSkins", "true"),
        ("FBXExportShapes", "true"),
        ("FBXExportConstraints", "false"),
        ("FBXExportInputConnections", "true"),
        ("FBXExportAnimationOnly", "false"),
    )
    original = []
    animation_property = "Export|IncludeGrp|Animation"
    was_enabled = _fbx_property_query(animation_property)
    try:
        _fbx_property_set(animation_property, True)
        for command, value in settings:
            original.append((command, mel.eval(command + " -q")))
            mel.eval("%s -v %s" % (command, value))
        with _temporary_baked_joint_animation(frame_range):
            cmds.file(path, force=True, type=translator,
                      exportAll=True, options="v=0;")
    finally:
        for command, value in reversed(original):
            if isinstance(value, bool):
                value = "true" if value else "false"
            mel.eval("%s -v %s" % (command, value))
        _fbx_property_set(animation_property, was_enabled)
    report = verify_exported_fbx(path)
    report.update(animation_included=True, frame_range=list(frame_range),
                  skinning_method="dualQuaternion")
    return report


def _smd_animation_joints():
    """Use hierarchy order and nearest joint parents, folding in transforms."""
    joints = sorted(cmds.ls(type="joint", long=True) or [],
                    key=lambda node: (node.count("|"), node))
    if not joints:
        raise RuntimeError("SMD animation has no joints")
    names = [_short_name(node) for node in joints]
    if len(set(names)) != len(names):
        raise RuntimeError("SMD animation requires unique joint names")
    indexes = {node: index for index, node in enumerate(joints)}
    records = []
    for node, name in zip(joints, names):
        parent = node.rsplit("|", 1)[0]
        while parent and parent not in indexes:
            parent = parent.rsplit("|", 1)[0]
        selection = OpenMaya2.MSelectionList()
        selection.add(node)
        records.append((name, indexes.get(parent, -1), selection.getDagPath(0)))
    return records


def export_smd_animation(path, frame_range):
    """Write Source SMD v1 skeletal frames (no mesh), in cm and XYZ radians."""
    records = _smd_animation_joints()
    original_time = cmds.currentTime(query=True)
    previous_rotations = {}
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as stream:
            stream.write("version 1\nnodes\n")
            for index, (name, parent, _) in enumerate(records):
                stream.write('%d "%s" %d\n' % (
                    index, _smd_safe_name(name, "joint_%d" % index), parent))
            stream.write("end\nskeleton\n")
            for frame in range(frame_range[0], frame_range[1] + 1):
                cmds.currentTime(frame, edit=True)
                matrices = [dag.inclusiveMatrix() for _, _, dag in records]
                stream.write("time %d\n" % (frame - frame_range[0]))
                for index, (name, parent, _) in enumerate(records):
                    matrix = matrices[index]
                    if parent >= 0:
                        matrix = matrix * matrices[parent].inverse()
                    transform = OpenMaya2.MTransformationMatrix(matrix)
                    scale = transform.scale(OpenMaya2.MSpace.kTransform)
                    shear = transform.shear(OpenMaya2.MSpace.kTransform)
                    if any(abs(value - 1.0) > 1e-5 for value in scale) or any(
                            abs(value) > 1e-5 for value in shear):
                        raise RuntimeError(
                            "SMD cannot store scale/shear: %s at frame %s"
                            % (name, frame))
                    position = transform.translation(OpenMaya2.MSpace.kTransform)
                    rotation = transform.rotation().reorder(OpenMaya2.MEulerRotation.kXYZ)
                    if index in previous_rotations:
                        rotation = rotation.closestSolution(previous_rotations[index])
                    previous_rotations[index] = rotation
                    stream.write("%d %.9g %.9g %.9g %.9g %.9g %.9g\n" % (
                        index, position.x * (0.01 if _OUTPUT_IN_METERS else 1.0),
                        position.y * (0.01 if _OUTPUT_IN_METERS else 1.0),
                        position.z * (0.01 if _OUTPUT_IN_METERS else 1.0),
                        rotation.x, rotation.y, rotation.z))
            stream.write("end\n")
    finally:
        cmds.currentTime(original_time, edit=True)
    return {
        "path": path, "size": os.path.getsize(path),
        "bone_count": len(records), "animation_included": True,
        "frame_count": frame_range[1] - frame_range[0] + 1,
        "source_frame_range": list(frame_range), "start_frame": 0,
        "mesh_included": False, "linear_unit": "m" if _OUTPUT_IN_METERS else "cm", "rotation_unit": "radian",
    }


def _write_animation_outputs(result, options, allocate=True):
    """Write selected animated formats and record independent format failures."""
    if options.output_unit == "m":
        return _units_module().export_copy(sys.modules[__name__], result, options, allocate)
    validate_output_options(options)
    result.frame_range = _animation_export_range(result.frame_range)
    result.framerate = float(_castplugin_module().utilityUnitToFramerate(
        OpenMaya.MTime.uiUnit()))
    if allocate:
        _allocate_result_output_paths(result, options.output_dir, options)
    result.output_errors = {}
    # Keep the in-memory scene name out of the temporary baseline directory.
    cmds.file(rename=result.output_scene or
              os.path.splitext(result.output_manifest)[0] + ".ma")
    for output in selected_output_formats(options):
        attribute = "output_scene" if output == "ma" else "output_" + output
        path = getattr(result, attribute)
        try:
            # Publish each file only after its writer/verification succeeds.
            with tempfile.TemporaryDirectory(
                    prefix=".vwt_", dir=os.path.dirname(path)) as staging:
                temporary_path = os.path.join(staging, os.path.basename(path))
                report = None
                if output == "ma":
                    cmds.file(rename=temporary_path)
                    try:
                        cmds.file(save=True, type="mayaAscii", force=True)
                    finally:
                        cmds.file(rename=path)
                elif output == "cast":
                    report = export_cast_animation(temporary_path, result)
                elif output == "smd":
                    report = export_smd_animation(temporary_path, result.frame_range)
                elif output == "fbx":
                    report = export_fbx_animation(temporary_path, result.frame_range)
                if not os.path.isfile(temporary_path) or not os.path.getsize(temporary_path):
                    raise RuntimeError("Animation output was not written")
                os.replace(temporary_path, path)
                if report is not None:
                    report["path"] = path
                    setattr(result, output + "_verification", report)
        except Exception as exc:
            result.output_errors[output] = str(exc)
            log("ANIMATION EXPORT ERROR %s: %s" % (output, exc))
    _write_manifest(result)


def _animation_jobs(paths, dual=False):
    """Normalize local paths and remove duplicates without reordering jobs."""
    if isinstance(paths, (str, bytes)):
        raise RuntimeError("Expected an animation list, not one path string")
    jobs = []
    seen = set()
    for value in paths:
        if dual:
            if isinstance(value, (str, bytes)) or len(value) != 2:
                raise RuntimeError("Each dual animation job needs a left/right pair")
            values = value
        else:
            values = (value,)
        normalized = []
        for path in values:
            path = str(path).strip()
            if not path:
                raise RuntimeError("Animation queue contains an empty path")
            if not re.match(r"^[A-Za-z]:[/\\]", path):
                path = _local_path_from_drop_url(path)
            if not path:
                raise RuntimeError("Animation queue requires local file paths")
            normalized.append(os.path.normpath(os.path.abspath(path)))
        key = tuple(os.path.normcase(path) for path in normalized)
        if key not in seen:
            jobs.append(tuple(normalized))
            seen.add(key)
    if not jobs:
        raise RuntimeError("Add at least one animation to the queue")
    return jobs


def _run_animation_queue(viewhands_path, weapon_path, paths, options,
                         dual=False, progress=None):
    """Run independent clips/pairs; progress returns False to cancel between jobs."""
    global _LAST_RESULT
    validate_output_options(options)
    jobs = _animation_jobs(paths, dual=dual)
    viewhands_path = _validate_cast_path(viewhands_path, "Viewhands")
    weapon_path = _validate_cast_path(weapon_path, "Weapon")
    if not dual:
        preflight_inputs(viewhands_path, weapon_path,
                         options.source_joint, options.target_joint)
    if cmds.file(query=True, modified=True) and not options.force_new_scene:
        raise RuntimeError("Save the current scene or approve a new scene first")
    options = replace(options, force_new_scene=True, export_animation=True)
    output_dir = resolved_output_directories(options)["manifest"]
    os.makedirs(output_dir, exist_ok=True)
    descriptor, summary_path = tempfile.mkstemp(
        prefix="dual_animation_batch_" if dual else "animation_batch_",
        suffix=".json", dir=output_dir)
    os.close(descriptor)
    summary = {
        "plugin_version": VERSION, "dual": dual,
        "viewhands_path": viewhands_path, "weapon_path": weapon_path,
        "requested_formats": list(selected_output_formats(options)),
        "total": len(jobs), "completed": 0, "cancelled": False,
        "items": [], "summary_path": summary_path,
    }
    def save_summary():
        with open(summary_path, "w", encoding="utf-8") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)

    save_summary()
    with tempfile.TemporaryDirectory(prefix="vwt_animation_batch_") as temporary:
        baseline_path = os.path.join(temporary, "baseline.ma")
        baseline_result = None
        try:
            for index, job in enumerate(jobs):
                if progress is not None and progress(index, len(jobs), job) is False:
                    summary["cancelled"] = True
                    break
                item = {"inputs": list(job), "status": "failed"}
                _LAST_RESULT = None
                try:
                    for path in job:
                        _cast_animation_inventory(_validate_cast_path(path, "Animation"))
                    if dual:
                        result = attach_dual_wield(
                            viewhands_path, weapon_path, job[0], job[1], options)
                    else:
                        if baseline_result is None:
                            baseline_result = _build_single_attachment(
                                viewhands_path, weapon_path, options)
                            cmds.file(rename=baseline_path)
                            cmds.file(save=True, type="mayaAscii", force=True)
                        else:
                            cmds.file(baseline_path, open=True, force=True,
                                      prompt=False, executeScriptNodes=False)
                        result = replace(
                            baseline_result, animated_outputs=True,
                            warnings=list(baseline_result.warnings),
                            animation_path=job[0])
                        if hasattr(baseline_result, "_cast_bind_model"):
                            result._cast_bind_model = baseline_result._cast_bind_model
                        if hasattr(baseline_result, "_cast_bind_error"):
                            result._cast_bind_error = baseline_result._cast_bind_error
                        _LAST_RESULT = result
                        result.animation_verification = import_animation_file(
                            job[0], protect_translation=True,
                            source_joint=options.source_joint,
                            target_joint=options.target_joint)
                        if not result.animation_verification["anim_curve_count"]:
                            raise RuntimeError("Animation contains no matching joint tracks")
                        result.frame_range = tuple(
                            result.animation_verification["animation_range"])
                        _write_animation_outputs(result, options)
                    item.update(
                        status=("failed" if len(result.output_errors) ==
                                len(selected_output_formats(options)) else
                                "partial" if result.output_errors else "ok"),
                        manifest=result.output_manifest,
                        output_errors=dict(result.output_errors),
                        outputs={name: getattr(result, "output_%s" % name)
                                 for name in ("scene", "cast", "smd", "fbx")
                                 if getattr(result, "output_%s" % name) and
                                 ("ma" if name == "scene" else name)
                                 not in result.output_errors},
                        frame_range=list(result.frame_range),
                        framerate=result.framerate)
                except Exception as exc:
                    _LAST_RESULT = None
                    item["error"] = str(exc)
                    log("BATCH ANIMATION ERROR %s: %s" % (job, exc))
                    log(traceback.format_exc())
                summary["items"].append(item)
                summary["completed"] = index + 1
                save_summary()
        finally:
            if os.path.normpath(cmds.file(query=True, sceneName=True)) == baseline_path:
                cmds.file(rename="untitled")
            save_summary()
    return summary


def batch_export_animations(viewhands_path, weapon_path, animation_paths,
                            options=None, progress=None):
    """Export one assembled single-weapon scene per animation CAST path."""
    return _run_animation_queue(
        viewhands_path, weapon_path, animation_paths,
        options or AttachOptions(), progress=progress)


def batch_export_dual_animations(viewhands_path, weapon_path, animation_pairs,
                                 options=None, progress=None):
    """Export one dual-wield scene per explicit (left, right) CAST pair."""
    return _run_animation_queue(
        viewhands_path, weapon_path, animation_pairs,
        options or DualWieldOptions(), dual=True, progress=progress)


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
    return _set_scene_animation_range((start, end))


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
    # Re-import can reuse existing curves, so returnNewNodes is not a complete
    # list of animation targets (notably when reopening a metric output MA).
    for record in _cast_animation_inventory(animation_path)["curve_records"]:
        targets = ([_node_from_uuid(hand_uuid)] if record["node"] == source_joint else
                   cmds.ls(record["node"], type="joint", long=True) or [])
        attribute = "rotate" if record["property"] == "rq" else record["property"]
        if len(targets) == 1 and cmds.objExists(targets[0] + "." + attribute):
            anim_curves.extend(cmds.listConnections(targets[0] + "." + attribute,
                source=True, destination=False, type="animCurve") or [])
    anim_curves = sorted(set(anim_curves))
    if not anim_curves:
        raise RuntimeError("Imported animation created no matching keyframes")
    animation_range = _curve_time_range(anim_curves)
    playback_range = _set_playback_range_from_curves(anim_curves)

    if _LAST_RESULT and _LAST_RESULT.source_uuid == source_uuid:
        _LAST_RESULT.animation_path = animation_path
        _LAST_RESULT.frame_range = animation_range
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
        "animation_range": animation_range,
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
        "reference_pose_path": state.get("reference_pose_path", ""),
        "reference_pose_compensation": state.get(
            "reference_pose_compensation",
            _disabled_reference_pose_compensation()),
        "dual_verification": validation,
        "preflight": state.get("preflight", payload.get("preflight", {})),
        "left_import_report": state.get("left_import_report", {}),
        "right_import_report": state.get("right_import_report", {}),
        "warnings": list(state.get("warnings", [])),
    })
    _update_output_file_stats(payload, {
        key: state.get("output_%s" % key, "")
        for key in ("scene", "cast", "smd", "fbx")
    })
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
        output_unit="m" if _LAST_RESULT.unit_conversion.get("output_unit") == "m" else "original",
    )
    _write_result_outputs(_LAST_RESULT, options, allocate=False)
    if _LAST_RESULT.output_errors:
        raise RuntimeError("Some animation outputs failed: %s" % _LAST_RESULT.output_errors)
    return _LAST_RESULT.output_scene or _LAST_RESULT.output_manifest


# ---------------------------------------------------------------------------
# UI helpers.
# ---------------------------------------------------------------------------

# Shared native Maya controls keep both editions and workflows consistent.
_UI_FEEDBACK_CONTROL = "viewmodelWeaponToolkitFeedback"
_UI_FIELD_LABELS = {}
_UI_WRAP_TEXTS = {}
_UI_SECTIONS = []
_UI_QT = None


def _ui_translate(text):
    return globals().get("_zh_cn_translate_ui_text", lambda value: value)(text)


def _ui_qt():
    global _UI_QT
    if _UI_QT is None:
        try:
            from PySide6 import QtCore, QtWidgets
            from shiboken6 import wrapInstance
        except ImportError:
            from PySide2 import QtCore, QtWidgets
            from shiboken2 import wrapInstance
        _UI_QT = (QtCore, QtWidgets, wrapInstance)
    return _UI_QT


def _ui_widget(control):
    _, QtWidgets, wrap = _ui_qt()
    pointer = (OpenMayaUI.MQtUtil.findControl(control) or
               OpenMayaUI.MQtUtil.findLayout(control) or
               OpenMayaUI.MQtUtil.findWindow(control))
    if not pointer:
        return None
    widget = wrap(int(pointer), QtWidgets.QWidget)
    interactive = (QtWidgets.QAbstractButton, QtWidgets.QLineEdit,
                   QtWidgets.QComboBox, QtWidgets.QAbstractItemView,
                   QtWidgets.QPlainTextEdit)
    if not isinstance(widget, interactive):
        children = [child for child in widget.findChildren(QtWidgets.QWidget)
                    if isinstance(child, interactive)]
        if len(children) == 1:
            return children[0]
    return widget


def _ui_text(label, bold=False):
    control = cmds.text(label=label, align="left", wordWrap=True, width=1,
                        height=22, font="boldLabelFont" if bold else "plainLabelFont")
    _UI_WRAP_TEXTS[control] = label
    return control


def _ui_reflow_labels():
    """Maya labels need an explicit height after their wrapping width changes."""
    QtCore, _, _ = _ui_qt()
    for control, label in _UI_WRAP_TEXTS.items():
        if not cmds.control(control, exists=True):
            continue
        widget = _ui_widget(control)
        if widget:
            width = max(120, widget.width())
            bounds = widget.fontMetrics().boundingRect(
                QtCore.QRect(0, 0, width, 10000),
                QtCore.Qt.TextWordWrap, _ui_translate(label))
            cmds.text(control, edit=True, height=max(22, bounds.height() + 4))
    # Maya caches column/frame heights when a wrapped label becomes shorter.
    for frame, column in _UI_SECTIONS:
        children = cmds.columnLayout(column, query=True, childArray=True) or []
        height = sum(cmds.control(child, query=True, height=True)
                     for child in children)
        height += max(0, len(children) - 1) * 8 + 2
        cmds.columnLayout(column, edit=True, height=height)
        if not cmds.frameLayout(frame, query=True, collapse=True):
            cmds.frameLayout(frame, edit=True, height=height + 45)


@contextmanager
def _ui_section(label, collapsed=False):
    parent = cmds.setParent(query=True)
    frame = cmds.frameLayout(label=label, collapsable=True, collapse=collapsed,
                             marginWidth=10, marginHeight=10,
                             expandCommand=lambda *_: _ui_reflow_labels())
    column = cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    _UI_SECTIONS.append((frame, column))
    try:
        yield
    finally:
        cmds.setParent(parent)


def _ui_path_row(label, field_name, value, callback=None):
    label_control = _ui_text(label)
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1,
                   columnWidth2=(1, 100), columnAttach2=("both", "both"),
                   columnOffset2=(0, 6))
    cmds.textField(field_name, text=value, height=32, width=1, annotation=label)
    browse = cmds.button(
        label="Browse...", height=32,
        annotation="Browse: " + label,
        command=callback or (lambda *_: _browse_cast(field_name)))
    cmds.setParent("..")
    _UI_FIELD_LABELS[field_name] = (label, label_control, browse)
    return browse


def _ui_joint_field(label, field_name, value):
    label_control = _ui_text(label)
    cmds.textField(field_name, text=value, height=32, annotation=label)
    _UI_FIELD_LABELS[field_name] = (label, label_control, None)


def _ui_actions(actions, primary=None):
    """One or two flexible columns; labels keep space at narrow widths."""
    for offset in range(0, len(actions), 2):
        row = cmds.formLayout(height=36)
        pair = actions[offset:offset + 2]
        controls = []
        for label, callback in pair:
            button = cmds.button(label=label, height=32, command=callback)
            controls.append(button)
            if label == primary:
                widget = _ui_widget(button)
                if widget:
                    widget.setProperty("primaryAction", True)
        if len(controls) == 1:
            cmds.formLayout(row, edit=True, attachForm=[
                (controls[0], "left", 0), (controls[0], "right", 0),
                (controls[0], "top", 0)])
        else:
            cmds.formLayout(row, edit=True,
                            attachForm=[(controls[0], "left", 0),
                                        (controls[1], "right", 0),
                                        (controls[0], "top", 0),
                                        (controls[1], "top", 0)],
                            attachPosition=[(controls[0], "right", 4, 50),
                                            (controls[1], "left", 4, 50)])
        cmds.setParent("..")


def _ui_output_options(saved, batch=False, dual=False):
    with _ui_section("Output files"):
        _ui_text("Output unit:")
        cmds.optionMenu(OUTPUT_UNIT_MENU, height=32)
        cmds.menuItem(label="Keep original")
        cmds.menuItem(label="Meters (input: ft)")
        cmds.optionMenu(OUTPUT_UNIT_MENU, edit=True, select=2 if saved.output_unit == "m" else 1)
        _ui_text("Meters converts an export copy: 1 ft = 0.3048 m. The working scene is unchanged.")
        _ui_path_row("Manifest/default:", OUTPUT_DIR_FIELD, saved.output_dir,
                     lambda *_: _browse_output_dir(
                         OUTPUT_DIR_FIELD, "manifest/default output"))
        _ui_text("Select at least one format. Blank folders use the default folder.")
        records = (
            (EXPORT_MA_CHECK, "Maya ASCII scene + animation (.ma)" if dual or batch
             else "Maya ASCII scene (.ma)", saved.save_scene,
             MA_OUTPUT_DIR_FIELD, saved.ma_output_dir),
            (EXPORT_CAST_CHECK, "Model + animation CAST (.cast)" if batch
             else "Static combined model Cast (.cast)", saved.export_cast,
             CAST_OUTPUT_DIR_FIELD, saved.cast_output_dir),
            (EXPORT_SMD_CHECK, "Skeleton animation only (.smd)" if batch
             else "Static Source model (.smd)", saved.export_smd,
             SMD_OUTPUT_DIR_FIELD, saved.smd_output_dir),
            (EXPORT_FBX_CHECK, "Skinned model + animation (.fbx)" if batch
             else "Static model with skinning (.fbx)", saved.export_fbx,
             FBX_OUTPUT_DIR_FIELD, saved.fbx_output_dir),
        )
        for check, label, enabled, field_name, value in records:
            cmds.checkBox(check, label=label, value=enabled, height=28)
            cmds.rowLayout(numberOfColumns=2, adjustableColumn=1,
                           columnWidth2=(1, 100),
                           columnAttach2=("both", "both"), columnOffset2=(0, 6))
            cmds.textField(field_name, text=value, height=32, width=1, enable=enabled,
                           annotation=label)
            browse = cmds.button(
                label="Browse...", height=32, enable=enabled,
                annotation="Browse: " + label,
                command=lambda *_, name=field_name, title=label:
                    _browse_output_dir(name, title))
            cmds.setParent("..")
            _UI_FIELD_LABELS[field_name] = (label, None, browse)

            def toggle(value, field=field_name, button=browse):
                cmds.textField(field, edit=True, enable=value)
                cmds.button(button, edit=True, enable=value)
            cmds.checkBox(check, edit=True, changeCommand=toggle)
        if batch:
            _ui_text("SMD stores skeletal animation only; use the JSON report for its frame rate.")
        else:
            _ui_text("CAST, SMD and FBX here export static models. Use Animation Batch for animated exports.")


def _ui_create_dialog(name, title, batch):
    for existing in (WINDOW_NAME, DUAL_WINDOW_NAME):
        if cmds.window(existing, exists=True):
            cmds.deleteUI(existing)
    _UI_FIELD_LABELS.clear()
    _UI_WRAP_TEXTS.clear()
    _UI_SECTIONS[:] = []
    win = cmds.window(name, title=title, widthHeight=(760, 820 if batch else 740),
                      sizeable=True, resizeToFitChildren=False)
    form = cmds.formLayout()
    scroll = cmds.scrollLayout(childResizable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=12,
                      columnOffset=("both", 12))
    return win, form, scroll


def _ui_footer(form, scroll):
    cmds.setParent(form)
    footer = cmds.columnLayout(adjustableColumn=True, rowSpacing=8,
                               columnOffset=("both", 12))
    cmds.formLayout(form, edit=True,
                    attachForm=[(scroll, "top", 0), (scroll, "left", 0),
                                (scroll, "right", 0), (footer, "left", 0),
                                (footer, "right", 0), (footer, "bottom", 12)],
                    attachControl=[(scroll, "bottom", 10, footer)])
    cmds.text(_UI_FEEDBACK_CONTROL, label="Ready", align="left",
              wordWrap=True, annotation="Operation status")
    return footer


def _ui_finish_dialog(win, first_field):
    """Add native accessibility metadata and keep keyboard focus in view."""
    cmds.showWindow(win)
    QtCore, QtWidgets, _ = _ui_qt()
    root = _ui_widget(win)
    if root:
        root.setMinimumSize(560, 360)
        font = root.font()
        font.setPointSizeF(max(10.0, font.pointSizeF()))
        root.setFont(font)
        # Maya assigns explicit fonts to controls; the window font alone does
        # not propagate to those controls.
        for widget in root.findChildren(QtWidgets.QWidget):
            control_font = widget.font()
            if control_font.pointSizeF() < 10.0:
                control_font.setPointSizeF(10.0)
                widget.setFont(control_font)
        root.setStyleSheet(
            "QPushButton:focus, QLineEdit:focus, QComboBox:focus, "
            "QListView:focus, QPlainTextEdit:focus {"
            "border: 2px solid #80c8ff; } "
            "QPushButton[primaryAction=\"true\"] { font-weight: 600; }")
        for field, (label, label_control, browse) in _UI_FIELD_LABELS.items():
            widget = _ui_widget(field)
            if widget:
                widget.setAccessibleName(_ui_translate(label))
                widget.setAccessibleDescription(_ui_translate(label))
                if label_control:
                    text_widget = _ui_widget(label_control)
                    if isinstance(text_widget, QtWidgets.QLabel):
                        text_widget.setBuddy(widget)
            if browse:
                button = _ui_widget(browse)
                if button:
                    button.setFocusPolicy(QtCore.Qt.StrongFocus)
                    button.setAccessibleName(
                        _ui_translate("Browse...") + " " + _ui_translate(label))
        for widget in root.findChildren(QtWidgets.QAbstractButton):
            widget.setFocusPolicy(QtCore.Qt.StrongFocus)
            widget.setMinimumHeight(28)
        for widget in root.findChildren(QtWidgets.QWidget):
            if not widget.accessibleName() and widget.toolTip():
                widget.setAccessibleName(widget.toolTip())
        screen = root.screen() if hasattr(root, "screen") else None
        if screen:
            available = screen.availableGeometry()
            root.resize(min(root.width(), available.width() - 32),
                        min(root.height(), available.height() - 64))

        class KeepFocusVisible(QtCore.QObject):
            def __init__(self, parent):
                super(KeepFocusVisible, self).__init__(parent)
                self.timer = QtCore.QTimer(self)
                self.timer.setSingleShot(True)
                self.timer.timeout.connect(_ui_reflow_labels)

            def eventFilter(self, watched, event):
                if watched is root and event.type() in (
                        QtCore.QEvent.Resize, QtCore.QEvent.FontChange):
                    self.timer.start(0)
                if event.type() == QtCore.QEvent.FocusIn:
                    parent = watched.parentWidget()
                    while parent and parent is not root:
                        if isinstance(parent, QtWidgets.QScrollArea):
                            center = watched.mapTo(parent.widget(),
                                                   watched.rect().center())
                            parent.ensureVisible(
                                center.x(), center.y(),
                                watched.width() // 2 + 8,
                                watched.height() // 2 + 8)
                            break
                        parent = parent.parentWidget()
                return False

        observer = KeepFocusVisible(root)
        root._vwt_focus_observer = observer
        root.installEventFilter(observer)
        for widget in root.findChildren(QtWidgets.QWidget):
            widget.installEventFilter(observer)
        QtWidgets.QApplication.processEvents()
        _ui_reflow_labels()
    cmds.setFocus(first_field)


def _ui_require_cast(field, label):
    try:
        return _validate_cast_path(_field_text(field), label)
    except Exception:
        cmds.setFocus(field)
        raise


def _show_error(title, exc):
    log("ERROR: %s" % exc)
    log(traceback.format_exc())
    if cmds.control(_UI_FEEDBACK_CONTROL, exists=True):
        cmds.text(_UI_FEEDBACK_CONTROL, edit=True, label="Failed:\n%s" % exc)
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
        output_unit=_output_unit_ui_value(saved.output_unit),
        force_new_scene=force_new_scene,
    )


def _output_unit_ui_value(default="original"):
    if cmds.optionMenu(OUTPUT_UNIT_MENU, exists=True):
        return "m" if cmds.optionMenu(OUTPUT_UNIT_MENU, query=True, select=True) == 2 else "original"
    return default


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
    viewhands = _ui_require_cast(VIEWHANDS_FIELD, "Viewhands")
    weapon = _field_text(WEAPON_FIELD)
    if require_weapon:
        weapon = _ui_require_cast(WEAPON_FIELD, "Weapon")
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
        output_unit=_output_unit_ui_value(saved.output_unit),
        animation_mode=_dual_mode_ui_value(),
        shared_hands_source="right",
        reference_pose_path=_field_text(DUAL_REFERENCE_POSE_FIELD, ""),
        force_new_scene=force_new_scene,
    )


def _dual_dialog_paths():
    return tuple(_ui_require_cast(field, label) for field, label in (
        (DUAL_VIEWHANDS_FIELD, "Viewhands"),
        (DUAL_WEAPON_FIELD, "Weapon"),
        (DUAL_LEFT_ANIMATION_FIELD, "Left animation"),
        (DUAL_RIGHT_ANIMATION_FIELD, "Right animation"),
    ))


def _reference_pose_ui_summary(reference_pose):
    if not reference_pose.get("enabled"):
        return "disabled"
    sides = reference_pose.get("sides", {})
    return "left %s; right %s" % (
        sides.get("left", {}).get("translation_offset", []),
        sides.get("right", {}).get("translation_offset", []),
    )


def _save_dual_dialog_settings(paths, options):
    viewhands, weapon, left_animation, right_animation = paths
    _save_string_option(DUAL_VIEWHANDS_OPTVAR, viewhands)
    _save_string_option(DUAL_WEAPON_OPTVAR, weapon)
    _save_string_option(DUAL_LEFT_ANIMATION_OPTVAR, left_animation)
    _save_string_option(DUAL_RIGHT_ANIMATION_OPTVAR, right_animation)
    _save_string_option(
        DUAL_REFERENCE_POSE_OPTVAR, options.reference_pose_path)
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
            reference_pose_path=options.reference_pose_path,
        )
        _save_dual_dialog_settings(paths, options)
        cmds.confirmDialog(
            title="%s - Dual Preflight Passed" % PRODUCT_SHORT_NAME,
            message=(
                "Preflight passed without changing the scene.\n\n"
                "Mode: %s\nFramerate: %s fps\n"
                "Left frames: %s\nRight frames: %s\n"
                "Reference compensation: %s\n"
                "Differing shared tracks: %d\nOrphan nodes: %s"
                % (
                    report["animation_mode"],
                    report["left_animation"]["framerate"],
                    report["left_animation"]["frame_range"],
                    report["right_animation"]["frame_range"],
                    _reference_pose_ui_summary(
                        report["reference_pose_compensation"]),
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
                "Mode: %s\nLeft frames: %s\nRight frames: %s\n"
                "Reference compensation: %s\n\n"
                "MA: %s\nCast: %s\nSMD: %s\nFBX: %s\nManifest: %s"
                % (
                    _short_name(result.source_node),
                    _short_name(result.target_node),
                    _short_name(result.right_source_node),
                    _short_name(result.right_target_node),
                    result.animation_mode,
                    result.left_clip_range,
                    result.right_clip_range,
                    _reference_pose_ui_summary(
                        result.reference_pose_compensation),
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


def _add_animation_queue_ui(dual=False, form=None, scroll=None):
    """Add a queue to a builder; paths remain visible in their explicit order."""
    jobs = []
    running = {"cancel": False}
    cmds.separator(height=8, style="in")
    cmds.text(label="Batch skinning: DQS (Dual Quaternion).", align="left")
    cmds.text(label=("Animation pairs (left | right):" if dual else
                     "Animation queue:"), align="left")
    def show_selected_paths(*_):
        selected = cmds.textScrollList(BATCH_ANIMATION_LIST, query=True,
                                       selectIndexedItem=True) or []
        cmds.scrollField(details, edit=True, text="\n\n".join(
            "\n".join(jobs[index - 1]) for index in selected))

    cmds.textScrollList(BATCH_ANIMATION_LIST, height=140,
                        annotation="Animation queue:",
                        allowMultiSelection=True, selectCommand=show_selected_paths)
    empty_hint = _ui_text("No animations queued. Add files to begin.")
    cmds.text(label="Selected paths (left, then right):" if dual else "Selected paths:", align="left")
    details = cmds.scrollField(editable=False, wordWrap=True, height=55,
                               annotation="Selected paths:")

    def redraw():
        cmds.textScrollList(BATCH_ANIMATION_LIST, edit=True, removeAll=True)
        for index, job in enumerate(jobs):
            cmds.textScrollList(BATCH_ANIMATION_LIST, edit=True,
                                append="%d. %s" % (index + 1, " | ".join(os.path.basename(p) for p in job)))
        cmds.scrollField(details, edit=True, text="")
        cmds.text(empty_hint, edit=True, manage=not bool(jobs))
        cmds.button(start_button, edit=True, enable=bool(jobs))
        cmds.text(BATCH_ANIMATION_STATUS, edit=True,
                  label="Ready" if jobs else "No animations queued. Add files to begin.")

    def add_current_pair(*_):
        try:
            pairs = jobs + [(_field_text(DUAL_LEFT_ANIMATION_FIELD),
                             _field_text(DUAL_RIGHT_ANIMATION_FIELD))]
            jobs[:] = _animation_jobs(pairs, dual=True)
            redraw()
        except Exception as exc:
            _show_error(PRODUCT_SHORT_NAME, exc)

    def add_files(*_):
        try:
            left = cmds.fileDialog2(
                fileMode=4, fileFilter="Cast (*.cast)", dialogStyle=2,
                caption="Select left animations" if dual else "Select animations") or []
            if not left:
                return
            if dual:
                right = cmds.fileDialog2(
                    fileMode=4, fileFilter="Cast (*.cast)", dialogStyle=2,
                    caption="Select right animations (same order)") or []
                if not right:
                    return
                if len(left) != len(right):
                    raise RuntimeError("Left and right animation counts must match")
                jobs[:] = _animation_jobs(jobs + list(zip(left, right)), dual=True)
            else:
                jobs[:] = _animation_jobs([job[0] for job in jobs] + left)
            redraw()
        except Exception as exc:
            _show_error(PRODUCT_SHORT_NAME, exc)

    def remove_selected(*_):
        for index in sorted(cmds.textScrollList(
                BATCH_ANIMATION_LIST, query=True, selectIndexedItem=True) or [],
                reverse=True):
            del jobs[index - 1]
        redraw()

    cmds.textScrollList(BATCH_ANIMATION_LIST, edit=True,
                        deleteKeyCommand=remove_selected)
    queue_controls = cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
    actions = [("Add Current Pair", add_current_pair)] if dual else []
    actions.extend([
        ("Add Animation Pairs..." if dual else "Add Animations...", add_files),
        ("Remove Selected", remove_selected),
        ("Clear Queue", lambda *_: (jobs.clear(), redraw())),
    ])
    _ui_actions(actions)
    cmds.setParent("..")
    if dual:
        cmds.text(label="Check every left/right pair in the queue before exporting.", align="left")
    if form is not None:
        _ui_footer(form, scroll)
    cmds.text(BATCH_ANIMATION_STATUS, label="No animations queued. Add files to begin.",
              align="left", wordWrap=True)
    cmds.progressBar(BATCH_ANIMATION_PROGRESS, maxValue=1, progress=0, height=16)

    def update_progress(index, total, job):
        if not cmds.control(BATCH_ANIMATION_STATUS, exists=True):
            return False
        cmds.progressBar(BATCH_ANIMATION_PROGRESS, edit=True,
                         maxValue=total, progress=index)
        cmds.text(BATCH_ANIMATION_STATUS, edit=True,
                  label="%d / %d: %s" % (index + 1, total, os.path.basename(job[0])))
        cmds.refresh()
        # Process the Cancel button while respecting the current clip boundary.
        try:
            from PySide6.QtWidgets import QApplication
        except ImportError:
            from PySide2.QtWidgets import QApplication
        QApplication.processEvents()
        return not running["cancel"] and cmds.control(BATCH_ANIMATION_STATUS, exists=True)

    def run_queue(*_):
        try:
            options = _dual_dialog_options() if dual else _dialog_options()
            validate_output_options(options)
            queue = _animation_jobs(jobs if dual else [job[0] for job in jobs], dual)
            hands = _ui_require_cast(
                DUAL_VIEWHANDS_FIELD if dual else VIEWHANDS_FIELD, "Viewhands")
            weapon = _ui_require_cast(
                DUAL_WEAPON_FIELD if dual else WEAPON_FIELD, "Weapon")
            if not _confirm_scene_reset():
                return
            options.force_new_scene = True
            if dual:
                _save_dual_dialog_settings((hands, weapon) + queue[0], options)
            else:
                save_options(hands, options)
            running["cancel"] = False
            cmds.button(start_button, edit=True, enable=False)
            cmds.button(cancel_button, edit=True, enable=True)
            cmds.columnLayout(queue_controls, edit=True, enable=False)
            runner = batch_export_dual_animations if dual else batch_export_animations
            summary = runner(hands, weapon, queue if dual else [j[0] for j in queue],
                             options, progress=update_progress)
            log("Batch report: %s" % summary["summary_path"])
            if not cmds.control(BATCH_ANIMATION_STATUS, exists=True):
                return
            counts = {status: sum(item["status"] == status for item in summary["items"])
                      for status in ("ok", "partial", "failed")}
            cmds.progressBar(BATCH_ANIMATION_PROGRESS, edit=True,
                             progress=summary["completed"])
            status = "Cancelled" if summary["cancelled"] else "Finished"
            cmds.text(BATCH_ANIMATION_STATUS, edit=True, label=status)
            cmds.confirmDialog(title=PRODUCT_SHORT_NAME,
                               message=("%s\nOK: %d\nPartial: %d\nFailed: %d\nReport: %s" % (
                                   status, counts["ok"], counts["partial"], counts["failed"],
                                   summary["summary_path"])), button=["OK"])
        except Exception as exc:
            if cmds.control(BATCH_ANIMATION_STATUS, exists=True):
                cmds.text(BATCH_ANIMATION_STATUS, edit=True, label="Failed")
            _show_error(PRODUCT_SHORT_NAME, exc)
        finally:
            if cmds.button(start_button, exists=True):
                cmds.button(start_button, edit=True, enable=bool(jobs))
                cmds.button(cancel_button, edit=True, enable=False)
                cmds.columnLayout(queue_controls, edit=True, enable=True)

    action_row = cmds.formLayout(height=36)
    start_button = cmds.button(label="Batch Export Animations", height=32,
                               enable=False, command=run_queue)
    cancel_button = cmds.button(label="Cancel After Current Item", height=32, enable=False,
                                command=lambda *_: running.update(cancel=True))
    cmds.formLayout(action_row, edit=True,
                    attachForm=[(start_button, "left", 0), (start_button, "top", 0),
                                (cancel_button, "right", 0), (cancel_button, "top", 0)],
                    attachPosition=[(start_button, "right", 4, 50),
                                    (cancel_button, "left", 4, 50)])
    _ui_widget(start_button).setProperty("primaryAction", True)
    cmds.setParent("..")


def _open_batch_from_builder(dual=False):
    if dual:
        _save_dual_dialog_settings((
            _field_text(DUAL_VIEWHANDS_FIELD), _field_text(DUAL_WEAPON_FIELD),
            _field_text(DUAL_LEFT_ANIMATION_FIELD), _field_text(DUAL_RIGHT_ANIMATION_FIELD)),
            _dual_dialog_options())
        show_dual_dialog(batch=True)
    else:
        weapon = _field_text(WEAPON_FIELD)
        save_options(_field_text(VIEWHANDS_FIELD), _dialog_options())
        show_dialog(batch=True, weapon_path=weapon)


def show_dual_dialog(batch=False):
    """Show source files, mapping, output formats, and explicit dual actions."""
    saved = load_saved_options()
    win, form, scroll = _ui_create_dialog(
        DUAL_WINDOW_NAME, "%s v%s - %s" % (
            PRODUCT_SHORT_NAME, VERSION,
            "Dual Animation Batch" if batch else "Dual-Wield Builder"), batch)
    with _ui_section("Source files"):
        _ui_text("Duplicates one weapon onto the left and right hand tags.")
        for label, field, option, default in (
                ("Viewhands:", DUAL_VIEWHANDS_FIELD, DUAL_VIEWHANDS_OPTVAR,
                 load_viewhands_path()),
                ("Weapon:", DUAL_WEAPON_FIELD, DUAL_WEAPON_OPTVAR, ""),
                ("Left animation:", DUAL_LEFT_ANIMATION_FIELD,
                 DUAL_LEFT_ANIMATION_OPTVAR, ""),
                ("Right animation:", DUAL_RIGHT_ANIMATION_FIELD,
                 DUAL_RIGHT_ANIMATION_OPTVAR, "")):
            _ui_path_row(label, field, _load_string_option(option, default))
        _ui_text("Animation mode:")
        cmds.optionMenu(DUAL_MODE_MENU, height=32, annotation="Animation mode:")
        cmds.menuItem(label="simultaneous")
        cmds.menuItem(label="sequential")
        saved_mode = _load_string_option(DUAL_MODE_OPTVAR, "simultaneous")
        if saved_mode in DUAL_ANIMATION_MODES:
            cmds.optionMenu(DUAL_MODE_MENU, edit=True, value=saved_mode)
        _ui_text("Simultaneous mode splits hand branches and uses the right "
                 "animation for shared torso/root tracks.")
    with _ui_section("Joint mapping and reference pose", collapsed=True):
        _ui_joint_field("Weapon root:", SOURCE_JOINT_FIELD, DEFAULT_SOURCE_JOINT)
        _ui_joint_field("Left target:", DUAL_LEFT_TARGET_FIELD, DEFAULT_LEFT_TARGET_JOINT)
        _ui_joint_field("Right target:", DUAL_RIGHT_TARGET_FIELD, DEFAULT_RIGHT_TARGET_JOINT)
        _ui_path_row("Reference pose (optional):", DUAL_REFERENCE_POSE_FIELD,
                     _load_string_option(DUAL_REFERENCE_POSE_OPTVAR, ""))
        _ui_text("Reference pose compensation shifts relative/additive weapon-tag "
                 "translation tracks from the selected reference viewhands rest pose.")
    _ui_output_options(saved, batch=batch, dual=True)
    if batch:
        _add_animation_queue_ui(dual=True, form=form, scroll=scroll)
    else:
        with _ui_section("Current scene tools", collapsed=True):
            _ui_actions([
                ("Validate Dual", lambda *_: _validate_dual_ui()),
                ("Save Current Result", lambda *_: _save_current_ui()),
                ("Replace Left Clip...", lambda *_: _replace_dual_animation_ui("left")),
                ("Replace Right Clip...", lambda *_: _replace_dual_animation_ui("right")),
                ("Open Output Folders", lambda *_: _open_output_dir_ui()),
                ("Dual Animation Batch...", lambda *_: _open_batch_from_builder(dual=True)),
            ])
        _ui_footer(form, scroll)
        _ui_actions([
            ("Preflight Dual", lambda *_: _preflight_dual_from_dialog()),
            ("Build + Import Both", lambda *_: _run_dual_from_dialog()),
            ("Close", lambda *_: cmds.deleteUI(DUAL_WINDOW_NAME)),
        ], primary="Build + Import Both")
    _ui_finish_dialog(win, DUAL_VIEWHANDS_FIELD)


def show_dialog(batch=False, weapon_path=""):
    """Show the single-weapon workflow with keyboard-accessible shared controls."""
    saved = load_saved_options()
    win, form, scroll = _ui_create_dialog(
        WINDOW_NAME, "%s v%s - %s" % (
            PRODUCT_SHORT_NAME, VERSION,
            "Single Animation Batch" if batch else "Single Weapon"), batch)
    with _ui_section("Source files"):
        _ui_text("Single mode - weapon:j_gun -> viewhands:tag_weapon. "
                 "Use Dual-Wield Builder for Akimbo scenes.")
        _ui_path_row("Viewhands:", VIEWHANDS_FIELD, load_viewhands_path())
        _ui_path_row("Weapon:", WEAPON_FIELD, weapon_path)
    with _ui_section("Joint mapping", collapsed=True):
        _ui_joint_field("Weapon joint:", SOURCE_JOINT_FIELD, saved.source_joint)
        _ui_joint_field("Viewhands tag:", TARGET_JOINT_FIELD, saved.target_joint)
        cmds.checkBox(
            PROTECT_TRANSLATION_CHECK,
            label="Protect weapon joint translation when importing animation",
            value=True if batch else saved.protect_translation,
            enable=not batch, height=28)
    _ui_output_options(saved, batch=batch)
    if batch:
        _add_animation_queue_ui(form=form, scroll=scroll)
    else:
        with _ui_section("Current scene tools", collapsed=True):
            _ui_actions([
                ("Import Animation Safely...", lambda *_: import_animation()),
                ("Validate Current", lambda *_: _validate_current_ui()),
                ("Select Attachment", lambda *_: _select_attachment_ui()),
                ("Save Current Result", lambda *_: _save_current_ui()),
                ("Open Output Folders", lambda *_: _open_output_dir_ui()),
                ("Batch Weapons...", lambda *_: _batch_from_dialog()),
                ("Single Animation Batch...", lambda *_: _open_batch_from_builder()),
            ])
        _ui_footer(form, scroll)
        _ui_actions([
            ("Preflight", lambda *_: _preflight_from_dialog()),
            ("Attach && Export", lambda *_: _run_from_dialog()),
            ("Close", lambda *_: cmds.deleteUI(WINDOW_NAME)),
        ], primary="Attach && Export")
    _ui_finish_dialog(win, VIEWHANDS_FIELD)


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


def _about_message():
    """Return the compact, user-facing product and capability summary."""
    return (
        "%s v%s\n"
        "CAST viewmodel assembly, safe animation import, and batch export "
        "for Maya.\n\n"
        "WORKFLOWS\n"
        "- Single weapon: attach weapon:j_gun to viewhands:tag_weapon;\n"
        "  includes preflight and validation.\n"
        "- Dual wield: duplicate one weapon onto tag_weapon_left/right;\n"
        "  compose left/right clips in simultaneous or sequential mode.\n"
        "- Optional reference-pose compensation corrects compatible "
        "weapon-tag\n"
        "  offsets.\n"
        "- Pure-animation CAST import and drag/drop safely avoid "
        "duplicate-joint\n"
        "  conflicts.\n\n"
        "ANIMATION & EXPORT\n"
        "- Queue multiple single clips or explicit left/right dual pairs.\n"
        "- Builders: animated MA scenes plus optional static CAST/SMD/FBX\n"
        "  model outputs.\n"
        "- Animation batches: animated MA/CAST/FBX and skeletal-animation "
        "SMD;\n"
        "  all use DQS skinning.\n"
        "- Choose formats and folders independently. Versioned names avoid\n"
        "  overwrites; JSON reports record results.\n\n"
        "COMPATIBILITY\n"
        "- Expected: Maya 2022+ in Python 3 mode.\n"
        "  Verified: Maya 2025 for Windows.\n"
        "- Uses an already loaded compatible Cast translator, or the "
        "adjacent\n"
        "  patched CAST 2.00 fallback.\n\n"
        "DUAL-WIELD SCOPE\n"
        "- Duplicates the same weapon; does not merge two different weapon\n"
        "  skeletons.\n\n"
        "Source and releases:\n"
        "https://github.com/ez4cywa/cod-viewmodel-toolkit"
        % (PRODUCT_NAME, VERSION)
    )


def _show_about():
    cmds.confirmDialog(
        title="About %s" % PRODUCT_SHORT_NAME,
        message=_about_message(),
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
    cmds.menuItem(label="Single Animation Batch...",
                  command=lambda *_: show_dialog(batch=True))
    cmds.menuItem(label="Dual Animation Batch...",
                  command=lambda *_: show_dual_dialog(batch=True))
    cmds.menuItem(divider=True)
    cmds.menuItem(label="Import Animation Safely...",
                  command=lambda *_: import_animation())
    cmds.menuItem(
        label="Auto-Safe Dropped CAST Animations",
        annotation=("Safely route pure animation CAST files dropped onto "
                    "a CoD Viewmodel Toolkit scene."),
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
                message="Saved CoD Viewmodel Toolkit settings cleared.",
                button=["OK"],
                defaultButton="OK",
            ),
        ),
    )
    cmds.menuItem(divider=True)
    cmds.menuItem(label="About", command=lambda *_: _show_about())


def initializePlugin(m_object):
    global _CAST_TRANSLATOR_FALLBACK_REGISTERED, _TOOLKIT_PLUGIN_PATH
    plugin = OpenMayaMPx.MFnPlugin(m_object, "OpenCode", VERSION, "Any")
    try:
        _TOOLKIT_PLUGIN_PATH = os.path.normpath(os.path.abspath(
            cmds.pluginInfo(plugin.name(), query=True, path=True)))
    except Exception:
        _TOOLKIT_PLUGIN_PATH = globals().get("__file__", "")
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
