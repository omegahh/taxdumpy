"""Tests for TaxDb class."""

import pickle
from unittest.mock import patch

import pytest

from taxdumpy import TaxDb, TaxDbError, TaxidError
from taxdumpy.basic import Node


class TestTaxDb:
    """Test the TaxDb class."""

    def test_taxdb_creation(self, sample_taxdump_dir):
        """Test creating a TaxDb instance."""
        taxdb = TaxDb(sample_taxdump_dir)
        assert isinstance(taxdb, TaxDb)
        assert taxdb._taxdump_dir == sample_taxdump_dir.resolve()
        assert not taxdb._fast

    def test_taxdb_fast_mode(self, fast_cache_dir):
        """Test creating TaxDb in fast mode."""
        taxdb = TaxDb(fast_cache_dir, fast=True)
        assert taxdb._fast is True

    def test_taxdb_length(self, sample_taxdb):
        """Test getting the number of nodes in TaxDb."""
        assert len(sample_taxdb) > 0
        # Should contain our sample nodes
        assert len(sample_taxdb) >= 10

    def test_taxdb_repr(self, sample_taxdb):
        """Test string representation of TaxDb."""
        repr_str = repr(sample_taxdb)
        assert "Taxdump (Dict) Database" in repr_str
        assert str(sample_taxdb._taxdump_dir) in repr_str

    def test_get_node_valid_taxid(self, sample_taxdb):
        """Test getting a valid node."""
        node = sample_taxdb.get_node(9606)  # Human
        assert isinstance(node, Node)
        assert node.taxid == 9606
        assert node.name == "Homo sapiens"
        assert node.rank == "species"

    def test_get_node_invalid_taxid(self, sample_taxdb):
        """Test getting a node with invalid taxid."""
        with pytest.raises(TaxidError):
            sample_taxdb.get_node(999999)

    def test_get_node_legacy_taxid(self, sample_taxdb):
        """Test getting a node with legacy (merged) taxid."""
        # 6043 should map to 6042 in our sample data
        node = sample_taxdb.get_node(6043)
        assert node.taxid == 6042
        assert "Demospongiae" in node.name

    def test_get_node_deleted_taxid(self, sample_taxdb):
        """Test getting a deleted taxid."""
        with pytest.raises(TaxidError):
            sample_taxdb.get_node(3451490)  # Deleted in our sample data

    def test_all_names_property(self, sample_taxdb):
        """Test the all_names cached property."""
        names = sample_taxdb.all_names
        assert isinstance(names, list)
        assert "Homo sapiens" in names
        assert "Methanobacterium bryantii" in names

    def test_name2taxid_property(self, sample_taxdb):
        """Test the name2taxid cached property."""
        name_map = sample_taxdb.name2taxid
        assert isinstance(name_map, dict)
        assert name_map["Homo sapiens"] == 9606
        assert name_map["Methanobacterium bryantii"] == 2161

    def test_delnodes_property(self, sample_taxdb):
        """Test the delnodes property."""
        del_nodes = sample_taxdb.delnodes
        assert isinstance(del_nodes, set)
        assert 3451490 in del_nodes
        assert 3451488 in del_nodes

    def test_max_taxid_strlen(self, sample_taxdb):
        """Test max_taxid_strlen property."""
        max_len = sample_taxdb.max_taxid_strlen
        assert isinstance(max_len, int)
        assert max_len > 0

    def test_max_rank_strlen(self, sample_taxdb):
        """Test max_rank_strlen property."""
        max_len = sample_taxdb.max_rank_strlen
        assert isinstance(max_len, int)
        assert max_len > 0

    def test_rapid_fuzz_search(self, sample_taxdb):
        """Test fuzzy name search."""
        results = sample_taxdb._rapid_fuzz("Homo sapiens", limit=5)
        assert isinstance(results, list)
        assert len(results) > 0

        # Check result format
        for result in results:
            assert "name" in result
            assert "taxid" in result
            assert "score" in result
            assert isinstance(result["score"], (int, float))

    def test_rapid_fuzz_search_with_typo(self, sample_taxdb):
        """Test fuzzy search with typos."""
        results = sample_taxdb._rapid_fuzz("Homo sapien", limit=5)  # Missing 's'
        assert len(results) > 0
        # Should still find "Homo sapiens"
        names = [r["name"] for r in results]
        assert any("Homo sapiens" in name for name in names)

    def test_rapid_fuzz_returns_all_taxids_for_duplicate_name(self, sample_taxdb):
        results = sample_taxdb._rapid_fuzz("Leishmania", limit=10)
        assert {result["taxid"] for result in results if result["name"] == "Leishmania"} == {5658, 38568}

    def test_rapid_fuzz_search_empty_query(self, sample_taxdb):
        """Test fuzzy search with empty query."""
        results = sample_taxdb._rapid_fuzz("", limit=5)
        assert isinstance(results, list)
        # Should return empty list for empty query
        assert len(results) == 0

    def test_missing_taxdump_files(self, temp_dir):
        """Test behavior with missing taxdump files."""
        # Create empty directory
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        with pytest.raises(TaxDbError):
            TaxDb(empty_dir)

    def test_pickle_loading(self, sample_taxdump_dir, temp_dir):
        """Test loading from pickle file."""
        # Create a TaxDb instance and dump it
        taxdb1 = TaxDb(sample_taxdump_dir)
        pickle_file = temp_dir / "test.pickle"
        taxdb1._pickle = pickle_file
        from taxdumpy.cache import atomic_pickle_dump

        atomic_pickle_dump(
            pickle_file,
            {
                "format_version": 1,
                "sources": taxdb1._source_signature,
                "nodes": taxdb1._taxid2nodes,
                "merged": taxdb1._old2news,
                "deleted": taxdb1.delnodes,
            },
        )

        # Create new instance that should load from pickle
        taxdb2 = TaxDb(sample_taxdump_dir)
        taxdb2._pickle = pickle_file

        # Force reload
        taxdb2._taxid2nodes, taxdb2._old2news, taxdb2._delnodes = taxdb2._load_cached_taxdump()

        # Should have same data
        assert len(taxdb1) == len(taxdb2)
        assert taxdb1.get_node(9606).name == taxdb2.get_node(9606).name

    def test_existing_pickle_is_deserialized_once(self, sample_taxdump_dir, temp_dir):
        """Loading an existing cache should not deserialize it as a probe first."""
        pickle_file = temp_dir / "taxdump.pickle"
        source_db = TaxDb(sample_taxdump_dir)
        source_db._pickle = pickle_file
        from taxdumpy.cache import atomic_pickle_dump

        atomic_pickle_dump(
            pickle_file,
            {
                "format_version": 1,
                "sources": source_db._source_signature,
                "nodes": source_db._taxid2nodes,
                "merged": source_db._old2news,
                "deleted": source_db.delnodes,
            },
        )

        with patch("taxdumpy.taxdb.pickle.load", wraps=pickle.load) as load:
            loaded_db = TaxDb(temp_dir)

        assert load.call_count == 1
        assert loaded_db.get_node(9606).name == "Homo sapiens"
