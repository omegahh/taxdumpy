"""Abstract base class for taxonomy database backends."""

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Dict, List, Set
from pathlib import Path

from taxdumpy.basic import Node


class TaxonomyDatabase(ABC):
    """
    Abstract base class for taxonomy database backends.

    This class defines the common interface that all database backends
    (TaxDb, TaxSQLite, etc.) should implement to ensure API consistency.
    """

    def __init__(self, taxdump_dir: Path | str, **kwargs):
        """
        Initialize the taxonomy database.

        Args:
            taxdump_dir: Path to directory containing NCBI taxdump files
            **kwargs: Backend-specific parameters
        """
        # Only set _taxdump_dir if taxdump_dir is valid
        # Individual backends will handle validation
        self._taxdump_dir = Path(taxdump_dir).resolve()

    @abstractmethod
    def get_node(self, taxid: int | str) -> Node:
        """
        Get a taxonomy node by taxid.

        Args:
            taxid: NCBI taxonomy ID (integer or string)

        Returns:
            Node object containing taxonomy information

        Raises:
            ValidationError: If taxid is invalid format
            TaxidError: If taxid is not found or deleted
        """
        pass

    @abstractmethod
    def fuzzy_search(self, query: str, limit: int = 10) -> None:
        """
        Print fuzzy search results to console.

        Args:
            query: Search query string
            limit: Maximum number of results to display
        """
        pass

    @abstractmethod
    def _rapid_fuzz(self, query: str, limit: int = 10) -> list[dict[str, str | int]]:
        """
        Perform fuzzy search on organism names.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of dictionaries with 'name', 'taxid', and 'score' keys

        Raises:
            ValidationError: If query or limit are invalid
        """
        pass

    @cached_property
    @abstractmethod
    def all_names(self) -> List[str]:
        """Get all scientific names in the database."""
        pass

    @cached_property
    @abstractmethod
    def name2taxid(self) -> Dict[str, int]:
        """Get mapping from scientific names to taxids."""
        pass

    @cached_property
    @abstractmethod
    def delnodes(self) -> Set[int]:
        """Get set of deleted taxids."""
        pass

    @cached_property
    @abstractmethod
    def max_taxid_strlen(self) -> int:
        """Get maximum string length of taxids for formatting."""
        pass

    @cached_property
    @abstractmethod
    def max_rank_strlen(self) -> int:
        """Get maximum string length of ranks for formatting."""
        pass

    @abstractmethod
    def __len__(self) -> int:
        """Return number of taxonomy nodes in database."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        """Return string representation of database."""
        pass

    def close(self) -> None:
        """
        Close database connection.

        Default implementation does nothing. Backends that require
        explicit cleanup should override this method.
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_database(
    taxdump_dir: Path | str, backend: str = "sqlite", **kwargs
) -> TaxonomyDatabase:
    """
    Factory function to create appropriate database backend.

    Args:
        taxdump_dir: Path to directory containing NCBI taxdump files
        backend: Database backend to use ("sqlite", "dict", or "memory")
        **kwargs: Backend-specific parameters

    Returns:
        TaxonomyDatabase instance

    Raises:
        ValueError: If backend is not supported
        ValidationError: If parameters are invalid
    """
    from taxdumpy.basic import ValidationError

    if not isinstance(backend, str):
        raise ValidationError("backend", type(backend).__name__, "string")

    backend = backend.lower()

    if backend in ("sqlite", "sql"):
        from taxdumpy.taxsqlite import TaxSQLite

        return TaxSQLite(taxdump_dir, **kwargs)
    elif backend in ("dict", "memory", "pickle"):
        from taxdumpy.taxdb import TaxDb

        return TaxDb(taxdump_dir, **kwargs)
    else:
        valid_backends = ["sqlite", "sql", "dict", "memory", "pickle"]
        raise ValidationError(
            "backend", backend, f"one of: {', '.join(valid_backends)}"
        )
