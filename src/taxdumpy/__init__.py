"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage."""

__version__ = "1.1.6"

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
from taxdumpy.functions import upper_rank_id
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
    # utilities
    "upper_rank_id",
]
