import pytest

from taxdumpy import TaxDb, TaxdumpFileError, TaxidError, Taxon, ValidationError, descendants
from taxdumpy.cli import main


def test_fast_cache_contains_only_selected_subtrees_and_ancestors(source_dir):
    db = TaxDb(source_dir)
    roots = [561, 562, 6043]  # overlapping subtrees and a merged ID
    expected = set()
    for root in roots:
        expected.update(Taxon(root, db).taxid_lineage)
        expected.update(descendants(db, root))
    selection = source_dir / "selected.txt"
    selection.write_text("561\n562\n6043\n")
    assert main(["cache", "-d", str(source_dir), "-f", str(selection)]) == 0
    fast = TaxDb(source_dir, fast=True)
    assert set(fast._taxid2nodes) == expected
    assert fast.get_node(6043).taxid == 6042
    assert 9606 not in expected


@pytest.mark.parametrize("ids", [[], [999999999], [3451490]])
def test_invalid_selection_preserves_previous_fast_cache(fast_cache_dir, ids):
    path = fast_cache_dir / "taxdump_fast.pickle"
    before = path.read_bytes()
    selection = fast_cache_dir / "selected.txt"
    selection.write_text("\n".join(map(str, ids)) + "\n")
    assert main(["cache", "-d", str(fast_cache_dir), "-f", str(selection)]) == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize("content", [None, b"invalid pickle"])
def test_unavailable_fast_cache_does_not_import_full_database(source_dir, content):
    path = source_dir / "taxdump_fast.pickle"
    (source_dir / "taxdump.pickle").unlink()
    if content is not None:
        path.write_bytes(content)
    with pytest.raises(TaxdumpFileError, match="Fast cache"):
        TaxDb(source_dir, fast=True)
    assert not (source_dir / "taxdump.pickle").exists()


def test_cli_unknown_selection_fails_without_creating_cache(source_dir):
    selection = source_dir / "selected.txt"
    selection.write_text("999999999\n")
    assert main(["cache", "-d", str(source_dir), "-f", str(selection)]) == 1
    assert not (source_dir / "taxdump_fast.pickle").exists()
