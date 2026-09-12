"""Legacy loader for CoD Viewmodel Toolkit 3.4.1.

Existing Maya installations may continue to auto-load ``attach_gun.py``.
New installations should load ``viewmodel_weapon_toolkit.py`` instead.
"""

import importlib.util
import os
import sys


_LOADER_FILE = globals().get("__file__") or sys._getframe().f_code.co_filename
_PRIMARY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(_LOADER_FILE)),
    "viewmodel_weapon_toolkit.py",
)

try:
    import viewmodel_weapon_toolkit as _implementation
    if os.path.normcase(os.path.abspath(_implementation.__file__)) != \
            os.path.normcase(_PRIMARY_PATH):
        raise ImportError("A different toolkit module is already imported")
except ImportError:
    _spec = importlib.util.spec_from_file_location(
        "viewmodel_weapon_toolkit_legacy_core", _PRIMARY_PATH)
    if _spec is None or _spec.loader is None:
        raise ImportError("Unable to load %s" % _PRIMARY_PATH)
    _implementation = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _implementation
    _spec.loader.exec_module(_implementation)


for _name in dir(_implementation):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_implementation, _name)


def __getattr__(name):
    return getattr(_implementation, name)


def initializePlugin(m_object):
    """Load the renamed primary plugin without owning runtime commands."""
    plugin = OpenMayaMPx.MFnPlugin(
        m_object, "EZ4 Compatibility Loader", VERSION, "Any")
    if not cmds.pluginInfo(
            PLUGIN_BASENAME, query=True, loaded=True):
        cmds.loadPlugin(_PRIMARY_PATH, quiet=True)
    try:
        cmds.pluginInfo(plugin.name(), edit=True, autoload=True)
        cmds.pluginInfo(savePluginPrefs=True)
    except RuntimeError as exc:
        log("could not persist legacy loader auto-load preference: %s" % exc)


def uninitializePlugin(m_object):
    """Leave the primary plugin running when the compatibility loader exits."""
    del m_object
