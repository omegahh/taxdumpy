"""Integration tests for taxdumpy package."""

import pytest

from taxdumpy import TaxDb, Taxon, TaxSQLite, upper_rank_id
from taxdumpy.cli import main


@pytest.mark.integration
class TestIntegration:
    """Integration tests that test components working together."""

    def test_taxdb_to_taxsqlite_consistency(self, sample_taxdb, sample_taxsqlite):
        """Test that TaxDb and TaxSQLite return consistent results."""
        for taxid in [9606, 2161, 7868, 2, 1]:
            assert sample_taxdb.get_node(taxid) == sample_taxsqlite.get_node(taxid)

    def test_taxon_with_both_backends(self, sample_taxdb, sample_taxsqlite):
        """Test Taxon class with both database backends."""
        taxon_taxdb = Taxon(9606, sample_taxdb)
        taxon_taxsqlite = Taxon(9606, sample_taxsqlite)

        assert taxon_taxdb.taxid == taxon_taxsqlite.taxid
        assert taxon_taxdb.name == taxon_taxsqlite.name
        assert taxon_taxdb.rank == taxon_taxsqlite.rank
        assert taxon_taxdb.is_legacy == taxon_taxsqlite.is_legacy
        assert taxon_taxdb.lineage == taxon_taxsqlite.lineage
        assert taxon_taxdb.taxid_lineage == taxon_taxsqlite.taxid_lineage
        assert taxon_taxdb.rank_lineage == taxon_taxsqlite.rank_lineage
        assert taxon_taxdb.name_lineage == taxon_taxsqlite.name_lineage

    def test_upper_rank_id_integration(self, sample_taxdb):
        """Test upper_rank_id function with real data."""
        # Test with human (species level)
        human_taxon = Taxon(9606, sample_taxdb)

        genus_id = upper_rank_id(human_taxon, "genus")
        assert genus_id == 9605
        assert Taxon(genus_id, sample_taxdb).rank == "genus"
        assert genus_id in human_taxon.taxid_lineage

    def test_legacy_taxid_resolution(self, sample_taxdb):
        """Test legacy taxid resolution end-to-end."""
        # Test with legacy taxid 6043 -> 6042
        legacy_taxon = Taxon(6043, sample_taxdb)

        # Should be marked as legacy
        assert legacy_taxon.is_legacy
        assert legacy_taxon.taxid == 6043
        assert legacy_taxon.update_taxid == 6042

        # Compare with direct access
        direct_taxon = Taxon(6042, sample_taxdb)
        assert legacy_taxon.name == direct_taxon.name
        assert legacy_taxon.rank == direct_taxon.rank
        assert legacy_taxon.lineage == direct_taxon.lineage

    def test_search_and_retrieve_workflow(self, sample_taxdb):
        """Test typical workflow: search for organism, then get details."""
        search_results = sample_taxdb.search("Homo sapiens", limit=5)
        human_result = next(result for result in search_results if result["taxid"] == 9606)
        human_taxon = Taxon(human_result["taxid"], sample_taxdb)
        assert human_taxon.name == "Homo sapiens"
        assert human_taxon.rank == "species"
        assert len(human_taxon.lineage) > 1
        assert human_taxon.lineage[0].taxid == 9606

    @pytest.mark.slow
    def test_database_rebuild_consistency(self, cached_dir):
        """Test that rebuilding database gives consistent results."""
        with TaxSQLite(cached_dir) as db:
            before = db.get_node(9606)
        assert main(["cache", "-d", str(cached_dir)]) == 0
        with TaxSQLite(cached_dir) as db:
            assert db.get_node(9606) == before

    def test_package_imports(self):
        """Test that all expected symbols can be imported from package."""
        # Test main imports
        from taxdumpy import (
            TaxDb,
            TaxDbError,
            TaxidError,
            Taxon,
            TaxSQLite,
            upper_rank_id,
        )

        # Test that classes are callable
        assert callable(TaxDb)
        assert callable(TaxSQLite)
        assert callable(Taxon)
        assert callable(upper_rank_id)

        # Test exception inheritance
        assert issubclass(TaxDbError, Exception)
        assert issubclass(TaxidError, Exception)

    def test_ansi_module_integration(self):
        """Test ANSI color module integration."""
        from taxdumpy.ansi import b_str, m_color, r_str, u_str

        # Test functions are callable
        test_string = "test"
        assert callable(u_str)
        assert callable(b_str)
        assert callable(r_str)
        assert callable(m_color)

        # Test they return strings
        assert isinstance(u_str(test_string), str)
        assert isinstance(b_str(test_string), str)
        assert isinstance(r_str(test_string), str)
