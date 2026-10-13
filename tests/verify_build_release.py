"""Host-free release contracts; run with ordinary Python, not Maya/Blender."""

from contextlib import redirect_stdout
import ast
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import build_release
import blender_zh_cn


# Existing layouts plus the two agreed release-process documents are a
# compatibility contract independent of the builder's internal catalog.
DOCUMENTS = {
    "CHANGELOG.md", "LICENSE", "README.md", "README.zh-CN.md",
    "THIRD_PARTY_NOTICES.md", "third_party/cast/LICENSE",
    "third_party/cast/PATCHES.md", "docs/OUTPUT_UNITS.md",
    "docs/VERIFICATION_3.4.0.md", "docs/BATCH_ANIMATION_VERIFICATION.md",
    "docs/VERIFICATION_3.2.0.md", "docs/RELEASE_NOTES_3.2.0.md",
    "docs/VERIFICATION_3.3.0.md", "docs/RELEASE_NOTES_3.3.0.md",
    "docs/RELEASE_NOTES_3.4.0.md", "docs/BLENDER.md", "docs/BLENDER.zh-CN.md",
    "docs/RELEASE_NOTES_3.4.1.md", "docs/VERIFICATION_3.4.1.md",
    "docs/MAYA.md", "docs/MAYA.zh-CN.md", "docs/RELEASE_NOTES_3.4.2.md",
    "docs/RELEASE_NOTES_3.4.3.md", "docs/CAST_IMPORT_OPTIMIZATION.md",
    "docs/RELEASE_NOTES_3.5.0.md", "docs/CAST_BACKEND_RESEARCH.md",
    "docs/CAST_BACKEND_BENCHMARK.md",
    "docs/RELEASE_CHECKLIST.md", "docs/RELEASE_NOTES_3.5.1.md",
}
MAYA_FILES = DOCUMENTS | {
    "SECURITY.md", "plug-ins/viewmodel_weapon_toolkit.py",
    "plug-ins/cod_viewmodel_units.py", "plug-ins/cod_viewmodel_cast_backend.py",
    "plug-ins/cod_viewmodel_cast/cast.py",
    "plug-ins/cod_viewmodel_cast/castplugin.py",
}
BLENDER_FILES = DOCUMENTS | {
    name + ".py" for name in
    ("__init__", "backend", "core", "animation", "exporting", "fbx", "ui", "units")
} | {
    "vendor_cast/__init__.py", "vendor_cast/import_cast.py",
    "vendor_cast/export_cast.py", "vendor_cast/shared_cast.py",
    "vendor_cast/PATCHES.md", "vendor_cast/cast.py", "vendor_cast/LICENSE",
    "third_party/cast_blender/PATCHES.md",
}


def fixture_sources():
    """Copy only release-listed text/runtime sources, never the whole checkout."""
    sources = DOCUMENTS | {"SECURITY.md", "scripts/build_release.py",
                           "scripts/blender_zh_cn.py"}
    sources |= {
        "plug-ins/" + name for name in
        ("viewmodel_weapon_toolkit.py", "viewmodel_weapon_toolkit_zh_CN.py",
         "attach_gun.py", "cod_viewmodel_units.py", "cod_viewmodel_cast_backend.py")
    }
    sources |= {
        "blender/cod_viewmodel_toolkit/" + name + ".py" for name in
        ("__init__", "backend", "core", "animation", "exporting", "fbx", "ui", "units")
    }
    sources |= {"third_party/cast/cast.py", "third_party/cast/castplugin.py"}
    sources |= {
        "third_party/cast_blender/" + name for name in
        ("__init__.py", "import_cast.py", "export_cast.py", "shared_cast.py", "PATCHES.md")
    }
    return sources


def assignments(source, name):
    """Inspect stable operation identifiers without importing bpy or Maya."""
    return [ast.literal_eval(node.value) for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name
                for target in node.targets)]


class ReleaseBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cod_release_contract_")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.root = self.folder / "source"
        self.root.mkdir()
        for name in fixture_sources():
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(REPO / name), str(destination))
        self.output = self.folder / "packages"
        self.root_patch = mock.patch.object(build_release, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.version = assignments(
            (self.root / "plug-ins/viewmodel_weapon_toolkit.py").read_text(encoding="utf-8"),
            "VERSION")[0]

    def build(self, output=None, zh_only=False):
        with redirect_stdout(io.StringIO()):
            build_release.build(output or self.output, zh_only)

    def mutate(self, name, old, new):
        path = self.root / name
        source = path.read_text(encoding="utf-8")
        self.assertIn(old, source)
        path.write_text(source.replace(old, new, 1), encoding="utf-8")

    def package_name(self, platform, edition):
        return "cod-viewmodel-toolkit-%s-%s-%s.zip" % (self.version, platform, edition)

    def assert_no_output(self):
        self.assertFalse(self.output.exists(), "Failed preflight created output directory")

    def test_version_failures_leave_no_output(self):
        cases = (
            ("plug-ins/viewmodel_weapon_toolkit_zh_CN.py", 'VERSION = "%s"' % self.version,
             'VERSION = "0.0.0"'),
            ("blender/cod_viewmodel_toolkit/__init__.py", '"version": %r' % (tuple(map(int, self.version.split("."))),),
             '"version": (0, 0, 0)'),
            ("blender/cod_viewmodel_toolkit/core.py", 'VERSION = "%s"' % self.version,
             'VERSION = "0.0.0"'),
            ("blender/cod_viewmodel_toolkit/ui.py", "CoD Viewmodel Toolkit " + self.version,
             "CoD Viewmodel Toolkit 0.0.0"),
        )
        for name, old, new in cases:
            with self.subTest(path=name):
                path = self.root / name
                original = path.read_bytes()
                self.mutate(name, old, new)
                try:
                    with self.assertRaises((ValueError, RuntimeError)) as failure:
                        self.build()
                    self.assertIn(name, str(failure.exception))
                    self.assert_no_output()
                finally:
                    path.write_bytes(original)

    def test_optimized_python_does_not_disable_version_validation(self):
        self.mutate("blender/cod_viewmodel_toolkit/core.py",
                    'VERSION = "%s"' % self.version, 'VERSION = "0.0.0"')
        result = subprocess.run(
            [sys.executable, "-O", "-B", str(self.root / "scripts/build_release.py"),
             str(self.output)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"blender/cod_viewmodel_toolkit/core.py", result.stderr)
        self.assert_no_output()

    def test_blender_version_requires_integer_components(self):
        version = tuple(int(part) for part in self.version.split("."))
        self.mutate("blender/cod_viewmodel_toolkit/__init__.py",
                    '"version": %r' % (version,),
                    '"version": %r' % (tuple(float(part) for part in version),))
        with self.assertRaisesRegex(ValueError, "bl_info version"):
            self.build()
        self.assert_no_output()

    def test_missing_source_leaves_no_output(self):
        missing = "third_party/cast_blender/shared_cast.py"
        (self.root / missing).unlink()
        with self.assertRaises((OSError, ValueError, RuntimeError)) as failure:
            self.build()
        self.assertIn("shared_cast.py", str(failure.exception))
        self.assert_no_output()

    def test_missing_chinese_title_mapping_leaves_no_output(self):
        title = "CoD Viewmodel Toolkit " + self.version
        with mock.patch.dict(blender_zh_cn.TEXT, {}, clear=True):
            with self.assertRaises((ValueError, RuntimeError)) as failure:
                self.build()
        self.assertIn(title, str(failure.exception))
        self.assert_no_output()

    def test_localization_rejects_each_missing_semantic_rewrite(self):
        source = (self.root / "blender/cod_viewmodel_toolkit/ui.py").read_text(encoding="utf-8")
        cases = (
            ("width = max(22,", "width = max(23,"),
            ("(7 * context.preferences.system.ui_scale)", "(8 * context.preferences.system.ui_scale)"),
            ("self.side.title() +", "self.side.upper() +"),
            ('result["status"])', 'result.get("status"))'),
        )
        for old, new in cases:
            with self.subTest(rewrite=old):
                with self.assertRaises((ValueError, RuntimeError)) as failure:
                    blender_zh_cn.localize(source.replace(old, new, 1), "ui.py")
                self.assertIn("ui.py", str(failure.exception))

    def test_localization_rejects_duplicate_semantic_rewrite(self):
        source = (self.root / "blender/cod_viewmodel_toolkit/ui.py").read_text(encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "found 2"):
            blender_zh_cn.localize(source + "\n# width = max(22,\n", "ui.py")

    def test_changed_chinese_rewrite_leaves_no_output(self):
        self.mutate("blender/cod_viewmodel_toolkit/ui.py",
                    "self.side.title() +", "self.side.upper() +")
        with self.assertRaisesRegex(ValueError, "ui.py"):
            self.build()
        self.assert_no_output()

    def test_existing_last_archive_is_preserved_and_no_other_package_created(self):
        self.output.mkdir()
        existing = self.output / self.package_name("blender", "zh-CN")
        existing.write_bytes(b"delivered archive")
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual(existing.read_bytes(), b"delivered archive")
        self.assertEqual(list(self.output.iterdir()), [existing])

    def test_archive_generation_failure_cleans_staging(self):
        self.output.mkdir()
        sentinel = self.output / "unrelated.txt"
        sentinel.write_bytes(b"keep")
        original = zipfile.ZipFile.writestr
        count = [0]

        def fail_later(bundle, *args, **kwargs):
            count[0] += 1
            if count[0] == len(MAYA_FILES) + 3:
                raise OSError("injected archive write failure")
            return original(bundle, *args, **kwargs)

        with mock.patch.object(zipfile.ZipFile, "writestr", fail_later):
            with self.assertRaisesRegex(OSError, "injected archive"):
                self.build()
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_publish_failure_removes_only_own_outputs(self):
        self.output.mkdir()
        sentinel = self.output / "unrelated.txt"
        sentinel.write_bytes(b"keep")
        original = shutil.copyfileobj
        count = [0]

        def fail_second(source, destination, *args, **kwargs):
            count[0] += 1
            if count[0] == 2:
                destination.write(b"partial")
                raise OSError("injected publish write failure")
            return original(source, destination, *args, **kwargs)

        with mock.patch.object(shutil, "copyfileobj", fail_second):
            with self.assertRaisesRegex(OSError, "injected publish"):
                self.build()
        self.assertEqual(list(self.output.iterdir()), [sentinel])
        self.assertEqual(sentinel.read_bytes(), b"keep")
        self.build()
        self.assertEqual(len(list(self.output.glob("*.zip"))), 4)

    def test_rollback_failure_still_attempts_other_outputs(self):
        original_copy = shutil.copyfileobj
        original_unlink = Path.unlink
        blocked = self.output / self.package_name("maya", "zh-CN")
        count = [0]

        def fail_third(source, destination, *args, **kwargs):
            count[0] += 1
            if count[0] == 3:
                raise OSError("injected publishing failure")
            return original_copy(source, destination, *args, **kwargs)

        def deny_one(path, *args, **kwargs):
            if path == blocked:
                raise PermissionError("injected rollback failure")
            return original_unlink(path, *args, **kwargs)

        with mock.patch.object(shutil, "copyfileobj", fail_third), \
                mock.patch.object(Path, "unlink", deny_one):
            with self.assertRaises(OSError) as failure:
                self.build()
        self.assertIn(str(blocked), str(failure.exception))
        self.assertEqual(list(self.output.iterdir()), [blocked])

    def test_concurrent_target_is_not_removed_on_rollback(self):
        original = shutil.copyfileobj
        conflict = self.output / self.package_name("maya", "zh-CN")

        def create_conflict(source, destination, *args, **kwargs):
            result = original(source, destination, *args, **kwargs)
            if not conflict.exists():
                conflict.write_bytes(b"another build")
            return result

        with mock.patch.object(shutil, "copyfileobj", create_conflict):
            with self.assertRaises(FileExistsError):
                self.build()
        self.assertEqual(conflict.read_bytes(), b"another build")
        self.assertEqual(list(self.output.iterdir()), [conflict])

    def test_concurrent_replacement_is_not_removed_on_rollback(self):
        original = shutil.copyfileobj
        first = self.output / self.package_name("maya", "en")
        count = [0]

        def replace_then_fail(source, destination, *args, **kwargs):
            count[0] += 1
            if count[0] == 2:
                replacement = self.output / "replacement.tmp"
                replacement.write_bytes(b"another process replacement")
                replacement.replace(first)
                raise OSError("injected after concurrent replacement")
            return original(source, destination, *args, **kwargs)

        with mock.patch.object(shutil, "copyfileobj", replace_then_fail):
            with self.assertRaisesRegex(OSError, "concurrent replacement"):
                self.build()
        self.assertEqual(first.read_bytes(), b"another process replacement")
        self.assertEqual(list(self.output.iterdir()), [first])

    def test_four_packages_preserve_layout_bytes_and_language_contracts(self):
        self.build()
        expected_names = {
            self.package_name(platform, edition)
            for platform in ("maya", "blender") for edition in ("en", "zh-CN")
        }
        self.assertEqual({path.name for path in self.output.iterdir()}, expected_names)
        for platform in ("maya", "blender"):
            for edition in ("en", "zh-CN"):
                with self.subTest(platform=platform, edition=edition):
                    archive = self.output / self.package_name(platform, edition)
                    prefix = archive.stem if platform == "maya" else "cod_viewmodel_toolkit"
                    expected = set(MAYA_FILES if platform == "maya" else BLENDER_FILES)
                    if platform == "maya":
                        expected.add("plug-ins/" + ("attach_gun.py" if edition == "en"
                                                   else "viewmodel_weapon_toolkit_zh_CN.py"))
                    with zipfile.ZipFile(str(archive)) as bundle:
                        self.assertEqual(set(bundle.namelist()), {prefix + "/" + name for name in expected})
                        self.assertEqual(bundle.namelist(), sorted(bundle.namelist()))
                        for item in bundle.infolist():
                            self.assertEqual(item.date_time, (2026, 1, 1, 0, 0, 0))
                            self.assertEqual(item.external_attr, 0o644 << 16)
                            self.assertEqual(item.compress_type, zipfile.ZIP_DEFLATED)
                        for name in expected:
                            if platform == "blender" and edition == "zh-CN" and name in ("__init__.py", "ui.py"):
                                continue
                            original = name
                            if platform == "maya" and name.startswith("plug-ins/cod_viewmodel_cast/"):
                                original = "third_party/cast/" + Path(name).name
                            elif platform == "blender":
                                if name in ("vendor_cast/cast.py", "vendor_cast/LICENSE"):
                                    original = "third_party/cast/" + Path(name).name
                                elif name.startswith("vendor_cast/"):
                                    original = "third_party/cast_blender/" + Path(name).name
                                elif name.endswith(".py"):
                                    original = "blender/cod_viewmodel_toolkit/" + name
                            self.assertEqual(bundle.read(prefix + "/" + name),
                                             (self.root / original).read_bytes(), name)
                        if platform == "maya":
                            self.assertEqual(bundle.read(prefix + "/plug-ins/cod_viewmodel_cast/cast.py"),
                                             (self.root / "third_party/cast/cast.py").read_bytes())
                        else:
                            ui = bundle.read(prefix + "/ui.py").decode("utf-8")
                            original_ui = (self.root / "blender/cod_viewmodel_toolkit/ui.py").read_text(encoding="utf-8")
                            self.assertEqual(assignments(ui, "bl_idname"), assignments(original_ui, "bl_idname"))
                            if edition == "en":
                                self.assertEqual(ui.encode("utf-8"), (self.root / "blender/cod_viewmodel_toolkit/ui.py").read_bytes())
                            else:
                                self.assertIn("CoD 视角模型工具包 " + self.version, ui)
                                self.assertIn("组装模型", assignments(ui, "bl_label"))
                                self.assertIn("width = max(11,", ui)
                                self.assertIn("(14 * context.preferences.system.ui_scale)", ui)
                                self.assertIn("'左' if self.side == 'left' else '右'", ui)
                                self.assertIn('"ok": "成功", "failed": "失败"', ui)
                                init = bundle.read(prefix + "/__init__.py").decode("utf-8")
                                self.assertIn("简体中文", init)
                        self.assertFalse(any(name.endswith(("cast.cfg", "castpluginoptions.mel", ".pyc"))
                                             for name in bundle.namelist()))

    def test_same_sources_build_identical_archives(self):
        self.build()
        second = self.folder / "second"
        self.build(second)
        for archive in self.output.iterdir():
            self.assertEqual(archive.read_bytes(), (second / archive.name).read_bytes())

    def test_chinese_only_cli_builds_one_package(self):
        result = subprocess.run(
            [sys.executable, "-B", str(self.root / "scripts/build_release.py"),
             str(self.output), "--blender-zh-only"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        expected = self.package_name("blender", "zh-CN")
        self.assertEqual({path.name for path in self.output.iterdir()}, {expected})
        self.assertEqual(len(result.stdout.splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
