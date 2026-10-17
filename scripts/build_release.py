"""Build Maya and Blender EN/ZH archives from explicit file lists."""

import argparse
import ast
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]

# These are published files, not a directory scan: preferences, generated
# assets and unrelated source files must never leak into an archive.
DOCUMENTS = (
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
    "docs/CAST_BACKEND_BENCHMARK.md", "docs/RELEASE_CHECKLIST.md",
    "docs/RELEASE_NOTES_3.5.1.md",
    "docs/RELEASE_NOTES_3.6.0.md",
    "docs/RELEASE_NOTES_3.6.1.md",
)
VERSION_FILES = (
    "plug-ins/viewmodel_weapon_toolkit.py",
    "plug-ins/viewmodel_weapon_toolkit_zh_CN.py",
    "blender/cod_viewmodel_toolkit/__init__.py",
    "blender/cod_viewmodel_toolkit/core.py",
    "blender/cod_viewmodel_toolkit/ui.py",
)


def _file_catalog(platform, edition):
    files = {name: name for name in DOCUMENTS}
    if platform == "maya":
        for name in ("SECURITY.md", "plug-ins/viewmodel_weapon_toolkit.py",
                     "plug-ins/cod_viewmodel_units.py",
                     "plug-ins/cod_viewmodel_exports.py",
                     "plug-ins/cod_viewmodel_cast_backend.py"):
            files[name] = name
        for name in ("cast.py", "castplugin.py"):
            files["plug-ins/cod_viewmodel_cast/" + name] = "third_party/cast/" + name
        entry = ("attach_gun.py" if edition == "en" else
                 "viewmodel_weapon_toolkit_zh_CN.py")
        files["plug-ins/" + entry] = "plug-ins/" + entry
    else:
        for name in ("__init__", "backend", "core", "animation", "exporting", "fbx", "ui", "units"):
            files[name + ".py"] = "blender/cod_viewmodel_toolkit/" + name + ".py"
        for name in ("__init__.py", "import_cast.py", "export_cast.py", "shared_cast.py", "PATCHES.md"):
            files["vendor_cast/" + name] = "third_party/cast_blender/" + name
        files["vendor_cast/cast.py"] = "third_party/cast/cast.py"
        files["vendor_cast/LICENSE"] = "third_party/cast/LICENSE"
        files["third_party/cast_blender/PATCHES.md"] = "third_party/cast_blender/PATCHES.md"
    return files


def _literal(source, path, name, class_name=None):
    """Read a release declaration without executing host-dependent modules."""
    tree = ast.parse(source, filename=path)
    nodes = tree.body
    if class_name is not None:
        classes = [node for node in nodes if isinstance(node, ast.ClassDef)
                   and node.name == class_name]
        if len(classes) != 1:
            raise ValueError("%s: expected one %s class" % (path, class_name))
        nodes = classes[0].body
    matches = [node.value for node in nodes if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == name
                       for target in node.targets)]
    if len(matches) != 1:
        raise ValueError("%s: expected one literal %s declaration" % (path, name))
    try:
        return ast.literal_eval(matches[0])
    except (ValueError, TypeError) as error:
        raise ValueError("%s: %s must be a literal" % (path, name)) from error


def _release_version(sources):
    path = VERSION_FILES[0]
    version = _literal(sources[path], path, "VERSION")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("%s: invalid VERSION %r" % (path, version))
    for path in (VERSION_FILES[1], VERSION_FILES[3]):
        actual = _literal(sources[path], path, "VERSION")
        if actual != version:
            raise ValueError("%s: VERSION %r does not match %s" % (path, actual, version))
    path = VERSION_FILES[2]
    info = _literal(sources[path], path, "bl_info")
    expected = tuple(int(part) for part in version.split("."))
    actual = info.get("version") if isinstance(info, dict) else None
    if (not isinstance(actual, tuple) or any(type(part) is not int for part in actual)
            or actual != expected):
        raise ValueError("%s: bl_info version does not match %s" % (path, version))
    path = VERSION_FILES[4]
    title = _literal(sources[path], path, "bl_label", "CODVWT_PT_main")
    if title != "CoD Viewmodel Toolkit " + version:
        raise ValueError("%s: main panel title %r does not match %s" % (path, title, version))
    return version


def _release_plan(blender_zh_only):
    """Snapshot and validate every input before creating any output directory."""
    from blender_zh_cn import localize

    editions = [("blender", "zh-CN")] if blender_zh_only else [
        (platform, edition) for platform in ("maya", "blender")
        for edition in ("en", "zh-CN")]
    catalogs = [_file_catalog(platform, edition) for platform, edition in editions]
    originals = set(VERSION_FILES)
    for files in catalogs:
        originals.update(files.values())
    snapshot = {name: (ROOT / name).read_bytes() for name in sorted(originals)}
    version = _release_version({name: snapshot[name].decode("utf-8") for name in VERSION_FILES})
    localized = {
        name: localize(snapshot["blender/cod_viewmodel_toolkit/" + name].decode("utf-8"), name)
        for name in ("__init__.py", "ui.py")
    }
    title = _literal(localized["ui.py"].decode("utf-8"), "localized ui.py",
                     "bl_label", "CODVWT_PT_main")
    if title != "CoD 视角模型工具包 " + version:
        raise ValueError("scripts/blender_zh_cn.py: missing or incorrect mapping for CoD Viewmodel Toolkit %s" % version)
    info = _literal(localized["__init__.py"].decode("utf-8"), "localized __init__.py", "bl_info")
    if info.get("name") != "CoD 视角模型工具包（简体中文）":
        raise ValueError("scripts/blender_zh_cn.py: missing Simplified Chinese addon name mapping")
    plans = []
    for (platform, edition), files in zip(editions, catalogs):
        filename = "cod-viewmodel-toolkit-%s-%s-%s" % (version, platform, edition)
        prefix = filename if platform == "maya" else "cod_viewmodel_toolkit"
        contents = {prefix + "/" + target:
                    (localized[target] if platform == "blender" and edition == "zh-CN"
                     and target in localized else snapshot[original])
                    for target, original in files.items()}
        plans.append((filename + ".zip", contents))
    return plans


def _rollback_created(created):
    """Remove only files still identifying outputs exclusively created by us."""
    errors = []
    for path, identity in reversed(created):
        try:
            current = path.lstat()
            if (current.st_dev, current.st_ino) == identity:
                path.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            errors.append((path, error))
    if errors:
        raise OSError("Could not roll back release archive(s): %s" %
                      "; ".join("%s: %s" % item for item in errors))


def build(output, blender_zh_only=False):
    """Build all requested archives before publishing without overwriting files.

    Publication uses exclusive file creation, not an atomic multi-file commit.
    On failure, newly created outputs are rolled back; pre-existing or replaced
    files belong to their creator and are preserved.
    """
    plans = _release_plan(blender_zh_only)
    output = Path(output).resolve()
    for filename, unused in plans:
        if os.path.lexists(str(output / filename)):
            raise FileExistsError("Release archive already exists: %s" % (output / filename))
    output.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with tempfile.TemporaryDirectory(prefix=".cod-release-", dir=str(output)) as temporary:
            staging = Path(temporary)
            for filename, contents in plans:
                with zipfile.ZipFile(str(staging / filename), "x", zipfile.ZIP_DEFLATED) as bundle:
                    for name, data in sorted(contents.items()):
                        info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                        info.compress_type = zipfile.ZIP_DEFLATED
                        info.external_attr = 0o644 << 16
                        bundle.writestr(info, data)
            for filename, unused in plans:
                target = output / filename
                with target.open("xb") as destination:
                    identity = os.fstat(destination.fileno())
                    created.append((target, (identity.st_dev, identity.st_ino)))
                    with (staging / filename).open("rb") as source:
                        shutil.copyfileobj(source, destination)
    except BaseException:
        _rollback_created(created)
        raise
    for filename, unused in plans:
        archive = output / filename
        print(archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="Directory for platform/language ZIPs")
    parser.add_argument("--blender-zh-only", action="store_true", help="Build only the supplemental Blender Chinese package")
    args = parser.parse_args()
    build(args.output, args.blender_zh_only)
