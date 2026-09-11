"""Build Maya EN/ZH and Blender EN archives from explicit file lists."""

import argparse
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    source = (ROOT / "plug-ins/viewmodel_weapon_toolkit.py").read_text(
        encoding="utf-8")
    version = re.search(r'^VERSION = "([0-9.]+)"$', source, re.MULTILINE).group(1)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    common = {name: name for name in (
        "CHANGELOG.md", "LICENSE", "README.md", "README.zh-CN.md",
        "SECURITY.md", "THIRD_PARTY_NOTICES.md",
        "plug-ins/viewmodel_weapon_toolkit.py", "third_party/cast/LICENSE",
        "third_party/cast/PATCHES.md", "docs/BATCH_ANIMATION_VERIFICATION.md",
        "docs/VERIFICATION_3.2.0.md", "docs/RELEASE_NOTES_3.2.0.md",
        "docs/VERIFICATION_3.3.0.md", "docs/RELEASE_NOTES_3.3.0.md",
        "docs/BLENDER.md", "docs/BLENDER.zh-CN.md")}
    for name in ("cast.py", "castplugin.py"):
        common["plug-ins/" + name] = "third_party/cast/" + name
    for edition in ("en", "zh-CN"):
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
             for name in ("__init__", "backend", "core", "animation", "exporting", "fbx", "ui")}
    for name in ("__init__.py", "import_cast.py", "export_cast.py", "shared_cast.py", "PATCHES.md"):
        files["vendor_cast/" + name] = "third_party/cast_blender/" + name
    files["vendor_cast/cast.py"] = "third_party/cast/cast.py"
    files["vendor_cast/LICENSE"] = "third_party/cast/LICENSE"
    for name in ("LICENSE", "README.md", "README.zh-CN.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.md",
                 "third_party/cast/LICENSE", "third_party/cast/PATCHES.md",
                 "third_party/cast_blender/PATCHES.md",
                 "docs/BLENDER.md", "docs/BLENDER.zh-CN.md", "docs/VERIFICATION_3.3.0.md",
                 "docs/VERIFICATION_3.2.0.md", "docs/RELEASE_NOTES_3.2.0.md",
                 "docs/BATCH_ANIMATION_VERIFICATION.md",
                 "docs/RELEASE_NOTES_3.3.0.md"):
        files[name] = name
    archive = output / ("cod-viewmodel-toolkit-%s-blender-en.zip" % version)
    with zipfile.ZipFile(str(archive), "x", zipfile.ZIP_DEFLATED) as bundle:
        for target, original in sorted(files.items()):
            info = zipfile.ZipInfo("cod_viewmodel_toolkit/" + target, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, (ROOT / original).read_bytes())
    print(archive)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="Directory for all three platform/language ZIPs")
    build(parser.parse_args().output)
