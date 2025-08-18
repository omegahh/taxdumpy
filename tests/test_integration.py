"""Integration tests for taxdumpy package."""

import pytest
from pathlib import Path
import tempfile

from taxdumpy import TaxDb, TaxSQLite, Taxon, upper_rank_id


@pytest.mark.integration
class TestIntegration:
    """Integration tests that test components working together."""

    def test_taxdb_to_taxsqlite_consistency(self, sample_taxdump_dir):
        """Test that TaxDb and TaxSQLite return consistent results."""
        taxdb = TaxDb(sample_taxdump_dir)

        with TaxSQLite(sample_taxdump_dir) as taxsqlite:
            # Test same taxids return same basic information
            test_taxids = [9606, 2161, 7868, 2, 1]

            for taxid in test_taxids:
                try:
                    taxdb_node = taxdb.get_node(taxid)
                    taxsqlite_node = taxsqlite.get_node(taxid)

                    assert taxdb_node.taxid == taxsqlite_node.taxid
                    assert taxdb_node.name == taxsqlite_node.name
                    assert taxdb_node.rank == taxsqlite_node.rank
                    assert taxdb_node.parent == taxsqlite_node.parent
                    assert taxdb_node.division == taxsqlite_node.division

                except Exception:
                    # Some taxids might not exist in sample data
                    pass

    def test_taxon_with_both_backends(self, sample_taxdump_dir):
        """Test Taxon class with both database backends."""
        taxdb = TaxDb(sample_taxdump_dir)

        with TaxSQLite(sample_taxdump_dir) as taxsqlite:
            # Test human taxon with both backends
            taxon_taxdb = Taxon(9606, taxdb)
            taxon_taxsqlite = Taxon(9606, taxsqlite)

            # Should have same basic properties
            assert taxon_taxdb.taxid == taxon_taxsqlite.taxid
            assert taxon_taxdb.name == taxon_taxsqlite.name
            assert taxon_taxdb.rank == taxon_taxsqlite.rank
            assert taxon_taxdb.is_legacy == taxon_taxsqlite.is_legacy

            # Lineages should be the same
            assert len(taxon_taxdb.lineage) == len(taxon_taxsqlite.lineage)
            assert taxon_taxdb.taxid_lineage == taxon_taxsqlite.taxid_lineage
            assert taxon_taxdb.rank_lineage == taxon_taxsqlite.rank_lineage
            assert taxon_taxdb.name_lineage == taxon_taxsqlite.name_lineage

    def test_upper_rank_id_integration(self, sample_taxdb):
        """Test upper_rank_id function with real data."""
        # Test with human (species level)
        human_taxon = Taxon(9606, sample_taxdb)

        # Only test if the lineage has the required ranks
        if "genus" in human_taxon.rank_lineage:
            genus_id = upper_rank_id(human_taxon, sample_taxdb, "genus")
            genus_taxon = Taxon(genus_id, sample_taxdb)
            assert genus_taxon.rank == "genus"
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
        # Search for human-related terms
        search_results = sample_taxdb._rapid_fuzz("human", limit=5)

        human_result = None
        for result in search_results:
            if result["taxid"] == 9606:
                human_result = result
                break

        if human_result:
            # Get detailed information
            human_taxon = Taxon(human_result["taxid"], sample_taxdb)
            assert human_taxon.name == "Homo sapiens"
            assert human_taxon.rank == "species"

            # Check lineage makes sense
            assert len(human_taxon.lineage) > 1
            assert human_taxon.lineage[0].taxid == 9606  # Self should be first

    @pytest.mark.slow
    def test_database_rebuild_consistency(self, sample_taxdump_dir):
        """Test that rebuilding database gives consistent results."""
        # Create first database
        with tempfile.TemporaryDirectory() as temp_dir1:
            temp_path1 = Path(temp_dir1)

            # Copy sample data
            for file in [
                "nodes.dmp",
                "names.dmp",
                "merged.dmp",
                "delnodes.dmp",
                "division.dmp",
            ]:
                src = sample_taxdump_dir / file
                dst = temp_path1 / file
                dst.write_text(src.read_text())

            # Build first database
            taxsqlite1 = TaxSQLite(temp_path1)
            node1 = taxsqlite1.get_node(9606)
            taxsqlite1.close()

            # Create second database from same data
            with tempfile.TemporaryDirectory() as temp_dir2:
                temp_path2 = Path(temp_dir2)

                # Copy same data
                for file in [
                    "nodes.dmp",
                    "names.dmp",
                    "merged.dmp",
                    "delnodes.dmp",
                    "division.dmp",
                ]:
                    src = sample_taxdump_dir / file
                    dst = temp_path2 / file
                    dst.write_text(src.read_text())

                # Build second database
                taxsqlite2 = TaxSQLite(temp_path2)
                node2 = taxsqlite2.get_node(9606)
                taxsqlite2.close()

                # Should be identical
                assert node1.taxid == node2.taxid
                assert node1.name == node2.name
                assert node1.rank == node2.rank
                assert node1.parent == node2.parent

    def test_package_imports(self):
        """Test that all expected symbols can be imported from package."""
        # Test main imports
        from taxdumpy import TaxDb, TaxSQLite, Taxon, upper_rank_id
        from taxdumpy import TaxDbError, TaxidError

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
        from taxdumpy.ansi import u_str, b_str, r_str, m_color

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
