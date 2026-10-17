"""Host-free checks for root CAST names and append-only collision suffixes."""

from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_standalone_export_ui import UICommands, load_core


class CastImportNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = load_core(UICommands())

    def plan(self, names, existing=()):
        return self.core._cast_import_root_names(list(enumerate(names)), existing)

    def test_first_import_preserves_names(self):
        self.assertEqual(self.plan(["Joints", "j_gun", "mesh_LOD0"]),
                         {0: "Joints", 1: "j_gun", 2: "mesh_LOD0"})

    def test_duplicate_import_appends_digits(self):
        self.assertEqual(self.plan(["Joints", "j_gun", "mesh_LOD0"],
                                   ["Joints", "j_gun", "mesh_LOD0"]),
                         {0: "Joints1", 1: "j_gun1", 2: "mesh_LOD01"})

    def test_existing_numeric_suffix_is_not_incremented(self):
        self.assertEqual(self.plan(["bone7"], ["bone7", "bone71"]), {0: "bone72"})

    def test_collisions_do_not_steal_other_original_names(self):
        self.assertEqual(self.plan(["bone", "bone1"], ["bone"]),
                         {0: "bone2", 1: "bone1"})

    def test_duplicate_source_leaf_names_stay_distinct(self):
        self.assertEqual(self.plan(["bone", "bone", "bone1"]),
                         {0: "bone", 1: "bone2", 2: "bone1"})

    def test_old_scene_names_are_never_modified(self):
        existing = ["j_gun", "j_gun1", "j_gun3"]
        self.assertEqual(self.plan(["j_gun"], existing), {0: "j_gun2"})
        self.assertEqual(existing, ["j_gun", "j_gun1", "j_gun3"])

    def test_scene_identity_query_supplies_explicit_nodes(self):
        paths = ["|existing", "material"]
        ls = Mock(side_effect=[paths, ["uuid-a", "uuid-b"]])
        with patch.object(self.core, "cmds", SimpleNamespace(ls=ls)):
            self.assertEqual(self.core._cast_scene_uuids(), {"uuid-a", "uuid-b"})
        self.assertEqual(ls.call_args_list, [call(long=True), call(paths, uuid=True)])


if __name__ == "__main__":
    unittest.main()
