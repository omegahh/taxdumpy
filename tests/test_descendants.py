"""Tests for subtree traversal: descendants, descendant_nodes, children index."""

from pathlib import Path

import pytest

from taxdumpy import TaxDb, TaxSQLite
from taxdumpy.basic import TaxidError, ValidationError
from taxdumpy.functions import build_children_index, descendant_nodes, descendants


@pytest.fixture(params=["dict", "sqlite"])
def db(request, sample_taxdump_dir: Path):
    """Every test runs against both backends, which must agree exactly."""
    factory = TaxDb if request.param == "dict" else TaxSQLite
    instance = factory(sample_taxdump_dir)
    yield instance
    instance.close()


class TestDescendants:
    def test_genus_returns_its_species(self, db):
        # 561 = Escherichia, 562 = E. coli
        assert 562 in descendants(db, 561)

    def test_excludes_self(self, db):
        assert 561 not in descendants(db, 561)

    def test_leaf_returns_empty(self, db):
        assert descendants(db, 562) == []

    def test_root_returns_everything_else(self, db):
        result = descendants(db, 1)
        assert len(result) == len(db) - 1  # all nodes but root itself
        assert 1 not in result

    def test_is_transitive_not_just_children(self, db):
        """A grandchild must appear, not only direct children."""
        # 2 = Bacteria; 562 sits several ranks below it.
        result = descendants(db, 2)
        assert 562 in result
        assert 561 in result
        assert len(result) > len(descendants(db, 2, max_depth=1))

    def test_accepts_string_taxid(self, db):
        assert descendants(db, "561") == descendants(db, 561)

    def test_no_duplicates(self, db):
        result = descendants(db, 1)
        assert len(result) == len(set(result))

    def test_deleted_taxids_excluded(self, db):
        result = set(descendants(db, 1))
        assert not (result & db.delnodes)

    def test_breadth_first_order(self, db):
        """Shallower nodes precede deeper ones."""
        result = descendants(db, 2)
        direct = descendants(db, 2, max_depth=1)
        assert result[: len(direct)] == direct

    def test_matches_lineage_definition(self, db):
        """Ground truth: x is a descendant of t iff t is in x's lineage."""
        from taxdumpy.taxon import Taxon

        target = 561
        expected = {t for t in descendants(db, 1) if target in Taxon(t, db).taxid_lineage and t != target}
        assert set(descendants(db, target)) == expected


class TestMaxDepth:
    def test_depth_one_gives_direct_children_only(self, db):
        direct = descendants(db, 561, max_depth=1)
        for child in direct:
            assert db.get_node(child).parent == 561

    def test_deeper_is_superset(self, db):
        d1 = set(descendants(db, 2, max_depth=1))
        d2 = set(descendants(db, 2, max_depth=2))
        assert d1 <= d2

    def test_large_depth_equals_unlimited(self, db):
        assert descendants(db, 2, max_depth=10_000) == descendants(db, 2)

    @pytest.mark.parametrize("bad", [0, -1, -5])
    def test_rejects_non_positive(self, db, bad):
        with pytest.raises(ValidationError):
            descendants(db, 1, max_depth=bad)

    @pytest.mark.parametrize("bad", ["2", 1.5, True])
    def test_rejects_wrong_type(self, db, bad):
        with pytest.raises(ValidationError):
            descendants(db, 1, max_depth=bad)


class TestErrors:
    def test_unknown_taxid(self, db):
        with pytest.raises(TaxidError):
            descendants(db, 999_999_999)

    @pytest.mark.parametrize("bad", ["", "abc", 0, -1, None])
    def test_invalid_taxid(self, db, bad):
        with pytest.raises(ValidationError):
            descendants(db, bad)


class TestBackendConsistency:
    def test_backends_agree(self, sample_taxdump_dir: Path):
        with TaxDb(sample_taxdump_dir) as a, TaxSQLite(sample_taxdump_dir) as b:
            for taxid in (1, 2, 561, 562, 9606):
                assert sorted(descendants(a, taxid)) == sorted(descendants(b, taxid))
                assert sorted(descendants(a, taxid, max_depth=2)) == sorted(descendants(b, taxid, max_depth=2))


class TestChildrenIndex:
    def test_cached_across_calls(self, db):
        assert build_children_index(db) is build_children_index(db)

    def test_index_excludes_root_self_loop(self, db):
        # root's parent is itself; that must not make root its own child.
        assert 1 not in build_children_index(db).get(1, [])


class TestDescendantNodes:
    def test_returns_nodes_matching_taxids(self, db):
        nodes = descendant_nodes(db, 561)
        assert [n.taxid for n in nodes] == descendants(db, 561)
        assert all(n.rank for n in nodes)

    def test_respects_max_depth(self, db):
        assert len(descendant_nodes(db, 2, max_depth=1)) == len(descendants(db, 2, max_depth=1))
