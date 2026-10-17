"""Static integrity checks for the bundled patched CAST v2.01 translator."""

import ast
import hashlib
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAST_DIR = ROOT / "third_party" / "cast"
CAST_MODULE = CAST_DIR / "cast.py"
CAST_PLUGIN = CAST_DIR / "castplugin.py"

CAST_MODULE_SHA256 = (
    "633ab934360aeb04e74eb72e9ad014b5bb8d56acbe452ca1fc4f0166b46231c6"
)
CAST_PLUGIN_SHA256 = (
    "bcf5d84ff772d18dc56e6b4af84daf06c7e44c9ea13c44c9dcbb2e02092da656"
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_as_python37(source, path):
    try:
        ast.parse(source, filename=str(path), feature_version=(3, 7))
    except TypeError:
        # Python 3.7 itself predates ast.parse(feature_version=...). Its native
        # parser is already the compatibility target in that environment.
        ast.parse(source, filename=str(path))


def main():
    for path in (CAST_MODULE, CAST_PLUGIN):
        source = path.read_text(encoding="utf-8")
        _parse_as_python37(source, path)

    if _sha256(CAST_MODULE) != CAST_MODULE_SHA256:
        raise RuntimeError("Bundled patched cast.py changed unexpectedly")
    if _sha256(CAST_PLUGIN) != CAST_PLUGIN_SHA256:
        raise RuntimeError("Bundled patched castplugin.py changed unexpectedly")

    plugin_source = CAST_PLUGIN.read_text(encoding="utf-8")
    required_markers = (
        'version = "2.01"',
        'def utilityOperationOptions(options=None, runtime=None):',
        'def utilityAnimationTargets(targets=None):',
        'def utilityNamespaceName(name):',
        'def utilityNewShadingNode(nodeType, name=None, **options):',
        'if jointPathName in uniqueBones:',
        'uniqueBones[jointDagPath.fullPathName()][7]',
        'meshNode.SetSkinningMethod(',
        'type=fileTranslatorName',
        "def utilityApplyTranslatorOptions(optionString, supportedNames):",
        'if cmds.about(batch=True):',
        'missingUVs = {}',
        '("exportModel", "exportAnim", "bakeKeyframes")',
        '"importIK", "importConstraints", "importAtTime",',
    )
    missing = [marker for marker in required_markers
               if marker not in plugin_source]
    if missing:
        raise RuntimeError("Bundled CAST patches are incomplete: %r" % missing)

    forbidden = (CAST_DIR / "cast.cfg", CAST_DIR / "castpluginoptions.mel")
    present = [str(path.name) for path in forbidden if path.exists()]
    if present:
        raise RuntimeError("Unexpected CAST user/legacy files: %r" % present)

    print("VENDORED_CAST_VERIFICATION_OK")


if __name__ == "__main__":
    main()
