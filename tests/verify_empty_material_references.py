"""Host-free CAST optional material contracts using real binary node round trips."""

import importlib.util
import io
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "cast_material_contract", ROOT / "third_party/cast/cast.py")
cast = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cast)


def binary(node):
    stream = io.BytesIO()
    node.save(stream)
    return stream.getvalue()


def round_trip(node):
    return cast.CastNode.load(io.BytesIO(binary(node)))


class MaterialReferences(unittest.TestCase):
    def nodes(self):
        for node_type in (cast.Mesh, cast.Hair):
            model = cast.Model()
            yield model, model.CreateChild(node_type())

    def test_missing_optional_reference(self):
        for model, node in self.nodes():
            with self.subTest(node=type(node).__name__):
                self.assertIsNone(node.Material())
                self.assertIsNone(round_trip(model).childNodes[0].Material())

    def test_empty_reference_round_trip_and_read_does_not_mutate(self):
        for model, node in self.nodes():
            with self.subTest(node=type(node).__name__):
                node.CreateProperty("m", "l").values = []
                loaded = round_trip(model)
                child = loaded.childNodes[0]
                prop = child.properties["m"]
                self.assertEqual(prop.values, ())
                before = binary(loaded)
                self.assertIsNone(child.Material())
                self.assertIs(child.properties["m"], prop)
                self.assertEqual(child.properties["m"].values, ())
                self.assertEqual(binary(loaded), before)

    def test_empty_in_memory_list_and_tuple(self):
        for model, node in self.nodes():
            for values in ([], ()):
                with self.subTest(node=type(node).__name__, values=values):
                    node.CreateProperty("m", "l").values = values
                    self.assertIsNone(node.Material())

    def test_valid_reference_identity_and_round_trip(self):
        for model, node in self.nodes():
            with self.subTest(node=type(node).__name__):
                material = model.CreateMaterial()
                node.SetMaterial(material.Hash())
                self.assertIs(node.Material(), material)
                loaded = round_trip(model)
                self.assertIs(loaded.childNodes[0].Material(), loaded.Materials()[0])

    def test_unresolved_and_zero_hash_keep_none(self):
        for model, node in self.nodes():
            for value in (0, 0xFFFFFFFFFFFFFFFF):
                with self.subTest(node=type(node).__name__, value=value):
                    node.SetMaterial(value)
                    self.assertIsNone(node.Material())
                    self.assertIsNone(round_trip(model).childNodes[0].Material())

    def test_multiple_references_still_use_first_value(self):
        for model, node in self.nodes():
            with self.subTest(node=type(node).__name__):
                first, second = model.CreateMaterial(), model.CreateMaterial()
                prop = node.CreateProperty("m", "l")
                prop.values = [first.Hash(), second.Hash()]
                self.assertIs(node.Material(), first)
                prop.values = [0xFFFFFFFFFFFFFFFF, second.Hash()]
                self.assertIsNone(node.Material())

    def test_existing_wrong_target_type_behavior_is_unchanged(self):
        for model, node in self.nodes():
            with self.subTest(node=type(node).__name__):
                skeleton = model.CreateSkeleton()
                node.SetMaterial(skeleton.Hash())
                self.assertIs(node.Material(), skeleton)

    def test_nonempty_orphan_reference_still_exposes_invalid_parent(self):
        for node_type in (cast.Mesh, cast.Hair):
            with self.subTest(node=node_type.__name__):
                node = node_type()
                node.SetMaterial(1)
                with self.assertRaises(AttributeError):
                    node.Material()

    def test_other_empty_properties_are_not_globally_normalized(self):
        node = cast.Mesh()
        node.CreateProperty("ul", "b").values = ()
        with self.assertRaises(IndexError):
            node.UVLayerCount()


if __name__ == "__main__":
    unittest.main()
