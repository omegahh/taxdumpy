"""
Description: NCBI Taxonomy toolkit for parsing database, display taxid, show-lineage, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import re
import pickle
import logging
from pathlib import Path
from functools import cached_property
from typing import Dict, List, Set, Tuple

from rapidfuzz import process, fuzz

from taxdumpy.basic import (
    Node,
    TaxDbError,
    TaxidError,
    TaxdumpFileError,
    ValidationError,
)
from taxdumpy.ansi import u_str, m_color
from taxdumpy.database import TaxonomyDatabase

# Set up logging
logger = logging.getLogger(__name__)


class TaxDb(TaxonomyDatabase):
    """
    Create an object of the TaxDb class for NCBI taxonomy database operations.

    Args:
        taxdump_dir: Path to directory containing NCBI taxdump files
        fast: Use fast mode with pre-cached subset of data

    Raises:
        ValidationError: If taxdump_dir is invalid
        TaxdumpFileError: If required taxdump files are missing
        DatabaseCorruptionError: If database files are corrupted
    """

    # Required taxdump files
    REQUIRED_FILES = [
        "merged.dmp",
        "delnodes.dmp",
        "division.dmp",
        "nodes.dmp",
        "names.dmp",
    ]

    def __init__(self, taxdump_dir: Path | str, fast: bool = False) -> None:
        # Call parent constructor
        super().__init__(taxdump_dir)

        # Validate inputs
        self._validate_init_params(taxdump_dir, fast)

        self._fast = fast

        # Set up file paths
        self._taxdbf = [
            self._taxdump_dir / filename for filename in self.REQUIRED_FILES
        ]
        self._mrgef, self._delnf, self._divsf, self._nodef, self._namef = self._taxdbf
        self._pickle = self._taxdump_dir / (
            "taxdump_fast.pickle" if fast else "taxdump.pickle"
        )

        # Check files exist before proceeding
        self._check_taxdump()

        try:
            logger.info(f"Loading taxonomy database from {self._taxdump_dir}")
            self._taxid2nodes, self._old2news, self._delnodes = self._load_taxdump()
            logger.info(f"Successfully loaded {len(self._taxid2nodes)} taxonomy nodes")
        except Exception as e:
            logger.error(f"Failed to load taxonomy database: {e}")
            raise

    @staticmethod
    def _validate_init_params(taxdump_dir: Path | str, fast: bool) -> None:
        """Validate initialization parameters."""
        if not taxdump_dir:
            raise ValidationError("taxdump_dir", taxdump_dir, "non-empty path")

        if not isinstance(fast, bool):
            raise ValidationError("fast", fast, "boolean")

        taxdump_path = Path(taxdump_dir)
        if not taxdump_path.exists():
            raise ValidationError(
                "taxdump_dir", str(taxdump_path), "existing directory path"
            )

        if not taxdump_path.is_dir():
            raise ValidationError(
                "taxdump_dir", str(taxdump_path), "directory (not file)"
            )

    def _check_taxdump(self) -> None:
        """Check that required taxdump files exist and are readable."""
        # If pickle exists and is newer than source files, we're good
        if self._pickle.is_file():
            try:
                # Quick validation that pickle is readable
                with open(self._pickle, "rb") as f:
                    # Just read the first few bytes to check format
                    pickle.load(f)
                logger.debug(f"Found valid pickle file: {self._pickle}")
                return
            except (pickle.PickleError, EOFError, OSError) as e:
                logger.warning(f"Pickle file corrupted, will rebuild from source: {e}")
                # Remove corrupted pickle
                try:
                    self._pickle.unlink()
                except OSError:
                    pass

        # Check that all required files exist
        missing_files = []
        corrupted_files = []

        for filepath in self._taxdbf:
            if not filepath.exists():
                missing_files.append(filepath.name)
            elif filepath.stat().st_size == 0:
                corrupted_files.append(filepath.name)
            else:
                # Basic validation - check file starts with expected format
                try:
                    with open(filepath, "r") as f:
                        first_line = f.readline().strip()
                        # Different files have different formats, but all should have some tabs
                        if not first_line or "\t" not in first_line:
                            corrupted_files.append(filepath.name)
                except (OSError, UnicodeDecodeError) as e:
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

    def _load_taxdump(self):
        if self._pickle.is_file():
            with open(self._pickle, "rb") as fin:
                taxid2nodes, old2news, del_taxids = pickle.load(fin)
        else:
            taxid2nodes, old2news, del_taxids = self._import_nodes()
            # Save the imported data to pickle for future use
            try:
                self._save_pickle(taxid2nodes, old2news, del_taxids)
            except Exception as e:
                logger.warning(f"Failed to save pickle file: {e}")

        return taxid2nodes, old2news, del_taxids

    @cached_property
    def all_names(self) -> List[str]:
        return [node.name for node in self._taxid2nodes.values()]

    @cached_property
    def name2taxid(self) -> Dict[str, int]:
        return {node.name: taxid for taxid, node in self._taxid2nodes.items()}

    @cached_property
    def delnodes(self) -> set[int]:
        return self._delnodes

    @cached_property
    def max_taxid_strlen(self) -> int:
        return len(str(max(self._taxid2nodes.keys())))

    @cached_property
    def max_rank_strlen(self) -> int:
        return max(len(n.rank) for n in self._taxid2nodes.values())

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
                            logger.warning(
                                f"Malformed line {line_num} in {self._mrgef.name}: {line}"
                            )
                            continue

                        old_id, new_id = parts[0], parts[2]
                        old2new[int(old_id)] = int(new_id)

                    except (ValueError, IndexError) as e:
                        logger.warning(
                            f"Error parsing line {line_num} in {self._mrgef.name}: {line} ({e})"
                        )
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
                            logger.warning(
                                f"Malformed line {line_num} in {self._divsf.name}: {line}"
                            )
                            continue

                        div_id, div_name = parts[0], parts[2]
                        div2codes[int(div_id)] = div_name

                    except (ValueError, IndexError) as e:
                        logger.warning(
                            f"Error parsing line {line_num} in {self._divsf.name}: {line} ({e})"
                        )
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
                        logger.warning(
                            f"Error parsing line {line_num} in {self._delnf.name}: {line} ({e})"
                        )
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
                            logger.warning(
                                f"Malformed line {line_num} in {self._namef.name}: {line}"
                            )
                            continue

                        taxid = int(parts[0])
                        name = parts[2].strip()
                        name_class = parts[6].strip()

                        if not name:
                            logger.warning(
                                f"Empty name at line {line_num} in {self._namef.name}"
                            )
                            continue

                        if name_class == "scientific name":
                            sci_names[taxid] = name
                        elif name_class == "equivalent name":
                            eq_names.setdefault(taxid, []).append(name)
                        elif name_class == "acronym":
                            acr_names.setdefault(taxid, []).append(name)
                        # Ignore other name classes

                    except (ValueError, IndexError) as e:
                        logger.warning(
                            f"Error parsing line {line_num} in {self._namef.name}: {line} ({e})"
                        )
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
                    equal=(
                        "|".join(eq_names[taxid]) if taxid in eq_names.keys() else None
                    ),
                    acronym=(
                        "|".join(acr_names[taxid])
                        if taxid in acr_names.keys()
                        else None
                    ),
                    division=div2codes[divid],
                )

                taxid2nodes[taxid] = node
        # Finished import all current taxid nodes, check for conflicts
        cur_taxids = set(taxid2nodes.keys())
        overlap = old_taxids.intersection(cur_taxids)
        if overlap:
            raise TaxDbError(
                f"Database integrity error: Current taxids have legacy taxids: {sorted(overlap)}"
            )

        return taxid2nodes, old2news, del_taxids

    def _save_pickle(self, taxid2nodes, old2news, del_taxids):
        """Save processed data to pickle file."""
        with open(self._pickle, "wb") as fout:
            pickle.dump(
                [taxid2nodes, old2news, del_taxids],
                fout,
                protocol=pickle.HIGHEST_PROTOCOL,
            )
        logger.debug(f"Saved pickle file: {self._pickle}")

    def dump_taxdump(self):
        """Manually save the current database to pickle file."""
        print(f"Writing to {self._pickle}")
        self._save_pickle(self._taxid2nodes, self._old2news, self.delnodes)
        print(f"Taxdump dumped!")

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

    @staticmethod
    def _validate_taxid(taxid: int | str) -> int:
        """Validate and convert taxid to integer."""
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

        if not isinstance(taxid, int):
            raise ValidationError("taxid", type(taxid).__name__, "integer")

        if taxid < 1:
            raise ValidationError("taxid", taxid, "positive integer")

        return taxid

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
        # Validate inputs
        if not isinstance(query, str):
            raise ValidationError("query", type(query).__name__, "string")

        if not query.strip():
            logger.warning("Empty search query provided")
            return []

        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit", limit, "positive integer")

        if limit > 1000:
            logger.warning(f"Search limit {limit} is very high, limiting to 1000")
            limit = 1000

        try:
            # Perform fuzzy search
            results = process.extract(
                query.strip(), self.all_names, scorer=fuzz.WRatio, limit=limit
            )

            # Format results
            formatted_results = []
            for name, score, _ in results:
                try:
                    taxid = self.name2taxid[name]
                    formatted_results.append(
                        {"name": name, "taxid": taxid, "score": score}
                    )
                except KeyError:
                    logger.warning(
                        f"Name '{name}' found in search but not in name2taxid mapping"
                    )
                    continue

            logger.debug(
                f"Fuzzy search for '{query}' returned {len(formatted_results)} results"
            )
            return formatted_results

        except Exception as e:
            logger.error(f"Error during fuzzy search: {e}")
            raise TaxDbError(f"Fuzzy search failed: {str(e)}")

    def fuzzy_search(self, query: str, limit: int = 10) -> None:
        """
        Print fuzzy search results to console.

        Args:
            query: Search keyword
            limit: Maximum number of results to display
        """
        try:
            results = self._rapid_fuzz(query, limit)

            if not results:
                print(f"No results found for '{query}'")
                return

            for result in results:
                tid = result["taxid"]
                name = str(result["name"])
                try:
                    node = self.get_node(tid)
                    # Highlight matching text
                    col = re.sub(query, m_color, name, flags=re.IGNORECASE)
                    print(
                        f"{tid:<{self.max_taxid_strlen}}\t{node.rank:<{self.max_rank_strlen}}\t{col}"
                    )
                except Exception as e:
                    logger.warning(f"Error displaying result for taxid {tid}: {e}")

        except Exception as e:
            print(f"Search error: {e}")
            logger.error(f"Fuzzy search display failed: {e}")
