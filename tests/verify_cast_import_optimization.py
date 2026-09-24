"""Mayapy: import equivalence, preflight counts and operation-local cache lifetime."""
from pathlib import Path
import os
import sys
import tempfile
from unittest.mock import patch

from benchmark_cast_import import baseline_module, snapshot, core, cmds
import maya.standalone
from verify_batch_animation_export import make_model


def main():
    cmds.loadPlugin(core.__file__, quiet=True)
    backend = core._castplugin_module()
    old = baseline_module("third_party/cast/castplugin.py", "cast_342_regression")
    old.sceneSettings = backend.sceneSettings
    old_core = baseline_module("plug-ins/viewmodel_weapon_toolkit.py", "toolkit_342_regression")
    with tempfile.TemporaryDirectory(prefix="cast_import_regression_") as folder:
        folder = Path(folder)
        hands, weapon = folder / "hands.cast", folder / "weapon.cast"
        make_model(core, hands, True)
        make_model(core, weapon, False)
        document = backend.Cast.load(str(weapon))
        mesh = document.Roots()[0].ChildrenOfType(backend.Model)[0].Meshes()[0]
        count = mesh.VertexCount()
        # Preserve orphan vertices, remove degenerates, and exercise both color encodings.
        mesh.SetFaceBuffer(list(mesh.FaceBuffer())[:-3] + [0, 0, 1])
        mesh.SetUVLayerCount(2)
        mesh.SetVertexUVLayerBuffer(1, [(i / count, 1.5 - i / count) for i in range(count)])
        mesh.SetColorLayerCount(2)
        mesh.SetVertexColorBuffer(0, [0x80FF0020] * count)
        mesh.SetVertexColorBuffer(1, [(0.25, 0.5, 0.75, 0.5)] * count)
        document.save(str(weapon))
        assert core._cast_bone_inventory(str(weapon)) == old_core._cast_bone_inventory(str(weapon))
        outputs = []
        for importer in (old.importModelNode, backend.importModelNode):
            cmds.file(new=True, force=True)
            with patch.object(backend, "importModelNode", importer):
                core.import_cast(str(weapon), "fixture")
            outputs.append(snapshot())
        assert outputs[0] == outputs[1], "Mesh channels differ from 3.4.2"
        print("CAST_BUFFER_EQUIVALENCE_OK")

        with patch.object(backend.Cast, "load", wraps=backend.Cast.load) as load:
            core._build_single_attachment(str(hands), str(weapon),
                core.AttachOptions(force_new_scene=True, export_cast=False))
            assert load.call_count == 2, load.call_args_list
        assert backend._castReadCache is None
        with backend.utilityCastReadSession():
            first = backend.utilityLoadCast(str(weapon))
            with backend.utilityCastReadSession():
                assert backend.utilityLoadCast(str(weapon)) is first
            assert backend.utilityLoadCast(str(weapon)) is first
            info = weapon.stat()
            os.utime(str(weapon), ns=(info.st_atime_ns, info.st_mtime_ns + 2000000000))
            assert backend.utilityLoadCast(str(weapon)) is not first
        assert backend._castReadCache is None
        try:
            with backend.utilityCastReadSession():
                backend.utilityLoadCast(str(weapon))
                raise RuntimeError("fixture failure")
        except RuntimeError:
            pass
        assert backend._castReadCache is None
        try:
            core._build_single_attachment(str(hands), str(folder / "missing.cast"),
                core.AttachOptions(force_new_scene=True, export_cast=False))
        except RuntimeError:
            pass
        else:
            raise AssertionError("Missing file unexpectedly accepted")
        assert backend._castReadCache is None
        with patch.object(backend.Cast, "load", wraps=backend.Cast.load) as load:
            backend.utilityLoadCast(str(weapon))
            backend.utilityLoadCast(str(weapon))
            assert load.call_count == 2, "Ordinary imports must not cache"
        print("CAST_READ_SESSION_OK")

        # Invalid indices must count occurrences; UV mismatch diagnostics stay intact.
        mesh.SetFaceBuffer([0, count + 5, count + 5, 0, 1, 2])
        mesh.SetVertexUVLayerBuffer(1, [(0.0, 0.0)])
        document.save(str(weapon))
        new_report = core._cast_bone_inventory(str(weapon))
        assert new_report == old_core._cast_bone_inventory(str(weapon))
        assert new_report["invalid_face_index_count"] == 2
        assert new_report["uv_buffer_mismatch_count"] == 1
        print("CAST_PREFLIGHT_EQUIVALENCE_OK")


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
