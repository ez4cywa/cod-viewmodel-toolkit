"""Smoke-test one assembled English or Simplified Chinese release directory."""

import argparse
import hashlib
import os
from pathlib import Path

import maya.cmds as cmds

if not hasattr(cmds, "pluginInfo"):
    import maya.standalone
    maya.standalone.initialize(name="python")


CAST_HASHES = {
    "cast.py": "d1ff7fcb2a184f208b21be34485d1863834ae33811078a28a2ccf6ff61f2c577",
    "castplugin.py": "5e28184d2fc4a24613ceeacc37006b3baaea82c4798ee0a97348f909f232fa00",
}


def same_path(left, right):
    return os.path.normcase(os.path.abspath(str(left))) == \
        os.path.normcase(os.path.abspath(str(right)))


def main(package, edition):
    package = Path(package).resolve()
    plugin_dir = package / "plug-ins"
    assert (plugin_dir / "cod_viewmodel_units.py").is_file()
    assert (package / "docs/OUTPUT_UNITS.md").is_file()
    expected = {
        "CHANGELOG.md", "LICENSE", "README.md", "README.zh-CN.md",
        "SECURITY.md", "THIRD_PARTY_NOTICES.md", "plug-ins", "third_party",
    }
    assert expected.issubset({item.name for item in package.iterdir()})
    assert not list(package.rglob("cast.cfg"))
    assert not list(package.rglob("castpluginoptions.mel"))
    assert not list(package.rglob("__pycache__"))
    assert not list(package.rglob("*.pyc"))
    for name, expected_hash in CAST_HASHES.items():
        actual = hashlib.sha256((plugin_dir / name).read_bytes()).hexdigest()
        assert actual == expected_hash, (name, actual)
    core_source = (plugin_dir / "viewmodel_weapon_toolkit.py").read_text(
        encoding="utf-8")
    for marker in ("def _about_message():", "ANIMATION & EXPORT",
                   "DQS skinning", "does not merge two"):
        assert marker in core_source, marker

    entry = plugin_dir / ("viewmodel_weapon_toolkit_zh_CN.py"
                          if edition == "zh-CN" else "viewmodel_weapon_toolkit.py")
    plugin_name = entry.stem
    cmds.loadPlugin(str(entry), quiet=True)
    assert str(cmds.pluginInfo(plugin_name, query=True, version=True)) == "3.4.2"
    assert hasattr(cmds, "viewmodelWeaponToolkit") and hasattr(cmds, "attachGun")
    # In Maya Batch the toolkit owns the fallback translator registration;
    # castplugin.py is loaded as the adjacent implementation module.
    import sys
    cast_module = sys.modules.get("castplugin")
    assert cast_module is not None
    assert same_path(getattr(cast_module, "__file__", ""),
                     plugin_dir / "castplugin.py"), getattr(cast_module, "__file__", "")
    assert str(getattr(cast_module, "version", "")) == "2.00"
    translators = cmds.pluginInfo(plugin_name, query=True, translator=True) or []
    if isinstance(translators, str):
        translators = [translators]
    assert any(str(name).lower() == "cast" for name in translators), translators
    if edition == "zh-CN":
        localized_core = sys.modules.get("viewmodel_weapon_toolkit_zh_cn_core")
        assert localized_core is not None
        translate = getattr(localized_core, "_zh_cn_translate_ui_text", None)
        assert translate is not None
        assert translate("Dual Animation Batch...") == "双持动画批量导出…"
        assert translate("Batch skinning: DQS (Dual Quaternion).") == \
            "批量蒙皮：DQS（双四元数）。"
        localized_about = translate(localized_core._about_message())
        for marker in ("主要流程", "动画与导出", "DQS 蒙皮",
                       "兼容性", "双持范围"):
            assert marker in localized_about, marker
    cmds.file(new=True, force=True)
    cmds.unloadPlugin(plugin_name, force=True)
    print("RELEASE_PACKAGE_OK", edition, package)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("package")
    parser.add_argument("edition", choices=("en", "zh-CN"))
    arguments = parser.parse_args()
    main(arguments.package, arguments.edition)
