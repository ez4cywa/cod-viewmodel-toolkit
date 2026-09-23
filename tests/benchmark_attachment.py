"""Run with mayapy; optional real inputs, otherwise generated skinned meshes."""
import argparse
import cProfile
import pstats
import sys
import tempfile
import time
from pathlib import Path

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plug-ins"))
import viewmodel_weapon_toolkit as core


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hands")
    parser.add_argument("--weapon")
    parser.add_argument("--max-seconds", type=float)
    parser.add_argument("--max-setattr-calls", type=int)
    parser.add_argument("--legacy-weights", action="store_true")
    args = parser.parse_args()
    cmds.loadPlugin(core.__file__, quiet=True)
    if args.legacy_weights:
        from verify_bulk_skin_weights import legacy
        core._castplugin_module().utilitySetSkinWeights = legacy
    with tempfile.TemporaryDirectory(prefix="attachment_benchmark_") as directory:
        paths = []
        for name, supplied, joint in (("hands", args.hands, "tag_weapon"),
                                      ("weapon", args.weapon, "j_gun")):
            if supplied:
                paths.append(supplied)
                continue
            cmds.file(new=True, force=True)
            root = cmds.createNode("joint", name=joint)
            mesh = cmds.polyPlane(name=name, subdivisionsX=160, subdivisionsY=160)[0]
            cmds.skinCluster(root, mesh, toSelectedBones=True)
            path = str(Path(directory) / (name + ".cast"))
            with core._temporary_cast_export_settings():
                cmds.file(path, force=True, type=core.cast_translator_name(), exportAll=True)
            paths.append(path)
        profile = cProfile.Profile()
        start = time.perf_counter()
        profile.enable()
        result = core._build_single_attachment(*paths, core.AttachOptions(
            force_new_scene=True, export_cast=False))
        profile.disable()
        elapsed = time.perf_counter() - start
        assert result.translation == (0.0, 0.0, 0.0)
        assert cmds.ls(type="skinCluster")
        print("ATTACH_SECONDS %.4f" % elapsed)
        pstats.Stats(profile).sort_stats("cumtime").print_stats(25)
        calls = sum(entry.callcount for entry in profile.getstats()
                    if isinstance(entry.code, str) and "maya.cmds.setAttr" in entry.code)
        print("SETATTR_CALLS", calls)
        if args.max_setattr_calls is not None:
            assert calls <= args.max_setattr_calls, (calls, args.max_setattr_calls)
        if args.max_seconds is not None:
            assert elapsed < args.max_seconds, (elapsed, args.max_seconds)


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
