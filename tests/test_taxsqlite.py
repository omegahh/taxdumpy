"""Tests for TaxSQLite class."""

import pytest
import sqlite3
from pathlib import Path

from taxdumpy import TaxSQLite, TaxidError
from taxdumpy.basic import Node


class TestTaxSQLite:
    """Test the TaxSQLite class."""

    def test_taxsqlite_creation(self, sample_taxdump_dir):
        """Test creating a TaxSQLite instance."""
        with TaxSQLite(sample_taxdump_dir) as taxsqlite:
            assert isinstance(taxsqlite, TaxSQLite)
            assert taxsqlite._taxdump_dir == sample_taxdump_dir.resolve()
            assert taxsqlite._db_path.exists()

    def test_context_manager(self, sample_taxdump_dir):
        """Test TaxSQLite as context manager."""
        with TaxSQLite(sample_taxdump_dir) as taxsqlite:
            # Should be able to use normally
            node = taxsqlite.get_node(9606)
            assert node.name == "Homo sapiens"

        # Connection should be closed after context
        # Note: We can't easily test this without accessing private members

    def test_taxsqlite_repr(self, sample_taxsqlite):
        """Test string representation of TaxSQLite."""
        repr_str = repr(sample_taxsqlite)
        assert "Taxdump (SQLite) Database" in repr_str
        assert "Imported nodes:" in repr_str
        assert "Legacy nodes:" in repr_str
        assert "Deleted nodes:" in repr_str

    def test_get_node_valid_taxid(self, sample_taxsqlite):
        """Test getting a valid node."""
        node = sample_taxsqlite.get_node(9606)  # Human
        assert isinstance(node, Node)
        assert node.taxid == 9606
        assert node.name == "Homo sapiens"
        assert node.rank == "species"

    def test_get_node_invalid_taxid(self, sample_taxsqlite):
        """Test getting a node with invalid taxid."""
        with pytest.raises(TaxidError):
            sample_taxsqlite.get_node(999999)

    def test_get_node_legacy_taxid(self, sample_taxsqlite):
        """Test getting a node with legacy (merged) taxid."""
        # 6043 should map to 6042 in our sample data
        node = sample_taxsqlite.get_node(6043)
        assert node.taxid == 6042
        assert "Demospongiae" in node.name

    def test_get_node_deleted_taxid(self, sample_taxsqlite):
        """Test getting a deleted taxid."""
        with pytest.raises(TaxidError):
            sample_taxsqlite.get_node(3451490)  # Deleted in our sample data

    def test_delnodes_property(self, sample_taxsqlite):
        """Test the delnodes property."""
        del_nodes = sample_taxsqlite.delnodes
        assert isinstance(del_nodes, set)
        assert 3451490 in del_nodes
        assert 3451488 in del_nodes

    def test_fuzzy_search(self, sample_taxsqlite):
        """Test fuzzy search functionality."""
        # This should print results, not return them
        # We can't easily test the output without capturing stdout
        sample_taxsqlite.fuzzy_search("Homo sapiens")
        sample_taxsqlite.fuzzy_search("human")
        sample_taxsqlite.fuzzy_search("Methanobacterium")

    def test_fuzzy_search_with_typo(self, sample_taxsqlite):
        """Test fuzzy search with typos."""
        # Should handle typos gracefully
        sample_taxsqlite.fuzzy_search("Homo sapien")  # Missing 's'
        sample_taxsqlite.fuzzy_search("Eschericia")  # Typo in genus

    def test_fuzzy_search_empty_query(self, sample_taxsqlite):
        """Test fuzzy search with empty query."""
        sample_taxsqlite.fuzzy_search("")  # Should handle gracefully

    def test_database_tables_exist(self, sample_taxsqlite):
        """Test that required database tables exist."""
        conn = sample_taxsqlite._conn

        # Check that tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()

        table_names = [table[0] for table in tables]
        assert "nodes" in table_names
        assert "names" in table_names
        assert "merged" in table_names

    def test_database_indexes_exist(self, sample_taxsqlite):
        """Test that database indexes exist."""
        conn = sample_taxsqlite._conn

        # Check that indexes exist
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        ).fetchall()

        index_names = [idx[0] for idx in indexes]
        assert any("names" in idx for idx in index_names)
        assert any("nodes" in idx for idx in index_names)

    def test_database_data_integrity(self, sample_taxsqlite):
        """Test basic data integrity."""
        conn = sample_taxsqlite._conn

        # Check that we have data in tables
        node_count = conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        name_count = conn.execute("SELECT COUNT(*) FROM names").fetchone()[0]

        assert node_count > 0
        assert name_count > 0

        # Check that human exists in both tables
        human_node = conn.execute("SELECT * FROM nodes WHERE taxid = 9606").fetchone()
        assert human_node is not None

        human_names = conn.execute("SELECT * FROM names WHERE taxid = 9606").fetchall()
        assert len(human_names) > 0

    def test_scientific_name_retrieval(self, sample_taxsqlite):
        """Test retrieving scientific names."""
        conn = sample_taxsqlite._conn

        # Get scientific name for human
        result = conn.execute(
            "SELECT name FROM names WHERE taxid = 9606 AND name_class = 'scientific name'"
        ).fetchone()

        assert result is not None
        assert result[0] == "Homo sapiens"

    def test_close_method(self, sample_taxdump_dir):
        """Test explicit close method."""
        taxsqlite = TaxSQLite(sample_taxdump_dir)

        # Should work normally
        node = taxsqlite.get_node(9606)
        assert node.name == "Homo sapiens"

        # Close explicitly
        taxsqlite.close()

        # Should raise error after closing
        with pytest.raises(sqlite3.ProgrammingError):
            taxsqlite.get_node(9606)

    def test_rebuild_database(self, temp_dir):
        """Test rebuilding database from scratch."""
        # Create sample taxdump files in temp dir
        nodes_content = """1\t|\t1\t|\tno rank\t|\t\t|\t8\t|\t0\t|\t1\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|\t\t|
9606\t|\t9605\t|\tspecies\t|\tHS\t|\t0\t|\t1\t|\t11\t|\t0\t|\t0\t|\t0\t|\t0\t|\t0\t|\t\t|
"""
        names_content = """1\t|\tcellular organisms\t|\t\t|\tscientific name\t|
9606\t|\tHomo sapiens\t|\t\t|\tscientific name\t|
"""
        merged_content = ""
        delnodes_content = ""
        division_content = """11\t|\tMammals\t|\tMAM\t|\t\t|
"""

        (temp_dir / "nodes.dmp").write_text(nodes_content)
        (temp_dir / "names.dmp").write_text(names_content)
        (temp_dir / "merged.dmp").write_text(merged_content)
        (temp_dir / "delnodes.dmp").write_text(delnodes_content)
        (temp_dir / "division.dmp").write_text(division_content)

        # Create TaxSQLite instance - should build database
        with TaxSQLite(temp_dir) as taxsqlite:
            node = taxsqlite.get_node(9606)
            assert node.name == "Homo sapiens"
