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
    assert db.build_fast_cache(roots) == len(expected)
    fast = TaxDb(source_dir, fast=True)
    assert set(fast._taxid2nodes) == expected
    assert fast.get_node(6043).taxid == 6042
    assert 9606 not in expected


@pytest.mark.parametrize("ids,error", [([], ValidationError), ([999999999], TaxidError), ([3451490], TaxidError)])
def test_invalid_selection_preserves_previous_fast_cache(fast_cache_dir, ids, error):
    path = fast_cache_dir / "taxdump_fast.pickle"
    before = path.read_bytes()
    with pytest.raises(error):
        TaxDb(fast_cache_dir).build_fast_cache(ids)
    assert path.read_bytes() == before


@pytest.mark.parametrize("content", [None, b"invalid pickle"])
def test_unavailable_fast_cache_does_not_import_full_database(source_dir, content):
    path = source_dir / "taxdump_fast.pickle"
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
