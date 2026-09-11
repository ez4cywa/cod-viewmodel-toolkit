"""Check exact pinned Blender backend bytes without importing Blender."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASHES = {
    "__init__.py": "27e7d89379e7bee8b8e538f281435aca73b838405c3ea82e5cf6cde7b1d269a0",
    "import_cast.py": "5ca3055e4933aa92178a1bf159f6cb219a27f2822568c495efbdf8b77590c6d0",
    "export_cast.py": "d62c9b2698e3e0f6619311fdacf1959105f25c36a48d9407bb2bd3fbca1e54c1",
    "shared_cast.py": "8f65cc1a4ee055127ecd202c65a10db2e3ceb3ba8d9273ca08888d3d4b9645ed",
}

for name, expected in HASHES.items():
    actual = hashlib.sha256((ROOT / "third_party/cast_blender" / name).read_bytes()).hexdigest()
    assert actual == expected, (name, actual)
print("VENDORED_BLENDER_CAST_OK")
