"""
Description: Functions for Taxdumpy
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-07-06 17:07:57
"""

from typing import Literal

from taxdumpy.basic import TaxRankError
from taxdumpy.taxon import Taxon
from taxdumpy.taxdb import TaxDb
# from taxdumpy.taxsqlite import TaxSQLite

RANKNAMES  = ["species", "genus", "family", "order", "class", "phylum", "superkingdom", "realm"]
RANK2LEVEL = {k: i for i,k in enumerate(RANKNAMES)}
LEVEL2RANK = {i: k for i,k in enumerate(RANKNAMES)}
def upper_rank_id(tax:  Taxon,
                  taxdb: TaxDb,
                  rank: Literal["species", "genus", "family", "order",
                                "class", "phylum", "superkingdom", "realm"],
                  ) -> int:
    curr_rank = tax.rank
    if curr_rank not in RANKNAMES:
        raise TaxRankError(f"TAXID={tax.taxid} ({curr_rank=}) is a non-canonical phylogenetic rank")
    assert rank in RANKNAMES, TaxRankError(f"{rank=} is a non-canonical phylogenetic rank")
    # and check rank levels
    curr_level = RANK2LEVEL[curr_rank]
    high_level = RANK2LEVEL[rank]
    if high_level <= curr_level:
        raise RuntimeError(f"{rank=} is in lower/equal level than {curr_rank=} in phylogenetic tree")
    # Get upper rank iteratively
    if rank in tax.rank_lineage:
        return tax.taxid_lineage[tax.rank_lineage.index(rank)]
    elif f"sub{rank}" in tax.rank_lineage:
        return tax.taxid_lineage[tax.rank_lineage.index(f"sub{rank}")]
    else:
        # neither rank nor sub-rank in the lineage
        temp_level = high_level
        temp_rank  = LEVEL2RANK[temp_level]
        while temp_level > curr_level:
            temp_level -= 1
            temp_rank = LEVEL2RANK[temp_level]
            if temp_rank in tax.rank_lineage:
                break;
        jump_taxid = tax.taxid_lineage[tax.rank_lineage.index(temp_rank)]
        for _ in range(high_level - temp_level):
            jump_taxid = Taxon(jump_taxid, taxdb).parent
        return jump_taxid
