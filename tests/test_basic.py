"""Tests for basic data structures and exceptions."""

import pytest
from taxdumpy.basic import Node, TaxDbError, TaxidError, TaxRankError


class TestNode:
    """Test the Node dataclass."""

    def test_node_creation(self):
        """Test creating a Node instance."""
        node = Node(
            taxid=9606,
            parent=9605,
            rank="species",
            name="Homo sapiens",
            equal=None,
            acronym="HS",
            division="Mammals",
        )

        assert node.taxid == 9606
        assert node.parent == 9605
        assert node.rank == "species"
        assert node.name == "Homo sapiens"
        assert node.equal is None
        assert node.acronym == "HS"
        assert node.division == "Mammals"

    def test_node_with_slots(self):
        """Test that Node uses __slots__ for memory efficiency."""
        node = Node(
            taxid=1,
            parent=1,
            rank="no rank",
            name="root",
            equal=None,
            acronym=None,
            division="root",
        )

        # Should not be able to add arbitrary attributes
        with pytest.raises(AttributeError):
            node.arbitrary_attr = "test"


class TestExceptions:
    """Test custom exception classes."""

    def test_taxdb_error(self):
        """Test TaxDbError exception."""
        with pytest.raises(TaxDbError):
            raise TaxDbError("Database error")

    def test_taxid_error(self):
        """Test TaxidError exception."""
        with pytest.raises(TaxidError):
            raise TaxidError("Invalid taxid")

    def test_taxrank_error(self):
        """Test TaxRankError exception."""
        with pytest.raises(TaxRankError):
            raise TaxRankError("Invalid rank")

    def test_exception_inheritance(self):
        """Test that custom exceptions inherit from Exception."""
        assert issubclass(TaxDbError, Exception)
        assert issubclass(TaxidError, Exception)
        assert issubclass(TaxRankError, Exception)
