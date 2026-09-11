"""Stable quaternion-to-Euler conversion at FBX's mandatory XYZ seam.

Blender's float quaternion conversion can amplify error near a 90-degree
pitch (common in CoD rest skeletons). Compute that conversion in double
precision without changing the Blender installation or the source rig.
"""

from contextlib import contextmanager
import math

from mathutils import Euler


def stable_xyz(quaternion, compatible=None):
    w, x, y, z = map(float, quaternion)
    length = math.sqrt(w*w + x*x + y*y + z*z)
    w, x, y, z = (value / length for value in (w, x, y, z))
    m00, m10 = 1 - 2*(y*y + z*z), 2*(x*y + w*z)
    m20, m21, m22 = 2*(x*z - w*y), 2*(y*z + w*x), 1 - 2*(x*x + y*y)
    cosine = math.hypot(m00, m10)
    pitch = math.atan2(-m20, cosine)
    if cosine > 1e-7:
        roll, yaw = math.atan2(m21, m22), math.atan2(m10, m00)
    else:
        roll = math.atan2(2*(w*x - y*z), 1 - 2*(x*x + z*z))
        yaw = 0.0
    result = Euler((roll, pitch, yaw), "XYZ")
    if compatible is not None:
        result.make_compatible(compatible)
    return result


@contextmanager
def stable_fbx_rotation():
    from io_scene_fbx.fbx_utils import ObjectWrapper
    original = ObjectWrapper.fbx_object_tx

    def transforms(self, scene_data, rest=False, rot_euler_compat=None):
        matrix = self.fbx_object_matrix(scene_data, rest=rest)
        location, rotation, scale = matrix.decompose()
        return (location, stable_xyz(rotation, rot_euler_compat), scale,
                matrix, rotation.to_matrix())

    ObjectWrapper.fbx_object_tx = transforms
    try:
        yield
    finally:
        ObjectWrapper.fbx_object_tx = original
