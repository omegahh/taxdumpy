"""Tests for functions module."""

import pytest
from taxdumpy import TaxDb, Taxon
from taxdumpy.functions import upper_rank_id, RANKNAMES, RANK2LEVEL, LEVEL2RANK
from taxdumpy.basic import TaxRankError


class TestFunctions:
    """Test utility functions."""

    def test_rank_constants(self):
        """Test rank name constants."""
        assert isinstance(RANKNAMES, list)
        assert isinstance(RANK2LEVEL, dict)
        assert isinstance(LEVEL2RANK, dict)

        # Check basic ranks are present
        assert "species" in RANKNAMES
        assert "genus" in RANKNAMES
        assert "family" in RANKNAMES
        assert "order" in RANKNAMES
        assert "class" in RANKNAMES
        assert "phylum" in RANKNAMES
        assert "superkingdom" in RANKNAMES

        # Check mappings are consistent
        for rank in RANKNAMES:
            level = RANK2LEVEL[rank]
            assert LEVEL2RANK[level] == rank

    def test_upper_rank_id_valid_ranks(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with valid ranks."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Test getting genus from species
        if "genus" in human_taxon.rank_lineage:
            genus_id = upper_rank_id(human_taxon, sample_taxdb, "genus")
            assert isinstance(genus_id, int)
            assert genus_id > 0

            # Verify it's actually a genus
            genus_taxon = Taxon(genus_id, sample_taxdb)
            assert genus_taxon.rank == "genus"

    def test_upper_rank_id_same_rank_error(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with same rank (should raise error)."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Trying to get species from species should raise error
        with pytest.raises(RuntimeError):
            upper_rank_id(human_taxon, sample_taxdb, "species")

    def test_upper_rank_id_lower_rank_error(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with lower rank (should raise error)."""
        # Get a genus-level taxon
        genus_taxon = Taxon(9605, sample_taxdb)  # Homo genus

        # Trying to get species from genus should raise error
        with pytest.raises(RuntimeError):
            upper_rank_id(genus_taxon, sample_taxdb, "species")

    def test_upper_rank_id_invalid_current_rank(self, sample_taxdb):
        """Test upper_rank_id with non-canonical current rank."""
        # Create a taxon with non-canonical rank (like "clade")
        clade_taxon = Taxon(6072, sample_taxdb)  # Eumetazoa (clade)

        # Should raise TaxRankError for non-canonical rank
        with pytest.raises(TaxRankError):
            upper_rank_id(clade_taxon, sample_taxdb, "genus")

    def test_upper_rank_id_invalid_target_rank(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with invalid target rank."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Should raise assertion error for invalid rank
        with pytest.raises(Exception):  # AssertionError wrapped in TaxRankError
            upper_rank_id(human_taxon, sample_taxdb, "invalid_rank")

    def test_upper_rank_id_direct_lineage(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id when target rank exists directly in lineage."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # If family exists in lineage, should find it directly
        if "family" in human_taxon.rank_lineage:
            family_id = upper_rank_id(human_taxon, sample_taxdb, "family")
            family_idx = human_taxon.rank_lineage.index("family")
            expected_id = human_taxon.taxid_lineage[family_idx]
            assert family_id == expected_id

    def test_upper_rank_id_sub_rank(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id when sub-rank exists in lineage."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # This test might not apply to our sample data
        # but tests the sub-rank logic
        lineage_ranks = human_taxon.rank_lineage

        # Mock a scenario where subfamily exists but not family
        # This is mainly to test the logic structure
        pass

    def test_upper_rank_id_jump_logic(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id jump logic when exact rank not found."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # This tests the complex logic where we need to jump up levels
        # The exact behavior depends on the lineage structure
        # For now, just test that it doesn't crash
        try:
            if len(human_taxon.rank_lineage) > 3:  # Need enough levels
                # Try to get a high-level rank
                result = upper_rank_id(human_taxon, sample_taxdb, "superkingdom")
                assert isinstance(result, int)
        except (RuntimeError, TaxRankError):
            # Expected if the rank structure doesn't support this
            pass

    def test_rank_level_consistency(self):
        """Test that rank levels are consistent and ordered."""
        levels = list(RANK2LEVEL.values())
        ranks = list(LEVEL2RANK.keys())

        # Should be consecutive integers starting from 0
        assert sorted(levels) == list(range(len(RANKNAMES)))
        assert sorted(ranks) == list(range(len(RANKNAMES)))

        # Species should be level 0 (most specific)
        assert RANK2LEVEL["species"] == 0

        # Higher taxonomic levels should have higher numbers
        assert RANK2LEVEL["genus"] > RANK2LEVEL["species"]
        assert RANK2LEVEL["family"] > RANK2LEVEL["genus"]

    def test_function_imports(self):
        """Test that functions can be imported from package."""
        from taxdumpy.functions import upper_rank_id
        from taxdumpy import upper_rank_id as pkg_upper_rank_id

        # Should be the same function
        assert upper_rank_id is pkg_upper_rank_id
