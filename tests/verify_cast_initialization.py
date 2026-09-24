"""Mayapy: real initialization entrypoint unwinds failed CAST dependencies.

Plugin registration is replaced with event-recording doubles; no real Maya
commands, translators, user preferences or UI objects are changed by this test.
"""

import importlib.util
from pathlib import Path
import sys
from unittest.mock import patch

import maya.cmds as cmds
import maya.standalone

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plug-ins/viewmodel_weapon_toolkit.py"
spec = importlib.util.spec_from_file_location("cast_initialization_probe", str(PLUGIN))
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


class Registration:
    def __init__(self, events):
        self.events = events
        self.commands = set()

    def name(self):
        return "cast_initialization_probe"

    def registerCommand(self, name, creator):
        self.events.append(("register_command", name))
        self.commands.add(name)

    def deregisterCommand(self, name):
        self.events.append(("deregister_command", name))
        self.commands.remove(name)


class Backend:
    def __init__(self, events, failure, cleanup_failure=False):
        self.events = events
        self.failure = failure
        self.cleanup_failure = cleanup_failure

    def register(self, plugin):
        self.events.append(("register_translator", plugin.name()))
        raise self.failure

    def unregister(self, plugin):
        self.events.append(("unregister_translator", plugin.name()))
        if self.cleanup_failure:
            raise RuntimeError("fixture translator cleanup failure")


def verify(case):
    events = []
    plugin = Registration(events)
    failure = RuntimeError("fixture " + case)
    backend = Backend(events, failure, cleanup_failure=(case == "cleanup_failure"))

    def resolve_backend():
        events.append(("resolve_backend", None))
        if case == "missing_backend":
            raise failure
        return backend

    def remove_callback():
        events.append(("remove_callback", None))
        if case == "cleanup_failure":
            raise RuntimeError("fixture callback cleanup failure")

    with patch.object(core.OpenMayaMPx, "MFnPlugin", return_value=plugin), \
            patch.object(core, "_cast_backend", side_effect=resolve_backend), \
            patch.object(core, "_remove_cast_drop_callback", side_effect=remove_callback), \
            patch.object(core.cmds, "pluginInfo", return_value=str(PLUGIN)), \
            patch.object(core.cmds, "about", return_value=True):
        try:
            core.initializePlugin(object())
        except RuntimeError as caught:
            assert caught is failure, "Cleanup replaced the original error"
        else:
            raise AssertionError("Expected initialization failure: " + case)

    assert not plugin.commands, (case, events)
    assert events.count(("resolve_backend", None)) == 1, (case, events)
    if case == "missing_backend":
        assert events == [("resolve_backend", None)], events
    else:
        assert ("unregister_translator", plugin.name()) in events, events
        assert ("remove_callback", None) in events, events
        for name in (core.COMMAND_NAME, core.LEGACY_COMMAND_NAME):
            assert ("deregister_command", name) in events, events
    print("CAST_INITIALIZATION_%s_OK" % case.upper())


if __name__ == "__main__":
    try:
        for case in ("missing_backend", "register_failure", "cleanup_failure"):
            verify(case)
    finally:
        maya.standalone.uninitialize()
