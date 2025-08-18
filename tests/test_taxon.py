"""Tests for Taxon class."""

import pytest
from taxdumpy import Taxon, TaxDb, TaxSQLite
from taxdumpy.basic import Node


class TestTaxon:
    """Test the Taxon class."""

    def test_taxon_creation_with_taxdb(self, sample_taxdb, sample_taxids):
        """Test creating a Taxon with TaxDb backend."""
        taxon = Taxon(sample_taxids["human"], sample_taxdb)

        assert taxon.taxid == sample_taxids["human"]
        assert isinstance(taxon.node, Node)
        assert taxon.name == "Homo sapiens"
        assert taxon.rank == "species"

    def test_taxon_creation_with_taxsqlite(self, sample_taxsqlite, sample_taxids):
        """Test creating a Taxon with TaxSQLite backend."""
        taxon = Taxon(sample_taxids["human"], sample_taxsqlite)

        assert taxon.taxid == sample_taxids["human"]
        assert isinstance(taxon.node, Node)
        assert taxon.name == "Homo sapiens"
        assert taxon.rank == "species"

    def test_taxon_properties(self, sample_taxdb, sample_taxids):
        """Test various Taxon properties."""
        taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Basic properties
        assert taxon.update_taxid == 9606
        assert taxon.name == "Homo sapiens"
        assert taxon.rank == "species"
        assert taxon.parent > 0
        assert taxon.division == "PRI"

    def test_taxon_legacy_detection(self, sample_taxdb, sample_taxids):
        """Test detection of legacy (merged) taxids."""
        # Normal taxid
        normal_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        assert not normal_taxon.is_legacy

        # Legacy taxid (6043 maps to 6042)
        legacy_taxon = Taxon(sample_taxids["legacy_6043"], sample_taxdb)
        assert legacy_taxon.is_legacy
        assert legacy_taxon.taxid == 6043
        assert legacy_taxon.update_taxid == 6042

    def test_taxon_lineage(self, sample_taxdb, sample_taxids):
        """Test lineage computation."""
        taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Test lineage properties
        assert isinstance(taxon.lineage, list)
        assert len(taxon.lineage) > 0
        assert all(isinstance(node, Node) for node in taxon.lineage)

        # Test lineage lists
        taxid_lineage = taxon.taxid_lineage
        rank_lineage = taxon.rank_lineage
        name_lineage = taxon.name_lineage

        assert len(taxid_lineage) == len(rank_lineage) == len(name_lineage)
        assert taxid_lineage[0] == sample_taxids["human"]  # First should be self
        assert rank_lineage[0] == "species"
        assert name_lineage[0] == "Homo sapiens"

    def test_species_level_detection(self, sample_taxdb, sample_taxids):
        """Test species level detection."""
        # Human is at species level
        human_taxon = Taxon(sample_taxids["human"], sample_taxdb)
        assert human_taxon.has_species_level
        assert human_taxon.species_taxid == sample_taxids["human"]

        # Genus level should have species in lineage
        genus_taxon = Taxon(9605, sample_taxdb)  # Homo genus
        # May or may not have species depending on lineage structure

    def test_taxon_string_representation(self, sample_taxdb, sample_taxids):
        """Test string representations of Taxon."""
        taxon = Taxon(sample_taxids["human"], sample_taxdb)

        # Test __str__
        str_repr = str(taxon)
        assert "9606" in str_repr
        assert "species" in str_repr
        assert "Homo sapiens" in str_repr

        # Test __repr__
        repr_str = repr(taxon)
        assert isinstance(repr_str, str)
        assert len(repr_str) > 0

        # Test legacy taxon representation
        legacy_taxon = Taxon(sample_taxids["legacy_6043"], sample_taxdb)
        legacy_str = str(legacy_taxon)
        assert "merged" in legacy_str.lower() or "legacy" in legacy_str.lower()

    def test_taxon_lineage_traversal(self, sample_taxdb, sample_taxids):
        """Test that lineage traversal works correctly."""
        taxon = Taxon(sample_taxids["human"], sample_taxdb)
        lineage = taxon.lineage

        # Each node's parent should be the next node in lineage (except root)
        for i in range(len(lineage) - 1):
            current_node = lineage[i]
            parent_node = lineage[i + 1]
            assert current_node.parent == parent_node.taxid

        # Root should be its own parent
        root_node = lineage[-1]
        assert root_node.taxid == root_node.parent

    def test_taxon_with_species(self, sample_taxdb, sample_taxids):
        """Test taxon with species-level organism."""
        species_taxon = Taxon(sample_taxids["methanobacterium_bryantii"], sample_taxdb)

        assert species_taxon.rank == "species"
        assert "Methanobacterium bryantii" in species_taxon.name

        # Should have species in lineage
        assert species_taxon.has_species_level
        species_taxid = species_taxon.species_taxid
        assert species_taxid == sample_taxids["methanobacterium_bryantii"]

    def test_taxon_max_lengths(self, sample_taxdb, sample_taxids):
        """Test max length properties for formatting."""
        taxon = Taxon(sample_taxids["human"], sample_taxdb)

        max_tlen = taxon._max_tlen
        max_rlen = taxon._max_rlen

        assert isinstance(max_tlen, int)
        assert isinstance(max_rlen, int)
        assert max_tlen > 0
        assert max_rlen > 0

    def test_invalid_taxid(self, sample_taxdb):
        """Test creating Taxon with invalid taxid."""
        with pytest.raises(Exception):  # Should raise TaxidError or similar
            Taxon(999999, sample_taxdb)

    def test_taxon_equality_comparison(self, sample_taxdb, sample_taxids):
        """Test if two Taxon objects with same taxid are equivalent."""
        taxon1 = Taxon(sample_taxids["human"], sample_taxdb)
        taxon2 = Taxon(sample_taxids["human"], sample_taxdb)

        # They should have the same properties
        assert taxon1.taxid == taxon2.taxid
        assert taxon1.name == taxon2.name
        assert taxon1.rank == taxon2.rank
        assert taxon1.lineage == taxon2.lineage
