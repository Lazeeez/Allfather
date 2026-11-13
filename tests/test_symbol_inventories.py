import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_symbol_inventories import snapshot_inventory  # noqa: E402


def test_inventory_reads_complete_base_snapshot_without_gold(local_repo):
    cache, first, _ = local_repo
    inventory = snapshot_inventory(cache, "acme/pkg", first)
    assert inventory["collection_complete"]
    assert {unit["id"] for unit in inventory["symbols"]} == {
        "pkg/auth.py::Session",
        "pkg/auth.py::Session.login",
        "pkg/render.py::render_template",
    }
    assert inventory["colliding_ids"] == {} and inventory["parser_error_files"] == []
    assert len(inventory["files"]) == 2
    assert all(file["blob"] for file in inventory["files"])
