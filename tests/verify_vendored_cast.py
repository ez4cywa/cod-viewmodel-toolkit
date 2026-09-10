"""Static integrity checks for the bundled patched CAST v2.00 translator."""

import ast
import hashlib
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
CAST_DIR = ROOT / "third_party" / "cast"
CAST_MODULE = CAST_DIR / "cast.py"
CAST_PLUGIN = CAST_DIR / "castplugin.py"

CAST_MODULE_SHA256 = (
    "d1ff7fcb2a184f208b21be34485d1863834ae33811078a28a2ccf6ff61f2c577"
)
CAST_PLUGIN_SHA256 = (
    "27f503383f92d55420f40d91789c3843d0f3efdded1fd681e2054a56bf451712"
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
        raise RuntimeError("Bundled cast.py differs from upstream v2.00")
    if _sha256(CAST_PLUGIN) != CAST_PLUGIN_SHA256:
        raise RuntimeError("Bundled patched castplugin.py changed unexpectedly")

    plugin_source = CAST_PLUGIN.read_text(encoding="utf-8")
    required_markers = (
        'version = "2.00"',
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
