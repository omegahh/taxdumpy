"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage.
"""

__version__ = "0.1.1"

from taxdumpy.taxdb import TaxDb
from taxdumpy.taxsqlite import TaxSQLite
from taxdumpy.taxon import Taxon
from taxdumpy.functions import upper_rank_id
from taxdumpy.basic import (
    TaxdumpyError, TaxDbError, TaxidError, TaxRankError,
    TaxdumpFileError, DatabaseCorruptionError, ValidationError
)

__all__ = [
        # Exceptions
        "TaxdumpyError",
        "TaxDbError",
        "TaxidError", 
        "TaxRankError",
        "TaxdumpFileError",
        "DatabaseCorruptionError",
        "ValidationError",
        # Data classes
        "TaxDb",
        "TaxSQLite",
        "Taxon",
        # utilities
        "upper_rank_id"
        ]
