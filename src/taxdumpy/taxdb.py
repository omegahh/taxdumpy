"""
Description: NCBI Taxonomy toolkit for parsing database, display taxid, show-lineage, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import logging
import os
import pickle
import tempfile
from functools import cached_property
from pathlib import Path

from taxdumpy.ansi import u_str
from taxdumpy.basic import (
    Node,
    TaxdumpFileError,
    TaxidError,
    ValidationError,
)
from taxdumpy.cache import CACHE_FORMAT_VERSION, atomic_pickle_dump, cache_is_stale, source_signature
from taxdumpy.database import TaxonomyDatabase
from taxdumpy.parsers import check_sources, deleted_rows, division_rows, merged_rows, name_rows, node_rows

# Set up logging
logger = logging.getLogger(__name__)


class TaxDb(TaxonomyDatabase):
    """
    Create an object of the TaxDb class for NCBI taxonomy database operations.

    Args:
        taxdump_dir: Path to directory containing caches built from NCBI taxdump files
        fast: Use fast mode with pre-cached subset of data
        verbose: If True, log INFO messages during initialization (default: False)

    Raises:
        ValidationError: If taxdump_dir is invalid
        TaxdumpFileError: If the cache is missing, stale, or unreadable
    """

    def __init__(self, taxdump_dir: Path | str, fast: bool = False, verbose: bool = False) -> None:
        self._configure(taxdump_dir, fast)
        self._taxid2nodes, self._old2news, self._delnodes, self._names_by_class = self._load_cached_taxdump()
        if verbose:
            logger.info("Loaded %s taxonomy nodes", len(self))

    def _configure(self, taxdump_dir: Path | str, fast: bool) -> None:
        """Set up a database reader without creating any cache files."""
        super().__init__(taxdump_dir)
        if not isinstance(fast, bool):
            raise ValidationError("fast", fast, "boolean")
        self._fast = fast

        self._pickle = self._taxdump_dir / ("taxdump_fast.pickle" if fast else "taxdump.pickle")

    @classmethod
    def _import_database(cls, taxdump_dir: Path | str, verbose: bool = False) -> "TaxDb":
        """Parse sources into memory without writing any cache."""
        database = cls.__new__(cls)
        database._configure(taxdump_dir, False)
        check_sources(database._taxdump_dir)
        database._source_signature = source_signature(database._taxdump_dir)
        database._taxid2nodes, database._old2news, database._delnodes = database._import_nodes()
        if verbose:
            logger.info("Imported %s taxonomy nodes", len(database))
        return database

    @classmethod
    def _build_cache(cls, taxdump_dir: Path | str, verbose: bool = False, *, output: Path | None = None) -> "TaxDb":
        """Build the full pickle cache for the CLI cache command."""
        database = cls._import_database(taxdump_dir, verbose)
        database._save_pickle(database._taxid2nodes, database._old2news, database._delnodes, path=output)
        return database

    @classmethod
    def _build_fast_cache(cls, taxdump_dir: Path | str, taxids, verbose: bool = False) -> int:
        """Reuse a valid full cache, or import sources without persisting it."""
        signature = source_signature(Path(taxdump_dir))
        try:
            database = cls(taxdump_dir, verbose=verbose)
        except TaxdumpFileError:
            database = cls._import_database(taxdump_dir, verbose)
        try:
            with tempfile.TemporaryDirectory(prefix=".taxdumpy-build-", dir=database._taxdump_dir) as directory:
                output = Path(directory) / "taxdump_fast.pickle"
                count = database._write_fast_cache(taxids, output=output)
                if signature != source_signature(database._taxdump_dir):
                    raise TaxdumpFileError(
                        "taxdump", "Sources changed during cache construction", "Retry with stable source files"
                    )
                os.replace(output, database._taxdump_dir / "taxdump_fast.pickle")
                return count
        finally:
            database.close()

    def __repr__(self):
        repr_str = f"Taxdump (Dict) Database from {u_str(self._taxdump_dir)}\n"
        repr_str += f"\tImported nodes: {len(self):,}\n"
        repr_str += f"\tLegacy nodes: {len(self._old2news):,}\n"
        repr_str += f"\tDeleted nodes: {len(self._delnodes):,}"
        return repr_str

    def __len__(self) -> int:
        return len(self._taxid2nodes)

    def _load_cached_taxdump(self):
        """Load an existing pickle cache; cache creation belongs to the CLI."""
        if not self._pickle.is_file():
            raise TaxdumpFileError(
                self._pickle.name,
                "Fast cache not found" if self._fast else "Cache not found",
                f"Run 'taxdumpy cache -d {self._taxdump_dir} -f FILE' before using fast mode"
                if self._fast
                else f"Run 'taxdumpy cache -d {self._taxdump_dir}' before using the Python API",
            )
        try:
            with open(self._pickle, "rb") as fin:
                data = pickle.load(fin)
            if not isinstance(data, dict) or data.get("format_version") != CACHE_FORMAT_VERSION:
                raise ValueError("Unsupported pickle cache version; rebuild with the current taxdumpy version")
            taxid2nodes, old2news, del_taxids = data["nodes"], data["merged"], data["deleted"]
            names_by_class = data["names_by_class"]
            signature = data["sources"]
            if not isinstance(taxid2nodes, dict) or not isinstance(old2news, dict) or not isinstance(del_taxids, set):
                raise ValueError("Invalid pickle cache structure")
            if not isinstance(names_by_class, dict) or not all(
                isinstance(name_class, str) and isinstance(names, dict) for name_class, names in names_by_class.items()
            ):
                raise ValueError("Invalid names cache structure")
            if cache_is_stale(self._pickle, signature):
                raise TaxdumpFileError(
                    self._pickle.name,
                    "Cache is stale",
                    f"Run 'taxdumpy cache -d {self._taxdump_dir} -f FILE' to rebuild the filtered cache"
                    if self._fast
                    else f"Run 'taxdumpy cache -d {self._taxdump_dir}' to rebuild it",
                )
            self._source_signature = signature if signature is not None else source_signature(self._taxdump_dir)
            return taxid2nodes, old2news, del_taxids, names_by_class
        except TaxdumpFileError:
            raise
        except (
            pickle.PickleError,
            EOFError,
            OSError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
            ImportError,
        ) as e:
            raise TaxdumpFileError(
                self._pickle.name,
                f"Fast cache is unreadable: {e}" if self._fast else f"Cache is unreadable: {e}",
                f"Run 'taxdumpy cache -d {self._taxdump_dir} -f FILE' to rebuild the filtered cache"
                if self._fast
                else f"Run 'taxdumpy cache -d {self._taxdump_dir}' to rebuild it",
            ) from e

    @cached_property
    def _search_names(self) -> dict[int, str]:
        return {taxid: node.name for taxid, node in self._taxid2nodes.items()}

    @cached_property
    def delnodes(self) -> frozenset[int]:
        return frozenset(self._delnodes)

    @cached_property
    def max_taxid_strlen(self) -> int:
        return len(str(max(self._taxid2nodes))) if self._taxid2nodes else 0

    @cached_property
    def max_rank_strlen(self) -> int:
        return max((len(n.rank) for n in self._taxid2nodes.values()), default=0)

    def _import_nodes(self) -> tuple[dict[int, Node], dict[int, int], set[int]]:
        old2news = dict(merged_rows(self._taxdump_dir))
        divisions = dict(division_rows(self._taxdump_dir))
        deleted = set(deleted_rows(self._taxdump_dir))
        scientific = {}
        alternatives = {}
        for taxid, name, name_class in name_rows(self._taxdump_dir):
            if name_class == "scientific name":
                if taxid in scientific and scientific[taxid] != name:
                    raise TaxdumpFileError("names.dmp", f"Multiple scientific names for TaxID {taxid}")
                scientific[taxid] = name
            else:
                alternatives.setdefault(name_class, {}).setdefault(taxid, set()).add(name)
        self._names_by_class = {
            name_class: {taxid: tuple(sorted(values)) for taxid, values in names.items()}
            for name_class, names in alternatives.items()
        }
        nodes = {}
        for taxid, parent, rank, division in node_rows(self._taxdump_dir, old2news, divisions):
            if taxid in nodes:
                raise TaxdumpFileError("nodes.dmp", f"Duplicate TaxID {taxid}")
            if taxid in old2news or taxid in deleted:
                raise TaxdumpFileError(
                    "nodes.dmp", f"Database integrity error: Current taxid {taxid} is merged or deleted"
                )
            if taxid not in scientific:
                raise TaxdumpFileError("names.dmp", f"Scientific name not found for TaxID {taxid}")
            names = self._names_by_class
            nodes[taxid] = Node(
                taxid,
                parent,
                rank,
                scientific[taxid],
                "|".join(names.get("equivalent name", {}).get(taxid, ())) or None,
                "|".join(names.get("acronym", {}).get(taxid, ())) or None,
                division,
            )
        return nodes, old2news, deleted

    def iter_parent_pairs(self):
        return (
            (taxid, node.parent)
            for taxid, node in self._taxid2nodes.items()
            if taxid != node.parent and taxid not in self._old2news and taxid not in self._delnodes
        )

    def _save_pickle(self, taxid2nodes, old2news, del_taxids, *, path=None, names_by_class=None):
        """Save processed data to pickle file."""
        atomic_pickle_dump(
            path or self._pickle,
            {
                "format_version": CACHE_FORMAT_VERSION,
                "sources": self._source_signature,
                "nodes": taxid2nodes,
                "merged": old2news,
                "deleted": del_taxids if isinstance(del_taxids, set) else set(del_taxids),
                "names_by_class": self._names_by_class if names_by_class is None else names_by_class,
            },
        )
        logger.debug(f"Saved pickle file: {self._pickle}")

    def _write_fast_cache(self, taxids, *, output: Path | None = None) -> int:
        """Cache selected taxids, their ancestors and descendants; return the node count.

        Resolve and validate every selection before writing. Descending multiple
        overlapping subtrees visits each node once, after one database-wide scan.
        This is used by the CLI cache command; API callers should only read the
        resulting cache with ``TaxDb(path, fast=True)``.
        """
        from taxdumpy.functions import build_children_index
        from taxdumpy.taxon import Taxon

        if self._fast:
            raise ValidationError("database", "fast", "a full TaxDb instance")
        roots = {self.get_node(taxid).taxid for taxid in taxids}
        if not roots:
            raise ValidationError("taxids", roots, "at least one existing taxid")
        kept = set()
        for root in roots:
            kept.update(Taxon(root, self).taxid_lineage)
        children = build_children_index(self)
        visited = set(roots)
        pending = list(roots)
        while pending:
            taxid = pending.pop()
            for child in children.get(taxid, ()):
                if child not in visited:
                    visited.add(child)
                    pending.append(child)
        kept.update(visited)
        nodes = {taxid: self._taxid2nodes[taxid] for taxid in sorted(kept)}
        names_by_class = {
            name_class: {taxid: values for taxid, values in names.items() if taxid in kept}
            for name_class, names in self._names_by_class.items()
        }
        self._save_pickle(
            nodes,
            self._old2news,
            self._delnodes,
            path=output or self._taxdump_dir / "taxdump_fast.pickle",
            names_by_class=names_by_class,
        )
        return len(nodes)

    def get_names(self, taxid: int | str) -> dict[str, tuple[str, ...]]:
        """Return scientific and alternative names for a resolved taxid."""
        node = self.get_node(taxid)
        result = {"scientific name": (node.name,)}
        for name_class, names in sorted(self._names_by_class.items()):
            values = names.get(node.taxid)
            if values:
                result[name_class] = values
        return result

    def get_node(self, taxid: int | str) -> Node:
        """
        Get a taxonomy node by taxid.

        Args:
            taxid: NCBI taxonomy ID (integer or string)

        Returns:
            Node object containing taxonomy information

        Raises:
            ValidationError: If taxid is invalid format
            TaxidError: If taxid is deleted, not found, or suggests alternatives
        """
        # Validate and convert taxid
        validated_taxid = self._validate_taxid(taxid)

        # Handle legacy/merged taxids
        original_taxid = validated_taxid
        if validated_taxid in self._old2news:
            validated_taxid = self._old2news[validated_taxid]
            logger.debug(f"Mapped legacy taxid {original_taxid} to {validated_taxid}")

        # Check if taxid has been deleted
        if validated_taxid in self._delnodes:
            raise TaxidError(
                original_taxid,
                f"TaxID {original_taxid} has been deleted from NCBI taxonomy",
                suggestion="Check NCBI taxonomy for updated taxid or use search function",
            )

        # Check if taxid exists in database
        if validated_taxid not in self._taxid2nodes:
            # Try to find similar taxids for suggestions
            suggestion = self._suggest_similar_taxids(validated_taxid)
            raise TaxidError(
                original_taxid,
                f"TaxID {original_taxid} is not found in the database",
                suggestion=suggestion,
            )

        return self._taxid2nodes[validated_taxid]

    def _suggest_similar_taxids(self, taxid: int) -> str:
        """Suggest similar taxids when lookup fails."""
        # Find taxids within a reasonable range
        similar_taxids = []
        search_range = 1000

        for candidate in range(max(1, taxid - search_range), taxid + search_range + 1):
            if candidate in self._taxid2nodes:
                similar_taxids.append(candidate)
                if len(similar_taxids) >= 3:
                    break

        if similar_taxids:
            similar_str = ", ".join(map(str, similar_taxids))
            return f"Try nearby taxids: {similar_str}, or use search function to find organisms"
        else:
            return "Use search function to find organisms by name"
