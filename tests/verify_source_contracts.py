"""Parse project sources without importing hosts or writing bytecode.

Maya runtime files additionally target Python 3.7 syntax. This verifies the
language contract; actual Maya API compatibility still requires host tests.
"""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORIES = (
    "plug-ins", "scripts", "tests", "third_party/cast",
    "third_party/cast_blender", "blender/cod_viewmodel_toolkit",
)


def main():
    paths = sorted(path for directory in SOURCE_DIRECTORIES
                   for path in (ROOT / directory).glob("*.py"))
    maya_paths = set((ROOT / "plug-ins").glob("*.py"))
    maya_paths.update((ROOT / "third_party/cast").glob("*.py"))
    failures = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT).as_posix()
        try:
            # compile catches errors such as return outside a function that
            # ast.parse alone accepts, without importing Maya or Blender.
            compile(source, relative, "exec")
            if path in maya_paths:
                ast.parse(source, filename=relative, feature_version=(3, 7))
        except SyntaxError as exc:
            failures.append("%s:%s: %s" % (relative, exc.lineno, exc.msg))
    if failures:
        raise RuntimeError("Source compatibility checks failed:\n" + "\n".join(failures))
    print("SOURCE_CONTRACTS_OK: %d files; %d Maya files parse as Python 3.7"
          % (len(paths), len(maya_paths)))


if __name__ == "__main__":
    main()
