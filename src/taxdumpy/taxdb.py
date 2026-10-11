"""
Description: NCBI Taxonomy toolkit for parsing database, display taxid, show-lineage, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import logging
import pickle
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Set, Tuple

from rapidfuzz import fuzz, process

from taxdumpy.ansi import u_str
from taxdumpy.basic import (
    Node,
    TaxDbError,
    TaxdumpFileError,
    TaxidError,
    ValidationError,
)
from taxdumpy.cache import atomic_pickle_dump, cache_is_stale, source_signature
from taxdumpy.database import SearchResult, TaxonomyDatabase

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

    # Required taxdump files
    REQUIRED_FILES = [
        "merged.dmp",
        "delnodes.dmp",
        "division.dmp",
        "nodes.dmp",
        "names.dmp",
    ]

    def __init__(self, taxdump_dir: Path | str, fast: bool = False, verbose: bool = False) -> None:
        self._configure(taxdump_dir, fast, verbose)
        self._taxid2nodes, self._old2news, self._delnodes = self._load_cached_taxdump()

    def _configure(self, taxdump_dir: Path | str, fast: bool, verbose: bool) -> None:
        """Set up a database reader without creating any cache files."""
        super().__init__(taxdump_dir)
        self._validate_init_params(taxdump_dir, fast)
        self._fast = fast
        self._verbose = verbose

        self._taxdbf = [self._taxdump_dir / filename for filename in self.REQUIRED_FILES]
        self._mrgef, self._delnf, self._divsf, self._nodef, self._namef = self._taxdbf
        self._pickle = self._taxdump_dir / ("taxdump_fast.pickle" if fast else "taxdump.pickle")

    @classmethod
    def _build_cache(cls, taxdump_dir: Path | str, verbose: bool = False) -> "TaxDb":
        """Build the full pickle cache for the CLI cache command."""
        database = cls.__new__(cls)
        database._configure(taxdump_dir, False, verbose)
        database._check_taxdump()
        database._source_signature = source_signature(database._taxdump_dir)
        database._taxid2nodes, database._old2news, database._delnodes = database._import_nodes()
        database._save_pickle(database._taxid2nodes, database._old2news, database._delnodes)
        return database

    @classmethod
    def _build_fast_cache(cls, taxdump_dir: Path | str, taxids, verbose: bool = False) -> int:
        """Build a filtered pickle cache for the CLI cache command."""
        database = cls._build_cache(taxdump_dir, verbose=verbose)
        return database._write_fast_cache(taxids)

    @staticmethod
    def _validate_init_params(taxdump_dir: Path | str, fast: bool) -> None:
        """Validate initialization parameters."""
        if not taxdump_dir:
            raise ValidationError("taxdump_dir", taxdump_dir, "non-empty path")

        if not isinstance(fast, bool):
            raise ValidationError("fast", fast, "boolean")

        taxdump_path = Path(taxdump_dir)
        if not taxdump_path.exists():
            raise ValidationError("taxdump_dir", str(taxdump_path), "existing directory path")

        if not taxdump_path.is_dir():
            raise ValidationError("taxdump_dir", str(taxdump_path), "directory (not file)")

    def _check_taxdump(self) -> None:
        """Check that required taxdump files exist and are readable."""
        # Check that all required files exist
        missing_files = []
        corrupted_files = []

        for filepath in self._taxdbf:
            if not filepath.exists():
                missing_files.append(filepath.name)
            elif filepath.stat().st_size == 0 and filepath.name not in {"merged.dmp", "delnodes.dmp"}:
                corrupted_files.append(filepath.name)
            else:
                # Basic validation - check file starts with expected format
                try:
                    with open(filepath, "r") as f:
                        first_line = f.readline().strip()
                        # Different files have different formats, but all should have some tabs
                        if not first_line and filepath.name in {"merged.dmp", "delnodes.dmp"}:
                            continue
                        if not first_line or "\t" not in first_line:
                            corrupted_files.append(filepath.name)
                except (OSError, UnicodeDecodeError):
                    corrupted_files.append(filepath.name)

        # Report issues
        if missing_files:
            raise TaxdumpFileError(
                filename=", ".join(missing_files),
                issue="Files not found",
                solution="Download NCBI taxdump files from ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz",
            )

        if corrupted_files:
            raise TaxdumpFileError(
                filename=", ".join(corrupted_files),
                issue="Files appear to be corrupted or have invalid format",
                solution="Re-download NCBI taxdump files",
            )

    def __repr__(self):
        repr_str = f"Taxdump (Dict) Database from {u_str(self._taxdump_dir)}\n"
        repr_str += f"\tImported nodes: {len(self):,}\n"
        repr_str += f"\tLegacy nodes: {len(self._old2news):,}\n"
        repr_str += f"\tDeleted nodes: {len(self.delnodes):,}"
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
            if isinstance(data, dict):
                if data.get("format_version") != 1:
                    raise ValueError("Unsupported pickle cache version")
                taxid2nodes, old2news, del_taxids = data["nodes"], data["merged"], data["deleted"]
                signature = data["sources"]
            else:
                taxid2nodes, old2news, del_taxids = data
                signature = None
            if not isinstance(taxid2nodes, dict) or not isinstance(old2news, dict) or not isinstance(del_taxids, set):
                raise ValueError("Invalid pickle cache structure")
            if cache_is_stale(self._pickle, signature):
                raise TaxdumpFileError(
                    self._pickle.name,
                    "Cache is stale",
                    f"Run 'taxdumpy cache -d {self._taxdump_dir}' to rebuild it",
                )
            self._source_signature = signature if signature is not None else source_signature(self._taxdump_dir)
            return taxid2nodes, old2news, del_taxids
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
                ("Fast cache is unreadable" if self._fast else f"Cache is unreadable: {e}"),
                f"Run 'taxdumpy cache -d {self._taxdump_dir}' to rebuild it",
            ) from e

    @cached_property
    def all_names(self) -> List[str]:
        return [node.name for node in self._taxid2nodes.values()]

    @cached_property
    def _search_names(self) -> dict[int, str]:
        return {taxid: node.name for taxid, node in self._taxid2nodes.items()}

    @cached_property
    def name2taxid(self) -> Dict[str, int]:
        return {node.name: taxid for taxid, node in self._taxid2nodes.items()}

    @cached_property
    def delnodes(self) -> set[int]:
        return self._delnodes

    @cached_property
    def max_taxid_strlen(self) -> int:
        return len(str(max(self._taxid2nodes))) if self._taxid2nodes else 0

    @cached_property
    def max_rank_strlen(self) -> int:
        return max((len(n.rank) for n in self._taxid2nodes.values()), default=0)

    def _import_merged(self) -> Dict[int, int]:
        """Import merged taxid mappings with error handling."""
        old2new = {}
        line_num = 0

        try:
            with open(self._mrgef, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split("\t")
                        if len(parts) < 3:
                            logger.warning(f"Malformed line {line_num} in {self._mrgef.name}: {line}")
                            continue

                        old_id, new_id = parts[0], parts[2]
                        old2new[int(old_id)] = int(new_id)

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error parsing line {line_num} in {self._mrgef.name}: {line} ({e})")
                        continue

        except (OSError, UnicodeDecodeError) as e:
            raise TaxdumpFileError(
                self._mrgef.name,
                f"Cannot read file: {e}",
                "Check file permissions and encoding",
            )

        logger.debug(f"Loaded {len(old2new):,} merged taxid mappings")
        return old2new

    def _import_divcodes(self) -> Dict[int, str]:
        """Import division codes with error handling."""
        div2codes = {}
        line_num = 0

        try:
            with open(self._divsf, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split("\t")
                        if len(parts) < 3:
                            logger.warning(f"Malformed line {line_num} in {self._divsf.name}: {line}")
                            continue

                        div_id, div_name = parts[0], parts[2]
                        div2codes[int(div_id)] = div_name

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error parsing line {line_num} in {self._divsf.name}: {line} ({e})")
                        continue

        except (OSError, UnicodeDecodeError) as e:
            raise TaxdumpFileError(
                self._divsf.name,
                f"Cannot read file: {e}",
                "Check file permissions and encoding",
            )

        logger.debug(f"Loaded {len(div2codes):,} division codes")
        return div2codes

    def _import_delnodes(self) -> Set[int]:
        """Import deleted taxids with error handling."""
        del_taxids = set()
        line_num = 0

        try:
            with open(self._delnf, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        taxid = int(line.split("\t")[0])
                        del_taxids.add(taxid)

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error parsing line {line_num} in {self._delnf.name}: {line} ({e})")
                        continue

        except (OSError, UnicodeDecodeError) as e:
            raise TaxdumpFileError(
                self._delnf.name,
                f"Cannot read file: {e}",
                "Check file permissions and encoding",
            )

        logger.debug(f"Loaded {len(del_taxids):,} deleted taxids")
        return del_taxids

    def _import_names(
        self,
    ) -> Tuple[Dict[int, str], Dict[int, List[str]], Dict[int, List[str]]]:
        """Import taxonomic names with error handling."""
        sci_names, eq_names, acr_names = {}, {}, {}
        line_num = 0

        try:
            with open(self._namef, "r", encoding="utf-8", errors="replace") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = line.split("\t")
                        if len(parts) < 7:
                            logger.warning(f"Malformed line {line_num} in {self._namef.name}: {line}")
                            continue

                        taxid = int(parts[0])
                        name = parts[2].strip()
                        name_class = parts[6].strip()

                        if not name:
                            logger.warning(f"Empty name at line {line_num} in {self._namef.name}")
                            continue

                        if name_class == "scientific name":
                            sci_names[taxid] = name
                        elif name_class == "equivalent name":
                            eq_names.setdefault(taxid, []).append(name)
                        elif name_class == "acronym":
                            acr_names.setdefault(taxid, []).append(name)
                        # Ignore other name classes

                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error parsing line {line_num} in {self._namef.name}: {line} ({e})")
                        continue

        except (OSError, UnicodeDecodeError) as e:
            raise TaxdumpFileError(
                self._namef.name,
                f"Cannot read file: {e}",
                "Check file permissions and encoding",
            )

        logger.debug(
            f"Loaded {len(sci_names):,} scientific names, {len(eq_names):,} equivalent names, {len(acr_names):,} acronyms"
        )
        return sci_names, eq_names, acr_names

    def _import_nodes(self) -> tuple[dict[int, Node], dict[int, int], set[int]]:
        old2news = self._import_merged()
        div2codes = self._import_divcodes()
        del_taxids = self._import_delnodes()
        old_taxids = set(old2news.keys())
        sci_names, eq_names, acr_names = self._import_names()
        taxid2nodes = {}
        with open(self._nodef, "r") as f:
            for line in f:
                line = line.split("\t")
                taxid = int(line[0])
                parent = int(line[2])
                rank = line[4]
                divid = int(line[8])

                node = Node(
                    taxid=taxid,
                    parent=old2news[parent] if parent in old_taxids else parent,
                    rank=rank,
                    name=sci_names[taxid],
                    equal=("|".join(eq_names[taxid]) if taxid in eq_names.keys() else None),
                    acronym=("|".join(acr_names[taxid]) if taxid in acr_names.keys() else None),
                    division=div2codes.get(divid, f"UNKNOWN_{divid}"),
                )

                taxid2nodes[taxid] = node
        # Finished import all current taxid nodes, check for conflicts
        cur_taxids = set(taxid2nodes.keys())
        overlap = old_taxids.intersection(cur_taxids)
        if overlap:
            raise TaxDbError(f"Database integrity error: Current taxids have legacy taxids: {sorted(overlap)}")

        return taxid2nodes, old2news, del_taxids

    def _save_pickle(self, taxid2nodes, old2news, del_taxids, *, path=None):
        """Save processed data to pickle file."""
        atomic_pickle_dump(
            path or self._pickle,
            {
                "format_version": 1,
                "sources": self._source_signature,
                "nodes": taxid2nodes,
                "merged": old2news,
                "deleted": del_taxids,
            },
        )
        logger.debug(f"Saved pickle file: {self._pickle}")

    def _write_fast_cache(self, taxids) -> int:
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
        self._save_pickle(nodes, self._old2news, self.delnodes, path=self._taxdump_dir / "taxdump_fast.pickle")
        return len(nodes)

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
        if validated_taxid in self.delnodes:
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

    def _rapid_fuzz(self, query: str, limit: int = 10) -> list[SearchResult]:
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
        # Validate inputs
        if not isinstance(query, str):
            raise ValidationError("query", type(query).__name__, "string")

        if not query.strip():
            logger.warning("Empty search query provided")
            return []

        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit", limit, "positive integer")

        if limit > 1000:
            logger.warning(f"Search limit {limit} is very high, limiting to 1000")
            limit = 1000

        try:
            # Perform fuzzy search
            results = process.extract(query.strip(), self._search_names, scorer=fuzz.WRatio, limit=limit)
            formatted_results = [{"name": name, "taxid": taxid, "score": score} for name, score, taxid in results]

            logger.debug(f"Fuzzy search for '{query}' returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Error during fuzzy search: {e}")
            raise TaxDbError(f"Fuzzy search failed: {str(e)}")
