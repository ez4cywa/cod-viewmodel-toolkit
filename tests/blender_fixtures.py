"""Small redistributable synthetic CAST inputs, independent of Maya."""


def model(cast, path, hands=True, reference_offset=0):
    document = cast.Cast()
    asset = document.CreateRoot().CreateModel()
    asset.SetName("Hands" if hands else "Weapon")
    skeleton = asset.CreateSkeleton()
    records = [
        ("tag_origin", -1, (0, 0, 0)),
        ("j_gun", 0, (0, 0, 0)),
        ("tag_weapon", 1, (0, 0, 2)),
        ("j_wrist_le", 0, (-4, 0, 0)),
        ("tag_weapon_left", 3, (0, 0, 2 + reference_offset)),
        ("j_wrist_ri", 0, (4, 0, 0)),
        ("tag_weapon_right", 5, (0, 0, 2 + reference_offset)),
    ] if hands else [
        ("j_gun", -1, (1, 0, 0)), ("j_slide", 0, (0, 0, 1))]
    for name, parent, position in records:
        bone = skeleton.CreateBone()
        bone.SetName(name)
        bone.SetParentIndex(parent)
        bone.SetLocalPosition(position)
        bone.SetLocalRotation((0, 0, 0, 1))
        bone.SetScale((1, 1, 1))
    mesh = asset.CreateMesh()
    mesh.SetName("hands_mesh" if hands else "weapon_mesh")
    mesh.SetVertexPositionBuffer(((0, 0, 0), (1, 0, 0), (0, 1, 0)))
    mesh.SetVertexNormalBuffer(((0, 0, 1),) * 3)
    mesh.SetFaceBuffer((0, 1, 2))
    mesh.SetUVLayerCount(1)
    mesh.SetVertexUVLayerBuffer(0, ((0, 0), (1, 0), (0, 1)))
    mesh.SetColorLayerCount(0)
    mesh.SetMaximumWeightInfluence(1)
    mesh.SetVertexWeightBoneBuffer((0, 0, 0))
    mesh.SetVertexWeightValueBuffer((1, 1, 1))
    mesh.SetSkinningMethod("quaternion")
    document.save(str(path))


def animation(cast, path, side="left", end=3, fps=30, amount=3):
    document = cast.Cast()
    animation = document.CreateRoot().CreateAnimation()
    animation.SetFramerate(fps)
    animation.SetName(side)
    animation.SetLooping(False)
    for name, prop, start, finish in (
            ("j_wrist_le", "tx", -4, -4 - amount if side == "left" else -4),
            ("j_wrist_ri", "tx", 4, 4 + amount if side == "right" else 4),
            ("j_gun", "tx", 0, amount / 2),
            ("j_slide", "tz", 1, 1 + amount)):
        curve = animation.CreateCurve()
        curve.SetNodeName(name)
        curve.SetKeyPropertyName(prop)
        curve.SetKeyFrameBuffer([0, end] if end else [0])
        curve.SetFloatKeyValueBuffer([start, finish] if end else [finish])
        curve.SetMode("absolute")
    notification = animation.CreateNotification()
    notification.SetName("fire")
    notification.SetKeyFrameBuffer([end])
    document.save(str(path))
