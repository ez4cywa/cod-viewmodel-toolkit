"""Install a release ZIP in an isolated BLENDER_USER_SCRIPTS directory.

Run in factory/background Blender, passing the ZIP after --.
"""

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import tempfile

import bpy
import addon_utils

ROOT = Path(__file__).resolve().parents[1]
archive = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
scripts = Path(os.environ["BLENDER_USER_SCRIPTS"]).resolve()
assert bpy.ops.preferences.addon_install(filepath=str(archive), overwrite=False) == {"FINISHED"}
bpy.utils.refresh_script_paths()
addon_utils.enable("cod_viewmodel_toolkit", default_set=False, persistent=False)
import cod_viewmodel_toolkit
from cod_viewmodel_toolkit import core, exporting
from cod_viewmodel_toolkit.backend import backend

assert Path(cod_viewmodel_toolkit.__file__).resolve().is_relative_to(scripts)
assert Path(backend().importer.__file__).parent.name == "vendor_cast"
assert cod_viewmodel_toolkit.bl_info["version"] == (3, 3, 0)
assert hasattr(bpy.types.Scene, "cod_vwt")
sys.path.insert(0, str(ROOT / "tests"))
from blender_fixtures import model, animation

with tempfile.TemporaryDirectory(prefix="cod_blender_package_") as temporary:
    folder = Path(temporary)
    hands, weapon, clip = [folder / (name + ".cast") for name in ("hands", "weapon", "clip")]
    model(backend().cast, hands)
    model(backend().cast, weapon, hands=False)
    animation(backend().cast, clip)
    rig = core.build(hands, weapon, left=str(clip))
    assert core.verify(rig)["valid"]
    with redirect_stdout(io.StringIO()):
        result = exporting.export(rig, exporting.ExportOptions(
            directory=str(folder / "out"), fbx=True, smd=True))
    assert len(result["outputs"]) == 4
addon_utils.disable("cod_viewmodel_toolkit", default_set=False)
assert not hasattr(bpy.types.Scene, "cod_vwt")
print("BLENDER_RELEASE_INSTALL_OK", archive.name)
