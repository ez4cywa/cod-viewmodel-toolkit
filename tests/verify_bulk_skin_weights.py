"""Mayapy: compare bulk CAST import against the previous per-vertex writer."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import maya.standalone
import maya.cmds as cmds
if not hasattr(cmds, "pluginInfo"):
    maya.standalone.initialize(name="python")
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plug-ins"))
import viewmodel_weapon_toolkit as core


def legacy(cluster, paths, bones, vertices, slots, bone_buffer, weights):
    remap = {paths.index(bone): index for index, bone in enumerate(bones)}
    for vertex in range(vertices):
        values = [0.0] * len(bones)
        if len(bones) == 1:
            values[0] = 1.0
            attribute = ".weights[0]"
        else:
            for slot in range(slots):
                source = vertex * slots + slot
                values[remap[bone_buffer[source]]] += weights[source]
            attribute = ".weights[0:%d]" % (len(bones) - 1)
        cmds.setAttr(cluster.name() + (".weightList[%d]" % vertex) + attribute, *values)


def snapshot():
    result = {}
    for name in cmds.ls(type="skinCluster"):
        select = om.MSelectionList()
        select.add(name)
        skin = oma.MFnSkinCluster(select.getDependNode(0))
        shape = skin.getPathAtIndex(0)
        mesh = om.MFnMesh(shape)
        component = om.MFnSingleIndexedComponent()
        vertices = component.create(om.MFn.kMeshVertComponent)
        component.setCompleteData(mesh.numVertices)
        weights, count = skin.getWeights(shape, vertices)
        # Influence creation order can differ between imports; compare by bone name.
        by_bone = {bone.partialPathName(): tuple(weights[i::count])
                   for i, bone in enumerate(skin.influenceObjects())}
        result[shape.partialPathName()] = (by_bone, cmds.getAttr(name + ".skinningMethod"),
                                          tuple(tuple(p) for p in mesh.getPoints(om.MSpace.kWorld)))
    return result


def main():
    cmds.loadPlugin(core.__file__, quiet=True)
    backend = core._castplugin_module()
    for real_path in sys.argv[1:]:
        snapshots = []
        for writer in (legacy, backend.utilitySetSkinWeights):
            cmds.file(new=True, force=True)
            with patch.object(backend, "utilitySetSkinWeights", writer):
                core.import_cast(real_path, "fixture")
            snapshots.append(snapshot())
        assert snapshots[0] == snapshots[1], "Real asset weights changed: " + real_path
        print("REAL_ASSET_WEIGHTS_OK", Path(real_path).name)
    with tempfile.TemporaryDirectory(prefix="bulk_skin_regression_") as temporary:
        path = str(Path(temporary) / "model.cast")
        for rigid in (False, True):
            cmds.file(new=True, force=True)
            bones = [cmds.createNode("joint", name="bone_%d" % i) for i in range(1 if rigid else 3)]
            mesh = cmds.polyPlane(subdivisionsX=300, subdivisionsY=300)[0]
            cmds.skinCluster(bones, mesh, toSelectedBones=True)
            with core._temporary_cast_export_settings():
                cmds.file(path, force=True, type=core.cast_translator_name(), exportAll=True)
            document = backend.Cast.load(path)
            model = next(child for child in document.Roots()[0].childNodes
                         if isinstance(child, backend.Model))
            mesh_record = model.Meshes()[0]
            count = mesh_record.VertexCount()
            mesh_record.SetSkinningMethod("quaternion")
            mesh_record.SetMaximumWeightInfluence(1 if rigid else 4)
            # Duplicated indices, zero weights and deliberately non-normalized sums.
            mesh_record.SetVertexWeightBoneBuffer(([0] if rigid else [2, 0, 2, 1]) * count)
            mesh_record.SetVertexWeightValueBuffer(([0.0] if rigid else [0.1, 0.4, 0.2, 0.0]) * count)
            document.save(path)
            snapshots = []
            for writer in (legacy, backend.utilitySetSkinWeights):
                cmds.file(new=True, force=True)
                with patch.object(backend, "utilitySetSkinWeights", writer):
                    core.import_cast(path, "fixture")
                # Also compare deformation after a joint transform, not only weights.
                cmds.setAttr("bone_0.ty", 2)
                snapshots.append(snapshot())
            assert snapshots[0] == snapshots[1], "Bulk import changed weights/deformation"
            print("BULK_SKIN_WEIGHTS_OK", "rigid" if rigid else "multi-influence/chunk-boundary")


if __name__ == "__main__":
    try:
        main()
    finally:
        maya.standalone.uninitialize()
