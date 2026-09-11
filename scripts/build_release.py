"""Build Maya and Blender EN/ZH archives from explicit file lists."""

import argparse
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output, blender_zh_only=False):
    source = (ROOT / "plug-ins/viewmodel_weapon_toolkit.py").read_text(
        encoding="utf-8")
    version = re.search(r'^VERSION = "([0-9.]+)"$', source, re.MULTILINE).group(1)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    common = {name: name for name in (
        "CHANGELOG.md", "LICENSE", "README.md", "README.zh-CN.md",
        "SECURITY.md", "THIRD_PARTY_NOTICES.md", "docs/OUTPUT_UNITS.md", "docs/VERIFICATION_3.4.0.md",
        "plug-ins/viewmodel_weapon_toolkit.py", "plug-ins/cod_viewmodel_units.py", "third_party/cast/LICENSE",
        "third_party/cast/PATCHES.md", "docs/BATCH_ANIMATION_VERIFICATION.md",
        "docs/VERIFICATION_3.2.0.md", "docs/RELEASE_NOTES_3.2.0.md",
        "docs/VERIFICATION_3.3.0.md", "docs/RELEASE_NOTES_3.3.0.md", "docs/RELEASE_NOTES_3.4.0.md",
        "docs/BLENDER.md", "docs/BLENDER.zh-CN.md")}
    for name in ("cast.py", "castplugin.py"):
        common["plug-ins/" + name] = "third_party/cast/" + name
    for edition in (() if blender_zh_only else ("en", "zh-CN")):
        files = dict(common)
        entry = ("attach_gun.py" if edition == "en" else
                 "viewmodel_weapon_toolkit_zh_CN.py")
        files["plug-ins/" + entry] = "plug-ins/" + entry
        prefix = "cod-viewmodel-toolkit-%s-maya-%s" % (version, edition)
        archive = output / (prefix + ".zip")
        # Refuse accidental overwrites of an already delivered archive.
        with zipfile.ZipFile(str(archive), "x", zipfile.ZIP_DEFLATED) as bundle:
            for target, original in sorted(files.items()):
                info = zipfile.ZipInfo(prefix + "/" + target, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                bundle.writestr(info, (ROOT / original).read_bytes())
        print(archive)
    import ast
    tree = ast.parse((ROOT / "blender/cod_viewmodel_toolkit/__init__.py").read_text(encoding="utf-8"))
    info = next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == "bl_info" for target in node.targets))
    assert ".".join(map(str, info["version"])) == version
    files = {name + ".py": "blender/cod_viewmodel_toolkit/" + name + ".py"
             for name in ("__init__", "backend", "core", "animation", "exporting", "fbx", "ui", "units")}
    for name in ("__init__.py", "import_cast.py", "export_cast.py", "shared_cast.py", "PATCHES.md"):
        files["vendor_cast/" + name] = "third_party/cast_blender/" + name
    files["vendor_cast/cast.py"] = "third_party/cast/cast.py"
    files["vendor_cast/LICENSE"] = "third_party/cast/LICENSE"
    for name in ("LICENSE", "README.md", "README.zh-CN.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md",
                 "third_party/cast/LICENSE", "third_party/cast/PATCHES.md",
                 "third_party/cast_blender/PATCHES.md",
                 "docs/BLENDER.md", "docs/BLENDER.zh-CN.md", "docs/VERIFICATION_3.3.0.md",
                 "docs/VERIFICATION_3.2.0.md", "docs/RELEASE_NOTES_3.2.0.md",
                 "docs/BATCH_ANIMATION_VERIFICATION.md", "docs/OUTPUT_UNITS.md", "docs/VERIFICATION_3.4.0.md",
                 "docs/RELEASE_NOTES_3.3.0.md", "docs/RELEASE_NOTES_3.4.0.md"):
        files[name] = name
    from blender_zh_cn import localize
    for edition in (("zh-CN",) if blender_zh_only else ("en", "zh-CN")):
        archive = output / ("cod-viewmodel-toolkit-%s-blender-%s.zip" % (version, edition))
        with zipfile.ZipFile(str(archive), "x", zipfile.ZIP_DEFLATED) as bundle:
            for target, original in sorted(files.items()):
                info = zipfile.ZipInfo("cod_viewmodel_toolkit/" + target, (2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                data = (ROOT / original).read_bytes()
                if edition == "zh-CN" and target in ("__init__.py", "ui.py"):
                    data = localize(data.decode("utf-8"), target)
                bundle.writestr(info, data)
        print(archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="Directory for platform/language ZIPs")
    parser.add_argument("--blender-zh-only", action="store_true", help="Build only the supplemental Blender Chinese package")
    args = parser.parse_args()
    build(args.output, args.blender_zh_only)
