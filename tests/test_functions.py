"""Tests for functions module."""

from dataclasses import replace

import pytest

from taxdumpy import TaxDbError, Taxon, open_database
from taxdumpy.basic import RC, TaxRankError, ValidationError
from taxdumpy.functions import (
    LEVEL2RANK,
    RANK2LEVEL,
    RANKNAMES,
    find_rank_in_lineage,
    get_all_ranks,
    get_canonical_ranks,
    get_closest_rank,
    get_rank_distance,
    get_rank_or_closest,
    get_rank_taxid,
    group_taxids_by_rank,
    upper_rank_id,
)
from taxdumpy.ranks import EXTENDED_RANKS, MPA_CODES, RANK_CODES


@pytest.fixture(params=["dict", "sqlite"])
def rank_db(request, sample_taxdump_dir):
    with open_database(sample_taxdump_dir, request.param) as db:
        yield db


class TestRankHelpers:
    def test_exact_subrank_and_missing_lookup(self, rank_db):
        human = Taxon(9606, rank_db)
        assert get_rank_taxid(human, "family") == 9604
        assert get_rank_taxid(human, "subfamily") == 207598
        human = Taxon(9606, rank_db)
        human._lineage = tuple(replace(node, rank="clade") if node.rank == "family" else node for node in human.lineage)
        assert get_rank_taxid(human, "family") == 207598
        assert get_rank_taxid(human, "family", include_subrank=False) is None
        assert get_rank_taxid(human, "absent") is None
        assert get_rank_taxid(Taxon(6072, rank_db), "kingdom") == 33208

    def test_canonical_ranks_with_subrank_control(self, rank_db):
        human = Taxon(9606, rank_db)
        human = Taxon(9606, rank_db)
        human._lineage = tuple(replace(node, rank="clade") if node.rank == "family" else node for node in human.lineage)
        ranks = get_canonical_ranks(human)
        assert ranks["family"] == 207598
        assert ranks["domain"] == ranks["superkingdom"] == 2759
        assert "clade" not in ranks
        assert "realm" not in ranks
        assert "family" not in get_canonical_ranks(human, include_subranks=False)
        assert get_canonical_ranks(Taxon(1, rank_db)) == {}

    def test_closest_rank_ignores_unranked_links(self, rank_db):
        taxon = Taxon(6072, rank_db)
        assert get_closest_rank(taxon, "class") == (33208, "kingdom")
        assert get_closest_rank(taxon, "invalid") == (None, None)
        assert get_closest_rank(Taxon(1, rank_db), "genus") == (None, None)
        human = Taxon(9606, rank_db)
        human = Taxon(9606, rank_db)
        human._lineage = tuple(replace(node, rank="clade") if node.rank == "family" else node for node in human.lineage)
        assert get_closest_rank(human, "family") == (207598, "subfamily")
        assert get_closest_rank(human, "family", include_subranks=False) == (9443, "order")

    def test_fallback_distance_counts_canonical_levels(self, rank_db):
        taxon = Taxon(6072, rank_db)
        assert get_rank_or_closest(taxon, "class", max_distance=1) is None
        assert get_rank_or_closest(taxon, "class", max_distance=2) == 33208
        assert get_rank_or_closest(taxon, "class") == 33208
        assert get_rank_or_closest(taxon, "kingdom", max_distance=0) == 33208
        assert get_rank_or_closest(taxon, "invalid") is None
        assert get_rank_or_closest(Taxon(1, rank_db), "species") is None

    @pytest.mark.parametrize("bad", [-1, True, 1.5, "2"])
    def test_fallback_rejects_invalid_distance(self, rank_db, bad):
        with pytest.raises(ValidationError, match="max_distance"):
            get_rank_or_closest(Taxon(9606, rank_db), "genus", max_distance=bad)

    def test_all_ranks_keeps_nearest_repeated_rank(self, rank_db):
        ranks = get_all_ranks(Taxon(9606, rank_db))
        assert ranks["species"] == 9606
        assert ranks["clade"] == 1437010
        assert ranks["no rank"] == 1
        assert ranks["subfamily"] == 207598

    def test_rank_preferences_are_respected(self, rank_db):
        taxon = Taxon(9606, rank_db)
        assert find_rank_in_lineage(taxon, ["family", "genus"]) == (9604, "family")
        assert find_rank_in_lineage(taxon, ["absent", "genus"]) == (9605, "genus")
        assert find_rank_in_lineage(taxon, ["absent"]) == (None, None)
        assert find_rank_in_lineage(taxon, []) == (None, None)

    @pytest.mark.parametrize("first,second,distance", [("species", "family", 2), ("genus", "genus", 0)])
    def test_rank_distance_is_symmetric(self, first, second, distance):
        assert get_rank_distance(first, second) == distance
        assert get_rank_distance(second, first) == distance
        assert get_rank_distance(first, "clade") is None
        assert get_rank_distance("invalid", second) is None


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
            assert RANK2LEVEL[LEVEL2RANK[level]] == level

        assert set(RANKNAMES) == set(RANK_CODES) == set(MPA_CODES)
        assert set(RANKNAMES) <= set(EXTENDED_RANKS)
        assert all(str(RC(code)) == code for code in RANK_CODES.values())

    def test_upper_rank_id_valid_ranks(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with valid ranks."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Test getting genus from species
        genus_id = upper_rank_id(human_taxon, "genus")
        assert genus_id == 9605
        assert Taxon(genus_id, sample_taxdb).rank == "genus"

    def test_upper_rank_id_same_rank_error(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with same rank (should raise error)."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Trying to get species from species should raise error
        with pytest.raises(RuntimeError):
            upper_rank_id(human_taxon, "species")

    def test_upper_rank_id_lower_rank_error(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with lower rank (should raise error)."""
        # Get a genus-level taxon
        genus_taxon = Taxon(9605, sample_taxdb)  # Homo genus

        # Trying to get species from genus should raise error
        with pytest.raises(RuntimeError):
            upper_rank_id(genus_taxon, "species")

    def test_upper_rank_id_invalid_current_rank(self, sample_taxdb):
        """Test upper_rank_id with non-canonical current rank."""
        # Create a taxon with non-canonical rank (like "clade")
        clade_taxon = Taxon(6072, sample_taxdb)  # Eumetazoa (clade)

        # Should raise TaxRankError for non-canonical rank
        with pytest.raises(TaxRankError):
            upper_rank_id(clade_taxon, "genus")

    def test_upper_rank_id_invalid_target_rank(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id with invalid target rank."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        with pytest.raises(TaxRankError):
            upper_rank_id(human_taxon, "invalid_rank")

    def test_upper_rank_id_direct_lineage(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id when target rank exists directly in lineage."""
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)

        assert upper_rank_id(human_taxon, "family") == 9604

    def test_upper_rank_id_sub_rank(self, sample_taxdb, sample_taxids):
        """Test upper_rank_id when sub-rank exists in lineage."""
        node = sample_taxdb.get_node(9604)
        sample_taxdb._taxid2nodes[9604] = replace(node, rank="clade")
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        assert upper_rank_id(human_taxon, "family") == 207598

    def test_upper_rank_id_missing_rank_does_not_guess_parent(self, sample_taxdb, sample_taxids):
        """Clades between ranks cannot substitute for a missing canonical rank."""
        for taxid, node in sample_taxdb._taxid2nodes.items():
            if node.rank in {"family", "subfamily"}:
                sample_taxdb._taxid2nodes[taxid] = replace(node, rank="clade")
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        with pytest.raises(TaxRankError, match="absent"):
            upper_rank_id(human_taxon, "family")

    def test_rank_level_consistency(self):
        """Test that rank levels are consistent and ordered."""
        levels = list(RANK2LEVEL.values())
        ranks = list(LEVEL2RANK.keys())

        # Should be consecutive integers starting from 0
        assert sorted(set(levels)) == list(range(len(LEVEL2RANK)))
        assert sorted(ranks) == list(range(len(LEVEL2RANK)))

        # Species should be level 0 (most specific)
        assert RANK2LEVEL["species"] == 0

        # Higher taxonomic levels should have higher numbers
        assert RANK2LEVEL["genus"] > RANK2LEVEL["species"]
        assert RANK2LEVEL["family"] > RANK2LEVEL["genus"]

    def test_domain_and_superkingdom_are_same_level(self, sample_taxdb):
        human = Taxon(9606, sample_taxdb)
        for rank in ("domain", "superkingdom"):
            assert get_rank_taxid(human, rank) == 2759
            assert upper_rank_id(human, rank) == 2759
            assert get_closest_rank(human, rank) == (2759, "domain")
            assert get_rank_or_closest(human, rank, max_distance=0) == 2759
            assert group_taxids_by_rank([9606], rank, sample_taxdb) == {2759: [9606]}
        assert get_rank_distance("domain", "superkingdom") == 0
        assert get_rank_distance("kingdom", "domain") == 1

    def test_realm_rank_codes_and_grouping(self, sample_taxdb):
        virus = Taxon(2585030, sample_taxdb)
        realm = get_rank_taxid(virus, "realm")
        assert realm == 2559587
        assert get_canonical_ranks(virus)["realm"] == realm
        assert Taxon(realm, sample_taxdb).rc == RC("R")
        assert virus.mpa_repr == "r__Riboviria"
        assert group_taxids_by_rank([2585030], "realm", sample_taxdb) == {realm: [2585030]}
        assert group_taxids_by_rank([2585030], "root", sample_taxdb) == {1: [2585030]}

    def test_legacy_superkingdom_resolves_domain_alias(self, sample_taxdb):
        node = sample_taxdb.get_node(2759)
        sample_taxdb._taxid2nodes[2759] = replace(node, rank="superkingdom")
        human = Taxon(9606, sample_taxdb)
        assert get_rank_taxid(human, "domain") == 2759
        assert get_closest_rank(human, "domain") == (2759, "superkingdom")

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

        assert isinstance(codes, tuple)
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

    def test_grouping_does_not_swallow_database_corruption(self, sample_taxdb):
        node = sample_taxdb.get_node(9605)
        sample_taxdb._taxid2nodes[9605] = replace(node, parent=9606)
        with pytest.raises(TaxDbError, match="cycle"):
            group_taxids_by_rank([9606], "family", sample_taxdb)
