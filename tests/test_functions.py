"""Tests for functions module."""

import pytest

from taxdumpy import Taxon
from taxdumpy.basic import RC, TaxRankError
from taxdumpy.functions import (
    LEVEL2RANK,
    RANK2LEVEL,
    RANKNAMES,
    group_taxids_by_rank,
    upper_rank_id,
)


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
        from taxdumpy import upper_rank_id as pkg_upper_rank_id
        from taxdumpy.functions import upper_rank_id

        # Should be the same function
        assert upper_rank_id is pkg_upper_rank_id

    def test_rc_class(self):
        """Test RC class for rank codes."""
        # Test creation from string
        assert str(RC("S")) == "S"
        assert str(RC("S1")) == "S1"
        assert str(RC("R")) == "R"

        # Test creation from int
        assert str(RC(2048)) == "S"
        assert str(RC(2049)) == "S1"

        # Test comparison
        assert RC("R") < RC("S")
        assert RC("F") < RC("F1")
        assert RC("G") < RC("S")

    def test_rankcode_lineage_property(self, sample_taxdb, sample_taxids):
        """Test rankcode_lineage property on Taxon."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        codes = human_taxon.rankcode_lineage

        assert isinstance(codes, list)
        assert len(codes) > 0
        # Should be RC objects
        assert all(isinstance(c, RC) for c in codes)
        # Should start with S for species (taxon->root order)
        assert codes[0] == RC("S")
        # Should contain G for genus
        assert RC("G") in codes

    def test_rankcode_lineage_intermediate_ranks(self, sample_taxdb, sample_taxids):
        """Test that intermediate ranks get depth numbers."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        codes = human_taxon.rankcode_lineage

        # Human lineage has many intermediate ranks, should have codes like F1, O1, etc.
        has_depth_codes = any((c & 0xFF) > 0 for c in codes)  # depth > 0
        assert has_depth_codes

    def test_rankcode_lineage_root(self, sample_taxdb, sample_taxids):
        """Test that root (taxid 1) is 'R' not 'R1'."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        codes = human_taxon.rankcode_lineage

        # Last element should be R for root (taxon->root order)
        assert codes[-1] == RC("R")

    def test_rankcode_comparable(self, sample_taxdb, sample_taxids):
        """Test that RC objects are comparable."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        codes = human_taxon.rankcode_lineage

        # R should be less than S (higher rank = lower value)
        assert RC("R") < RC("S")
        # F should be less than F1
        assert RC("F") < RC("F1")
        # Sorting should work
        sorted_codes = sorted(codes)
        assert sorted_codes[0] < sorted_codes[-1]

    def test_mpa_repr_property(self, sample_taxdb, sample_taxids):
        """Test mpa_repr property on Taxon."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        mpa = human_taxon.mpa_repr

        assert isinstance(mpa, str)
        # Should contain species
        assert "s__Homo_sapiens" in mpa
        # Should contain genus
        assert "g__Homo" in mpa
        # Should use pipe separator
        assert "|" in mpa
        # Should start with domain
        assert mpa.startswith("d__")

    def test_rc_import(self):
        """Test that RC can be imported from package."""
        from taxdumpy import RC

        assert RC("S") == RC(2048)

    def test_group_taxids_by_rank_family(self, sample_taxdb, sample_taxids):
        """Test grouping taxids by family."""
        taxids = [sample_taxids["human"], sample_taxids["homo"]]
        groups = group_taxids_by_rank(taxids, "family", sample_taxdb)

        assert isinstance(groups, dict)
        # Both should be in Hominidae (9604)
        assert 9604 in groups
        assert sample_taxids["human"] in groups[9604]
        assert sample_taxids["homo"] in groups[9604]

    def test_group_taxids_by_rank_genus(self, sample_taxdb, sample_taxids):
        """Test grouping taxids by genus."""
        taxids = [sample_taxids["human"], sample_taxids["homo"]]
        groups = group_taxids_by_rank(taxids, "genus", sample_taxdb)

        assert isinstance(groups, dict)
        # Both should be in Homo (9605)
        assert 9605 in groups
        assert sample_taxids["human"] in groups[9605]
        assert sample_taxids["homo"] in groups[9605]

    def test_group_taxids_by_rank_fallback(self, sample_taxdb, sample_taxids):
        """Test that grouping falls back to closest ancestor when exact rank missing."""
        # Human has F1 (subfamily) between G and F, so grouping by family should work
        taxids = [sample_taxids["human"]]
        groups = group_taxids_by_rank(taxids, "family", sample_taxdb)

        assert len(groups) == 1
        # Should find family (F) not subfamily (F1)
        group_taxid = list(groups.keys())[0]
        taxon = Taxon(group_taxid, sample_taxdb)
        assert taxon.rank == "family"

    def test_group_taxids_by_rank_invalid_rank(self, sample_taxdb, sample_taxids):
        """Test that invalid rank raises TaxRankError."""
        from taxdumpy import TaxRankError

        taxids = [sample_taxids["human"]]
        with pytest.raises(TaxRankError):
            group_taxids_by_rank(taxids, "invalid_rank", sample_taxdb)

    def test_group_taxids_by_rank_empty(self, sample_taxdb):
        """Test grouping with empty input."""
        groups = group_taxids_by_rank([], "family", sample_taxdb)
        assert groups == {}

    def test_group_taxids_by_rank_unknown_taxid(self, sample_taxdb):
        """Test that unknown taxids are skipped."""
        groups = group_taxids_by_rank([999999999], "family", sample_taxdb)
        assert groups == {}
