"""
Description: NCBI Taxonomy toolkit for parsing database, display taxid, show-lineage, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

from taxdumpy.ansi      import b_str, r_str
from taxdumpy.taxdb     import TaxDb
from taxdumpy.taxsqlite import Node, TaxSQLite

class Taxon:
    """
    Create an object of the Taxon class.
    """
    # @line_profiler.profile
    def __init__(self, taxid: int, taxdb: TaxDb|TaxSQLite):
        # taxid, taxonomy node, and lineage
        self._taxid   = taxid
        self._node    = taxdb.get_node(taxid)
        self._lineage = self._find_lineage(taxdb)

    @property
    def taxid(self) -> int:
        return self._taxid

    @property
    def node(self) -> Node:
        return self._node

    @property
    def lineage(self) -> list[Node]:
        return self._lineage

    # other infered taxon attributes
    @property
    def update_taxid(self) -> int:
        return self.node.taxid

    @property
    def name(self) -> str:
        return self.node.name

    @property
    def rank(self) -> str:
        return self.node.rank

    @property
    def parent(self) -> int:
        return self.node.parent

    @property
    def acronym(self) -> str|None:
        return self.node.acronym

    @property
    def division(self) -> str:
        return self.node.division

    @property
    def is_legacy(self) -> bool:
        return self.taxid != self.node.taxid

    @property
    def has_species_level(self) -> bool:
        return "species" in self.rank_lineage

    @property
    def species_taxid(self) -> int:
        return self.taxid_lineage[self.rank_lineage.index("species")] if self.has_species_level else 0

    @property
    def taxid_lineage(self) -> list[int]:
        return [node.taxid for node in self.lineage]

    @property
    def rank_lineage(self) -> list[str]:
        return [node.rank for node in self.lineage]

    @property
    def name_lineage(self) -> list[str]:
        return [node.name for node in self.lineage]

    @property
    def _max_tlen(self) -> int:
        return max([len(str(t)) for t in self.taxid_lineage])

    @property
    def _max_rlen(self) -> int:
        return max([len(r) for r in self.rank_lineage])

    def __repr__(self):
        lineage_str_list = []
        for t, r, n in zip(self.taxid_lineage, self.rank_lineage, self.name_lineage):
            current_str = f"{t:<{self._max_tlen}}\t{r:<{self._max_rlen}}\t{n}"
            if t == self.node.taxid:
                if self.acronym:
                    current_str += f" ({self.acronym})"
                if self.is_legacy:
                    current_str += r_str(f" <- [{self.taxid} has been merged!]")
                current_str = b_str(current_str)
            lineage_str_list.append(current_str)
        return "\n".join(reversed(lineage_str_list))

    def __str__(self):
        print_str = f"{self.update_taxid:<10}\t{self.rank}\t{self.name}"
        if self.is_legacy:
            print_str += r_str(f" <- [{self.taxid} has been merged!]")
        return print_str

    def _find_lineage(self, taxdb: TaxDb|TaxSQLite) -> list[Node]:
        lineage = [self.node]
        current_taxid = lineage[-1].taxid
        while lineage[-1].parent != current_taxid:
            current_taxid = lineage[-1].parent
            lineage.append(taxdb.get_node(current_taxid))
        return lineage
