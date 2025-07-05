"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage.
"""

__version__ = "0.1.0"

from taxdumpy.taxdb import TaxDb, TaxDbError
from taxdumpy.taxon import Taxon

__all__ = [
        # Exceptions
        "TaxDbError",
        # Data classes
        "TaxDb",
        "Taxon"
        ]
