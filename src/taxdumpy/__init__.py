"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage."""

__version__ = "1.1.7"

from taxdumpy.basic import (
    DatabaseCorruptionError,
    TaxDbError,
    TaxdumpFileError,
    TaxdumpyError,
    TaxidError,
    TaxRankError,
    ValidationError,
)
from taxdumpy.database import TaxonomyDatabase, create_database
from taxdumpy.functions import (
    find_rank_in_lineage,
    get_all_ranks,
    get_canonical_ranks,
    get_closest_rank,
    get_rank_distance,
    get_rank_or_closest,
    get_rank_taxid,
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
    # Factory functions
    "create_database",
    # Rank utility functions
    "upper_rank_id",
    "get_rank_taxid",
    "get_canonical_ranks",
    "get_closest_rank",
    "get_rank_or_closest",
    "get_all_ranks",
    "find_rank_in_lineage",
    "get_rank_distance",
]
