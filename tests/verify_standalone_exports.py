"""Host-free contracts for single-file export; synthetic Maya tests are separate."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "vwt_standalone_contract", ROOT / "plug-ins/cod_viewmodel_exports.py")
exports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exports)


class Commands:
    def __init__(self):
        self.name, self.modified, self.selection, self.frame = "original.ma", True, ["joint"], 2
        self.playback = {"animationStartTime": 0, "animationEndTime": 3, "minTime": 0, "maxTime": 3}
        self.snapshots = 0

    def file(self, path=None, **kwargs):
        if kwargs.get("query"):
            return self.name if kwargs.get("sceneName") else self.modified
        if kwargs.get("exportAll"):
            self.snapshots += 1
            Path(path).write_text("synthetic scene", encoding="utf-8")
            self.modified = True
        if "rename" in kwargs:
            self.name = kwargs["rename"]
        if "modified" in kwargs:
            self.modified = kwargs["modified"]

    def ls(self, *args, **kwargs):
        return list(self.selection) if kwargs.get("selection") else []

    def currentTime(self, value=None, **kwargs):
        if kwargs.get("query"):
            return self.frame
        self.frame = value

    def upAxis(self, **kwargs):
        return "y"

    def playbackOptions(self, **kwargs):
        if kwargs.pop("query", False):
            return next(self.playback[name] for name, enabled in kwargs.items() if enabled)
        self.playback.update(kwargs)

    def select(self, nodes=None, **kwargs):
        self.selection = [] if kwargs.get("clear") else list(nodes)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="vwt_export_contract_")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.executable = self.folder / ("mayapy.exe" if os.name == "nt" else "mayapy")
        self.executable.write_bytes(b"fake executable; never launched")
        self.commands = Commands()
        self.core = SimpleNamespace(
            cmds=self.commands, _core_module_path=lambda: str(ROOT / "plug-ins/viewmodel_weapon_toolkit.py"),
            _LAST_RESULT=None, DUAL_STATE_NODE="dual_state", log=lambda message: None,
            load_saved_options=lambda: SimpleNamespace(source_joint="j_gun", target_joint="tag_weapon"),
            validate_attachment=lambda source, target: {"source_node": source, "target_node": target},
            _short_name=lambda name: name.split("|")[-1],
        )
        self.addCleanup(patch.stopall)
        patch.object(exports.sys, "executable", str(self.executable)).start()
        self.requests = []

    def worker(self, executable, request_path, folder):
        request = json.loads(request_path.read_text(encoding="utf-8"))
        self.requests.append(request)
        Path(request["output"]).write_bytes(b"verified export bytes")
        return {"format": request["format"], "animation_included": request["animated"]}

    def assert_preserved(self):
        self.assertEqual((self.commands.name, self.commands.modified, self.commands.selection, self.commands.frame),
                         ("original.ma", True, ["joint"], 2))

    def test_only_selected_file_and_source_state(self):
        with patch.object(exports, "_run_worker", side_effect=self.worker):
            for file_format in ("fbx", "smd"):
                folder = self.folder / file_format
                report = exports.export_file(self.core, str(folder / "scene"), file_format)
                self.assertEqual([path.name for path in folder.iterdir()], ["scene." + file_format])
                self.assertEqual(Path(report["path"]).read_bytes(), b"verified export bytes")
                self.assertTrue(report["source_scene_preserved"])
                self.assert_preserved()

    def test_existing_file_gets_version_without_overwrite(self):
        original = self.folder / "scene.fbx"
        original.write_bytes(b"original bytes")
        with patch.object(exports, "_run_worker", side_effect=self.worker):
            report = exports.export_file(self.core, str(original), "fbx")
        self.assertEqual(original.read_bytes(), b"original bytes")
        self.assertEqual(Path(report["path"]).name, "scene_v001.fbx")

    def test_worker_failure_leaves_no_file_or_staging(self):
        original = self.folder / "scene.fbx"
        original.write_bytes(b"original bytes")
        with patch.object(exports, "_run_worker", side_effect=RuntimeError("writer failed")):
            with self.assertRaisesRegex(RuntimeError, "writer failed"):
                exports.export_file(self.core, str(original), "fbx")
        self.assertEqual(sorted(path.name for path in self.folder.iterdir()), [self.executable.name, "scene.fbx"])
        self.assertEqual(original.read_bytes(), b"original bytes")
        self.assert_preserved()

    def test_bad_report_or_empty_export_is_not_published(self):
        for report in ({"format": "smd", "animation_included": False},
                       {"format": "fbx", "animation_included": False}):
            with patch.object(exports, "_run_worker", return_value=report):
                with self.assertRaises(RuntimeError):
                    exports.export_file(self.core, str(self.folder / "scene.fbx"), "fbx")
            self.assertFalse((self.folder / "scene.fbx").exists())

    def test_invalid_inputs_fail_before_snapshot(self):
        cases = ({"file_format": "max"}, {"file_format": "fbx", "output_unit": "cm"},
                 {"file_format": "fbx", "animated": "false"},
                 {"file_format": "fbx", "animated": True, "frame_range": (-1, 3)},
                 {"file_format": "fbx", "animated": True, "frame_range": (0.5, 3)},
                 {"file_format": "fbx", "animated": True, "frame_range": (0, float("inf"))})
        for case in cases:
            with self.assertRaises(ValueError):
                exports.export_file(self.core, str(self.folder / "new" / "scene.fbx"), **case)
        self.assertEqual(self.commands.snapshots, 0)
        self.assertFalse((self.folder / "new").exists())

    def test_explicit_animation_range_and_units_reach_worker(self):
        with patch.object(exports, "_run_worker", side_effect=self.worker):
            exports.export_file(self.core, str(self.folder / "clip.smd"), "smd", True, (1, 3), "m")
        self.assertEqual(self.requests[0]["frame_range"], [1, 3])
        self.assertEqual(self.requests[0]["output_unit"], "m")
        self.assertEqual(self.requests[0]["mappings"], [])

    def test_failed_publication_removes_own_partial_file(self):
        source, target = self.folder / "staged.fbx", self.folder / "scene.fbx"
        source.write_bytes(b"complete staged bytes")

        def fail(source, destination):
            destination.write(b"partial")
            raise OSError("disk write failed")

        with patch.object(exports.shutil, "copyfileobj", side_effect=fail):
            with self.assertRaisesRegex(OSError, "disk write failed"):
                exports._publish(source, target)
        self.assertFalse(target.exists())
        self.assertEqual(source.read_bytes(), b"complete staged bytes")

    def test_failed_tree_termination_still_kills_and_waits_for_worker(self):
        process = Mock(pid=123)
        process.poll.return_value = None
        with patch.object(exports.os, "name", "nt"), \
                patch.object(exports.subprocess, "run", side_effect=exports.subprocess.TimeoutExpired("taskkill", 15)):
            diagnostic = exports._stop_worker(process)
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=15)
        self.assertIn("Process-tree termination failed", diagnostic)

    def test_worker_timeout_remains_primary_error_after_cleanup_failure(self):
        process = Mock(pid=123)
        process.wait.side_effect = exports.subprocess.TimeoutExpired("mayapy", exports.WORKER_TIMEOUT)
        request = self.folder / "request.json"
        request.write_text("{}", encoding="utf-8")
        with patch.object(exports.subprocess, "Popen", return_value=process), \
                patch.object(exports, "_stop_worker", return_value="cleanup failed") as stop:
            with self.assertRaisesRegex(RuntimeError, "timed out.*") as failure:
                exports._run_worker(self.executable, request, self.folder)
        self.assertIn("cleanup failed", str(failure.exception))
        self.assertIsInstance(failure.exception.__cause__, exports.subprocess.TimeoutExpired)
        stop.assert_called_once_with(process)


if __name__ == "__main__":
    unittest.main()
