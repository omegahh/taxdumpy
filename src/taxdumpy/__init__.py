"""Taxdumpy: A Python package for parsing NCBI taxdump database and resolving taxonomy lineage.
"""

__version__ = "0.1.0b0"

from taxdumpy.taxdumpy import (
        TaxDb,
        Taxon
        )


__all__ = [
        # Data classes
        "TaxDb",
        "Taxon"
        ]
