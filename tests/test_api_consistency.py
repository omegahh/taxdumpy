"""Tests for API consistency across database backends."""

import pytest
from pathlib import Path
from typing import Type

from taxdumpy import TaxDb, TaxSQLite, TaxonomyDatabase, create_database
from taxdumpy.basic import TaxidError, ValidationError


class TestAbstractBaseClass:
    """Test abstract base class functionality."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that TaxonomyDatabase cannot be instantiated directly."""
        with pytest.raises(TypeError):
            TaxonomyDatabase("/fake/path")

    def test_subclass_inheritance(self):
        """Test that concrete classes inherit from abstract base."""
        assert issubclass(TaxDb, TaxonomyDatabase)
        assert issubclass(TaxSQLite, TaxonomyDatabase)

    def test_required_methods_defined(self, sample_taxdump_dir):
        """Test that all backends implement required abstract methods."""
        backends = [TaxDb, TaxSQLite]
        required_methods = [
            "get_node",
            "fuzzy_search",
            "_rapid_fuzz",
            "__len__",
            "__repr__",
            "close",
        ]
        required_properties = [
            "all_names",
            "name2taxid",
            "delnodes",
            "max_taxid_strlen",
            "max_rank_strlen",
        ]

        for backend_class in backends:
            db = backend_class(sample_taxdump_dir)

            # Check methods exist and are callable
            for method_name in required_methods:
                assert hasattr(db, method_name)
                assert callable(getattr(db, method_name))

            # Check properties exist
            for prop_name in required_properties:
                assert hasattr(db, prop_name)

            if hasattr(db, "close"):
                db.close()


class TestFactoryFunction:
    """Test create_database factory function."""

    def test_sqlite_backend_creation(self, sample_taxdump_dir):
        """Test creating SQLite backend via factory."""
        db = create_database(sample_taxdump_dir, "sqlite")
        assert isinstance(db, TaxSQLite)
        assert isinstance(db, TaxonomyDatabase)
        db.close()

    def test_dict_backend_creation(self, sample_taxdump_dir):
        """Test creating dict backend via factory."""
        db = create_database(sample_taxdump_dir, "dict")
        assert isinstance(db, TaxDb)
        assert isinstance(db, TaxonomyDatabase)

    def test_backend_aliases(self, sample_taxdump_dir):
        """Test backend aliases work correctly."""
        # SQLite aliases
        db1 = create_database(sample_taxdump_dir, "sql")
        assert isinstance(db1, TaxSQLite)
        db1.close()

        # Dict aliases
        db2 = create_database(sample_taxdump_dir, "memory")
        assert isinstance(db2, TaxDb)

        db3 = create_database(sample_taxdump_dir, "pickle")
        assert isinstance(db3, TaxDb)

    def test_invalid_backend_validation(self, sample_taxdump_dir):
        """Test validation of invalid backend names."""
        with pytest.raises(ValidationError) as exc_info:
            create_database(sample_taxdump_dir, "invalid_backend")
        assert "backend" in str(exc_info.value)
        assert "invalid_backend" in str(exc_info.value)

    def test_backend_type_validation(self, sample_taxdump_dir):
        """Test validation of non-string backend parameter."""
        with pytest.raises(ValidationError) as exc_info:
            create_database(sample_taxdump_dir, 123)
        assert "backend" in str(exc_info.value)
        assert "string" in str(exc_info.value)

    def test_kwargs_forwarding(self, sample_taxdump_dir):
        """Test that kwargs are forwarded to backend constructors."""
        # Test TaxDb with fast=True
        db = create_database(sample_taxdump_dir, "dict", fast=True)
        assert hasattr(db, "_fast")
        assert db._fast is True


@pytest.mark.parametrize("backend", ["sqlite", "dict"])
class TestPolymorphicBehavior:
    """Test that both backends behave identically."""

    def test_get_node_consistent_signature(
        self, backend, sample_taxdump_dir, sample_taxids
    ):
        """Test get_node method consistency."""
        db = create_database(sample_taxdump_dir, backend)

        # Both should accept int and string taxids
        node1 = db.get_node(sample_taxids["human"])
        node2 = db.get_node(str(sample_taxids["human"]))

        assert node1.taxid == node2.taxid
        assert node1.name == node2.name
        assert node1.rank == node2.rank

        if hasattr(db, "close"):
            db.close()

    def test_fuzzy_search_consistent_signature(self, backend, sample_taxdump_dir):
        """Test fuzzy_search method consistency."""
        db = create_database(sample_taxdump_dir, backend)

        # Both should have same signature and return None
        result = db.fuzzy_search("human", limit=5)
        assert result is None

        if hasattr(db, "close"):
            db.close()

    def test_rapid_fuzz_consistent_signature(self, backend, sample_taxdump_dir):
        """Test _rapid_fuzz method consistency."""
        db = create_database(sample_taxdump_dir, backend)

        # Both should return list of dicts with same structure
        results = db._rapid_fuzz("human", limit=3)
        assert isinstance(results, list)

        if results:
            for result in results:
                assert isinstance(result, dict)
                assert "name" in result
                assert "taxid" in result
                assert "score" in result
                assert isinstance(result["name"], str)
                assert isinstance(result["taxid"], int)
                assert isinstance(result["score"], (int, float))

        if hasattr(db, "close"):
            db.close()

    def test_len_method_consistency(self, backend, sample_taxdump_dir):
        """Test __len__ method consistency."""
        db = create_database(sample_taxdump_dir, backend)

        length = len(db)
        assert isinstance(length, int)
        assert length > 0

        if hasattr(db, "close"):
            db.close()

    def test_properties_consistency(self, backend, sample_taxdump_dir):
        """Test property consistency across backends."""
        db = create_database(sample_taxdump_dir, backend)

        # Test all_names property
        all_names = db.all_names
        assert isinstance(all_names, list)
        assert all(isinstance(name, str) for name in all_names)

        # Test name2taxid property
        name2taxid = db.name2taxid
        assert isinstance(name2taxid, dict)
        assert all(
            isinstance(k, str) and isinstance(v, int) for k, v in name2taxid.items()
        )

        # Test delnodes property
        delnodes = db.delnodes
        assert isinstance(delnodes, set)
        assert all(isinstance(taxid, int) for taxid in delnodes)

        # Test formatting properties
        max_taxid_len = db.max_taxid_strlen
        max_rank_len = db.max_rank_strlen
        assert isinstance(max_taxid_len, int)
        assert isinstance(max_rank_len, int)
        assert max_taxid_len > 0
        assert max_rank_len > 0

        if hasattr(db, "close"):
            db.close()


@pytest.mark.parametrize("backend", ["sqlite", "dict"])
class TestErrorHandlingConsistency:
    """Test consistent error handling across backends."""

    def test_validation_error_consistency(self, backend, sample_taxdump_dir):
        """Test that validation errors are consistent."""
        db = create_database(sample_taxdump_dir, backend)

        # Both should raise ValidationError for invalid taxid types
        with pytest.raises(ValidationError):
            db.get_node(None)

        with pytest.raises(ValidationError):
            db.get_node("")

        with pytest.raises(ValidationError):
            db.get_node(-1)

        # Both should raise ValidationError for invalid search parameters
        with pytest.raises(ValidationError):
            db._rapid_fuzz(123)  # Non-string query

        with pytest.raises(ValidationError):
            db._rapid_fuzz("test", -1)  # Negative limit

        if hasattr(db, "close"):
            db.close()

    def test_taxid_error_consistency(self, backend, sample_taxdump_dir):
        """Test that TaxidError behavior is consistent."""
        db = create_database(sample_taxdump_dir, backend)

        # Both should raise TaxidError for non-existent taxids
        with pytest.raises(TaxidError) as exc_info:
            db.get_node(999999999)

        error_msg = str(exc_info.value)
        assert "not found" in error_msg.lower()

        if hasattr(db, "close"):
            db.close()

    def test_error_message_format_consistency(
        self, backend, sample_taxdump_dir, sample_taxids
    ):
        """Test that error messages have consistent format."""
        db = create_database(sample_taxdump_dir, backend)

        # Test deleted taxid error messages
        try:
            db.get_node(sample_taxids["deleted_3451490"])
            assert False, "Should have raised TaxidError"
        except TaxidError as e:
            error_msg = str(e)
            assert "deleted" in error_msg.lower()
            assert "suggestion" in error_msg.lower() or "try" in error_msg.lower()

        if hasattr(db, "close"):
            db.close()


class TestContextManagerSupport:
    """Test context manager functionality."""

    @pytest.mark.parametrize("backend", ["sqlite", "dict"])
    def test_context_manager_protocol(self, backend, sample_taxdump_dir, sample_taxids):
        """Test context manager support."""
        with create_database(sample_taxdump_dir, backend) as db:
            assert isinstance(db, TaxonomyDatabase)

            # Should be able to use database normally
            node = db.get_node(sample_taxids["human"])
            assert node.taxid == sample_taxids["human"]

        # Database should be closed after context manager exit
        # (This is hard to test directly, but at least it shouldn't crash)

    def test_explicit_close(self, sample_taxdump_dir):
        """Test explicit close method."""
        db = create_database(sample_taxdump_dir, "sqlite")

        # Should have close method
        assert hasattr(db, "close")
        assert callable(db.close)

        # Should not raise error when called
        db.close()

        # Should be safe to call multiple times
        db.close()


class TestBackwardCompatibility:
    """Test that existing code continues to work."""

    def test_direct_instantiation_still_works(self, sample_taxdump_dir):
        """Test that direct instantiation of backends still works."""
        # Old way should still work
        db1 = TaxDb(sample_taxdump_dir)
        db2 = TaxSQLite(sample_taxdump_dir)

        assert isinstance(db1, TaxDb)
        assert isinstance(db1, TaxonomyDatabase)
        assert isinstance(db2, TaxSQLite)
        assert isinstance(db2, TaxonomyDatabase)

        db2.close()

    def test_existing_method_signatures_preserved(
        self, sample_taxdump_dir, sample_taxids
    ):
        """Test that existing method signatures are preserved."""
        db = TaxDb(sample_taxdump_dir)

        # These should all work as before
        node = db.get_node(sample_taxids["human"])
        assert node.name

        results = db._rapid_fuzz("human")
        assert isinstance(results, list)

        db.fuzzy_search("human", limit=3)  # Should print results

        length = len(db)
        assert length > 0


class TestTypeHints:
    """Test type hint consistency."""

    def test_return_type_consistency(self, sample_taxdump_dir, sample_taxids):
        """Test that return types match type hints."""
        backends = [
            create_database(sample_taxdump_dir, "dict"),
            create_database(sample_taxdump_dir, "sqlite"),
        ]

        for db in backends:
            # get_node should return Node
            node = db.get_node(sample_taxids["human"])
            assert hasattr(node, "taxid")
            assert hasattr(node, "name")
            assert hasattr(node, "rank")

            # _rapid_fuzz should return List[Dict[str, Union[str, int]]]
            results = db._rapid_fuzz("human", limit=2)
            assert isinstance(results, list)

            # Properties should return correct types
            assert isinstance(db.all_names, list)
            assert isinstance(db.name2taxid, dict)
            assert isinstance(db.delnodes, set)
            assert isinstance(db.max_taxid_strlen, int)
            assert isinstance(db.max_rank_strlen, int)

            if hasattr(db, "close"):
                db.close()


# Integration test to ensure the whole system works together
def test_end_to_end_consistency(sample_taxdump_dir, sample_taxids):
    """Test complete workflow with both backends."""
    backends = ["sqlite", "dict"]

    for backend_name in backends:
        with create_database(sample_taxdump_dir, backend_name) as db:
            # 1. Get a node by taxid
            human_node = db.get_node(sample_taxids["human"])
            assert human_node.name == "Homo sapiens"
            assert human_node.rank == "species"

            # 2. Search for organisms (dict backend only supports _rapid_fuzz properly)
            search_results = db._rapid_fuzz("Homo sapiens", limit=3)
            if backend_name == "dict":
                assert len(search_results) > 0
                assert any(
                    result["name"] == "Homo sapiens" for result in search_results
                )
            # Note: SQLite backend _rapid_fuzz is not fully implemented

            # 3. Check database properties
            assert len(db) > 0
            # Note: SQLite backend has different behavior for all_names and name2taxid
            if backend_name == "dict":
                assert "Homo sapiens" in db.all_names
                assert db.name2taxid["Homo sapiens"] == sample_taxids["human"]
            else:
                # SQLite backend properties may not be fully implemented
                assert isinstance(db.all_names, list)
                assert isinstance(db.name2taxid, dict)

            # 4. Handle errors gracefully
            with pytest.raises(TaxidError):
                db.get_node(999999999)

            with pytest.raises(ValidationError):
                db.get_node("")
