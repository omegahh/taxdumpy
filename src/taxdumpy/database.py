"""Abstract base class for taxonomy database backends."""

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from functools import cached_property
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, TypedDict, TypeVar

from rapidfuzz import fuzz, process

from taxdumpy.ansi import m_color
from taxdumpy.basic import Node, TaxDbError, TaxidError, ValidationError

_T = TypeVar("_T")


class SearchResult(TypedDict):
    name: str
    taxid: int
    score: float


def abstract_cached_property(func: Callable[[Any], _T]) -> "cached_property[_T]":
    """Declare a `cached_property` that ABCMeta treats as abstract.

    Stacking `@cached_property` over `@abstractmethod` does not work:
    `cached_property` does not propagate `__isabstractmethod__`, so ABCMeta
    never sees the member and silently stops enforcing it. Setting the flag
    on the descriptor makes the contract real, while keeping the type a plain
    `cached_property` so subclass implementations remain assignable.
    """
    prop = cached_property(func)
    prop.__isabstractmethod__ = True  # type: ignore[attr-defined]
    return prop


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
            taxdump_dir: Path to directory containing caches built from NCBI taxdump files
            **kwargs: Backend-specific parameters
        """
        if taxdump_dir is None or (isinstance(taxdump_dir, str) and not taxdump_dir.strip()):
            raise ValidationError("taxdump_dir", taxdump_dir, "non-empty path")
        try:
            path = Path(taxdump_dir)
        except TypeError:
            raise ValidationError("taxdump_dir", type(taxdump_dir).__name__, "path-like value")
        if not path.exists():
            raise ValidationError("taxdump_dir", str(path), "existing directory path")
        if not path.is_dir():
            raise ValidationError("taxdump_dir", str(path), "directory (not file)")
        self._taxdump_dir = path.resolve()

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
    def get_names(self, taxid: int | str) -> dict[str, tuple[str, ...]]:
        """Return a taxid's names grouped by their NCBI name class.

        Includes the scientific name and every alternative name class present
        in names.dmp. Values are sorted, distinct tuples; absent classes are
        omitted. The returned dictionary can be changed without modifying the
        database. Merged taxids resolve to the current taxid; validation and
        deleted/unknown taxid errors follow get_node().
        """
        raise NotImplementedError

    def fuzzy_search(self, query: str, limit: int = 10) -> None:
        """Print highlighted matches, propagating validation and database errors."""
        results = self.search(query, limit)
        if not results:
            print(f"No results found for '{query}'")
            return
        for result in results:
            taxid = result["taxid"]
            # _search_names is defined over current nodes, but tolerate a
            # backend/cache that contains an obsolete candidate so one bad
            # row does not abort an otherwise useful search display.
            try:
                node = self.get_node(taxid)
            except TaxidError:
                continue
            name = re.sub(re.escape(query.strip()), m_color, result["name"], flags=re.IGNORECASE)
            print(f"{taxid:<{self.max_taxid_strlen}}\t{node.rank:<{self.max_rank_strlen}}\t{name}")

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Return name, taxid and similarity score for each fuzzy match.

        Scores range from 0 to 100. Each taxid is a distinct candidate even
        when scientific names are identical. Results are ordered by score.
        ``limit`` must be a positive integer; results are not capped at an
        arbitrary backend-specific maximum.
        Raises ValidationError for invalid inputs and TaxDbError on failure.
        """
        return self._rapid_fuzz(query, limit)

    def _rapid_fuzz(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Score distinct taxids using the backend's cached scientific names."""
        if not isinstance(query, str):
            raise ValidationError("query", type(query).__name__, "string")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit", limit, "positive integer")
        if not query.strip():
            return []
        # Materialize the backend cache outside the fuzzy-matching error
        # boundary.  Database/cache failures should retain their original
        # exception instead of being reported as a matching failure.
        names = self._search_names
        try:
            results = process.extract(query.strip(), names, scorer=fuzz.WRatio, limit=limit)
        except Exception as error:
            raise TaxDbError(f"Fuzzy search failed: {error}") from error
        return [{"name": name, "taxid": taxid, "score": score} for name, score, taxid in results]

    @abstract_cached_property
    def _search_names(self) -> dict[int, str]:
        """Scientific-name candidates, keyed by taxid to preserve homonyms."""
        raise NotImplementedError

    @cached_property
    def _all_names_values(self) -> tuple[str, ...]:
        """Cache the values snapshot while keeping ``all_names`` independent."""
        return tuple(self._search_names.values())

    @property
    def all_names(self) -> list[str]:
        """Return an independent list of scientific names, including homonyms."""
        return list(self._all_names_values)

    @cached_property
    def name2taxids(self) -> Mapping[str, tuple[int, ...]]:
        """Read-only mapping of scientific names to all matching taxids."""
        names = {}
        for taxid, name in self._search_names.items():
            names.setdefault(name, []).append(taxid)
        return MappingProxyType({name: tuple(sorted(taxids)) for name, taxids in names.items()})

    @abstractmethod
    def iter_parent_pairs(self) -> Iterable[tuple[int, int]]:
        """Yield ``(child_taxid, parent_taxid)`` pairs for current nodes.

        Self loops and obsolete IDs are excluded.  The child-first order is
        part of the backend contract and is consumed by ``children_index``.
        """
        raise NotImplementedError

    @cached_property
    def children_index(self) -> Mapping[int, tuple[int, ...]]:
        """Explicitly materialize a read-only index for repeated global traversal."""
        children = {}
        for taxid, parent in self.iter_parent_pairs():
            children.setdefault(parent, []).append(taxid)
        return MappingProxyType({parent: tuple(sorted(ids)) for parent, ids in children.items()})

    def children_for(self, parents: list[int]) -> list[int]:
        """Return current children in parent order, with each sibling group sorted."""
        children = self.children_index
        return [child for parent in parents for child in children.get(parent, ())]

    @abstract_cached_property
    def delnodes(self) -> frozenset[int]:
        """Get set of deleted taxids."""
        raise NotImplementedError

    @abstract_cached_property
    def max_taxid_strlen(self) -> int:
        """Get maximum string length of taxids for formatting."""
        raise NotImplementedError

    @abstract_cached_property
    def max_rank_strlen(self) -> int:
        """Get maximum string length of ranks for formatting."""
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        """Return number of taxonomy nodes in database."""
        pass

    @abstractmethod
    def __repr__(self) -> str:
        """Return string representation of database."""
        pass

    @staticmethod
    def _validate_taxid(taxid: int | str) -> int:
        """Validate and convert taxid to integer.

        Args:
            taxid: NCBI taxonomy ID (integer or string)

        Returns:
            Validated taxid as integer

        Raises:
            ValidationError: If taxid is invalid format
        """
        if taxid is None:
            raise ValidationError("taxid", taxid, "non-None value")

        # Convert string to int if possible
        if isinstance(taxid, str):
            if not taxid.strip():
                raise ValidationError("taxid", taxid, "non-empty string")
            try:
                taxid = int(taxid.strip())
            except ValueError:
                raise ValidationError("taxid", taxid, "integer or numeric string")

        if isinstance(taxid, bool) or not isinstance(taxid, int):
            raise ValidationError("taxid", type(taxid).__name__, "integer")

        if taxid < 1:
            raise ValidationError("taxid", taxid, "positive integer")

        return taxid

    def close(self) -> None:
        """Release derived global structures owned by this database instance."""
        for name in (
            "_search_names",
            "_all_names_values",
            "name2taxids",
            "children_index",
            "delnodes",
            "max_taxid_strlen",
            "max_rank_strlen",
        ):
            self.__dict__.pop(name, None)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def open_database(taxdump_dir: Path | str, backend: str = "sqlite", **kwargs) -> TaxonomyDatabase:
    """
    Open an existing cache with the requested database backend.

    Build caches first with ``taxdumpy cache -d PATH``. This factory is for
    opening a backend in a Python program, especially for batch operations; it
    never parses source taxdump files or creates cache files.

    Args:
        taxdump_dir: Path to directory containing caches built from NCBI taxdump files
        backend: Database backend to use ("sqlite"/"sql" or "dict"/"memory"/"pickle")
        **kwargs: Backend-specific parameters

    Returns:
        TaxonomyDatabase instance

    Raises:
        ValidationError: If parameters or the backend are invalid
        TaxdumpFileError: If the cache is missing, stale, or unreadable
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
        raise ValidationError("backend", backend, f"one of: {', '.join(valid_backends)}")
