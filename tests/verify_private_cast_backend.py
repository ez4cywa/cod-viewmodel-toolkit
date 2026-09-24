"""Mayapy: private CAST identity, options, translator lifecycle and coexistence.

Uses temporary translator plugins and a synthetic mesh, not game assets or
installed plugins. No preferences, upstream cfg files or user scenes are saved.
"""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch

import maya.cmds as cmds
import maya.standalone

if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "plug-ins/cod_viewmodel_cast_backend.py"
CORE = ROOT / "plug-ins/viewmodel_weapon_toolkit.py"


def load_helper(name):
    spec = importlib.util.spec_from_file_location(name, str(HELPER))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_fixture(serializer, path):
    document = serializer.Cast()
    model = document.CreateRoot().CreateModel()
    model.SetName("private_fixture")
    mesh = model.CreateMesh()
    mesh.SetName("fixture_mesh")
    mesh.SetVertexPositionBuffer([(0, 0, 0), (1, 0, 0), (0, 1, 0)])
    mesh.SetVertexNormalBuffer([(0, 0, 1)] * 3)
    mesh.SetFaceBuffer([0, 1, 2])
    mesh.SetUVLayerCount(1)
    mesh.SetVertexUVLayerBuffer(0, [(0, 0), (1, 0), (0, 1)])
    document.save(str(path))


EXTERNAL_PLUGIN = '''import maya.OpenMayaMPx as mpx
class Translator(mpx.MPxFileTranslator):
    def haveReadMethod(self):
        return True
    def identifyFile(self, *args):
        return mpx.MPxFileTranslator.kNotMyFileType
    def defaultExtension(self):
        return "cast"
def create():
    return mpx.asMPxPtr(Translator())
def initializePlugin(obj):
    mpx.MFnPlugin(obj, "CAST isolation test", "1", "Any").registerFileTranslator("Cast", None, create)
def uninitializePlugin(obj):
    mpx.MFnPlugin(obj).deregisterFileTranslator("Cast")
'''


def private_plugin():
    return '''import importlib.util
import maya.OpenMayaMPx as mpx
spec = importlib.util.spec_from_file_location("backend_plugin_probe_helper", %r)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
backend = helper.get_backend(%r)
def initializePlugin(obj):
    backend.register(mpx.MFnPlugin(obj, "CAST isolation test", "1", "Any"))
def uninitializePlugin(obj):
    backend.unregister(mpx.MFnPlugin(obj))
''' % (str(HELPER), str(CORE))


def main():
    previous = {name: sys.modules.get(name) for name in ("cast", "castplugin")}
    sentinels = {name: types.ModuleType(name) for name in previous}
    sys.modules.update(sentinels)
    try:
        helper = load_helper("backend_probe_helper")
        previous_search_path = list(sys.path)
        backend = helper.get_backend(str(CORE))
        assert sys.path == previous_search_path, "Backend changed Python import resolution"
        alias = load_helper("backend_alias_probe_helper")
        assert alias.get_backend(str(CORE)) is backend
        for name in ("viewmodel_weapon_toolkit_zh_CN.py", "attach_gun.py"):
            assert alias.get_backend(str(CORE.with_name(name))) is backend
        assert backend.module.Cast is backend.serializer.Cast
        assert backend.module.__name__ == "_cod_viewmodel_cast.castplugin"
        assert backend.serializer.__name__ == "_cod_viewmodel_cast.cast"
        assert all(sys.modules[name] is value for name, value in sentinels.items())
        info = backend.info()
        assert info["version"] == "2.01", info
        assert info["translator"] == "CoDToolkitCast", info
        assert all(info["capabilities"].values()), info
        assert len(info["module_sha256"]) == 64
        print("PRIVATE_CAST_IDENTITY_OK " + json.dumps(info, sort_keys=True))

        original_settings = dict(backend.module.sceneSettings)
        original_runtime = dict(backend.module.runtimeSettings)
        try:
            with backend.options({"importIK": False}, {"retargetScale": 2.0}):
                assert not backend.module.sceneSettings["importIK"]
                assert backend.module.runtimeSettings["retargetScale"] == 2.0
                with backend.options({"importIK": True}, {"retargetScale": 3.0}):
                    assert backend.module.sceneSettings["importIK"]
                    assert backend.module.runtimeSettings["retargetScale"] == 3.0
                assert not backend.module.sceneSettings["importIK"]
                assert backend.module.runtimeSettings["retargetScale"] == 2.0
                raise RuntimeError("fixture operation failure")
        except RuntimeError as exc:
            assert str(exc) == "fixture operation failure"
        assert backend.module.sceneSettings == original_settings
        assert backend.module.runtimeSettings == original_runtime
        try:
            with backend.options({"notASetting": True}):
                raise AssertionError("Unknown option accepted")
        except ValueError:
            pass
        assert backend.module.sceneSettings == original_settings
        print("PRIVATE_CAST_OPTIONS_OK")

        with tempfile.TemporaryDirectory(prefix="private_cast_backend_") as temporary:
            folder = Path(temporary)
            document_path = folder / "fixture.cast"
            try:
                helper.get_backend("relative/toolkit.py")
            except ValueError:
                pass
            else:
                raise AssertionError("Relative toolkit path accepted")
            try:
                helper.get_backend(str(folder / "missing/plug-ins/toolkit.py"))
            except RuntimeError as exc:
                assert "backend is missing" in str(exc)
            else:
                raise AssertionError("Missing private backend borrowed an external plugin")
            different = folder / "different_install/plug-ins/cod_viewmodel_cast"
            different.mkdir(parents=True)
            for name in ("cast.py", "castplugin.py"):
                (different / name).write_text("# Not this installation\n", encoding="utf-8")
            try:
                helper.get_backend(str(different.parent / "toolkit.py"))
            except RuntimeError as exc:
                assert "different toolkit CAST backend" in str(exc)
            else:
                raise AssertionError("Two installation paths silently shared a backend")
            assert helper.get_backend(str(CORE)) is backend
            print("PRIVATE_CAST_SOURCE_GUARDS_OK")
            make_fixture(backend.serializer, document_path)
            with patch.object(backend.serializer.Cast, "load", wraps=backend.serializer.Cast.load) as load:
                with backend.read_session():
                    document = backend.read(document_path)
                    with backend.read_session():
                        assert backend.read(document_path) is document
                assert load.call_count == 1
                assert backend.module._castReadCache is None
                assert backend.read(document_path) is not document
                assert load.call_count == 2
            print("PRIVATE_CAST_READ_SESSION_OK")

            external_path = folder / "external_cast_probe.py"
            private_path = folder / "private_cast_probe.py"
            external_path.write_text(EXTERNAL_PLUGIN, encoding="utf-8")
            private_path.write_text(private_plugin(), encoding="utf-8")
            for external_first in (True, False):
                sequence = (external_path, private_path) if external_first else (private_path, external_path)
                loaded = {}
                for path in sequence:
                    loaded[path] = cmds.loadPlugin(str(path), quiet=True)[0]
                try:
                    assert backend.registered
                    assert cmds.pluginInfo(str(external_path), query=True, translator=True) == ["Cast"]
                    assert cmds.pluginInfo(str(private_path), query=True, translator=True) == [backend.translator_name]
                    other_owner = types.SimpleNamespace(name=lambda: "another_toolkit")
                    backend.unregister(other_owner)
                    assert backend.registered
                    try:
                        backend.register(other_owner)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("Translator ownership was transferred")
                    cmds.file(new=True, force=True)
                    before = set(cmds.ls(long=True))
                    imported = cmds.file(str(document_path), i=True, type=backend.translator_name,
                                         namespace="private_probe", returnNewNodes=True)
                    assert imported, "returnNewNodes was lost"
                    assert set(imported) == set(cmds.ls(long=True)) - before
                    assert cmds.ls(imported, type="mesh"), imported
                    # Preserve upstream's existing behavior: its translator does
                    # not declare namespace support. Toolkit isolation uses its
                    # returned nodes/UUIDs, not a new namespace behavior here.
                    assert not backend.module.CastFileTranslator().haveNamespaceSupport()
                    assert all(sys.modules[name] is value for name, value in sentinels.items())
                finally:
                    cmds.file(new=True, force=True)
                    cmds.unloadPlugin(loaded[private_path])
                    assert not backend.registered
                    assert cmds.pluginInfo(str(external_path), query=True, loaded=True)
                    assert cmds.pluginInfo(str(external_path), query=True, translator=True) == ["Cast"]
                    cmds.unloadPlugin(loaded[external_path])
                assert helper.get_backend(str(CORE)) is backend
            assert not (folder / "cast.cfg").exists()
            print("PRIVATE_CAST_COEXISTENCE_RETURN_NODES_RELOAD_OK")
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
