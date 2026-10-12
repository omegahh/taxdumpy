"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage."""

__version__ = "1.4.0"

from taxdumpy.basic import (
    RC,
    DatabaseCorruptionError,
    TaxDbError,
    TaxdumpFileError,
    TaxdumpyError,
    TaxidError,
    TaxRankError,
    ValidationError,
)
from taxdumpy.database import TaxonomyDatabase, open_database
from taxdumpy.functions import (
    build_children_index,
    descendant_nodes,
    descendants,
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
from taxdumpy.taxdb import TaxDb
from taxdumpy.taxon import Taxon
from taxdumpy.taxsqlite import TaxSQLite

__all__ = [
    # Exceptions
    "TaxdumpyError",
    "TaxDbError",
    "TaxidError",
    "TaxRankError",
    "TaxdumpFileError",
    "DatabaseCorruptionError",
    "ValidationError",
    # Database classes
    "TaxonomyDatabase",
    "TaxDb",
    "TaxSQLite",
    "Taxon",
    # Rank code
    "RC",
    # Database readers
    "open_database",
    # Rank utility functions
    "upper_rank_id",
    "get_rank_taxid",
    "get_canonical_ranks",
    "get_closest_rank",
    "get_rank_or_closest",
    "get_all_ranks",
    "find_rank_in_lineage",
    "get_rank_distance",
    "group_taxids_by_rank",
    # Subtree traversal
    "descendants",
    "descendant_nodes",
    "build_children_index",
]
