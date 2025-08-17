"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage.
"""

__version__ = "0.1.1"

from taxdumpy.taxdb import TaxDb, TaxDbError, TaxidError
from taxdumpy.taxsqlite import TaxSQLite
from taxdumpy.taxon import Taxon
from taxdumpy.functions import upper_rank_id

__all__ = [
        # Exceptions
        "TaxDbError",
        "TaxidError",
        # Data classes
        "TaxDb",
        "TaxSQLite",
        "Taxon",
        # utilities
        "upper_rank_id"
        ]
