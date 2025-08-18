"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage."""

__version__ = "1.1.5"

from taxdumpy.taxdb import TaxDb
from taxdumpy.taxsqlite import TaxSQLite
from taxdumpy.taxon import Taxon
from taxdumpy.functions import upper_rank_id
from taxdumpy.basic import (
    TaxdumpyError,
    TaxDbError,
    TaxidError,
    TaxRankError,
    TaxdumpFileError,
    DatabaseCorruptionError,
    ValidationError,
)
from taxdumpy.database import TaxonomyDatabase, create_database

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
