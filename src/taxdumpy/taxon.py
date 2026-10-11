"""
Description: NCBI Taxonomy toolkit for parsing database, display taxid, show-lineage, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

from collections.abc import Mapping
from functools import cached_property
from types import MappingProxyType

from taxdumpy.ansi import b_str, r_str
from taxdumpy.basic import RC, Node, TaxDbError
from taxdumpy.database import TaxonomyDatabase
from taxdumpy.ranks import MPA_CODES as _MPA_CODES
from taxdumpy.ranks import RANK_CODES as _RANK_CODES


class Taxon:
    """
    Create an object of the Taxon class.
    """

    # @line_profiler.profile
    def __init__(self, taxid: int | str, taxdb: TaxonomyDatabase):
        # taxid, taxonomy node, and lineage
        self._taxdb = taxdb
        self._taxid = taxdb._validate_taxid(taxid)
        self._node = taxdb.get_node(self._taxid)
        self._lineage = self._find_lineage(taxdb)

    @property
    def taxid(self) -> int:
        return self._taxid

    @property
    def node(self) -> Node:
        return self._node

    @property
    def lineage(self) -> tuple[Node, ...]:
        return self._lineage

    # other infered taxon attributes
    @property
    def update_taxid(self) -> int:
        return self.node.taxid

    @property
    def name(self) -> str:
        return self.node.name

    @cached_property
    def names(self) -> Mapping[str, tuple[str, ...]]:
        """All NCBI name classes, loaded on first access while the database is open."""
        return MappingProxyType(self._taxdb.get_names(self.update_taxid))

    @property
    def synonyms(self) -> tuple[str, ...]:
        return self.names.get("synonym", ())

    @property
    def common_names(self) -> tuple[str, ...]:
        return self.names.get("common name", ())

    @property
    def genbank_common_names(self) -> tuple[str, ...]:
        return self.names.get("genbank common name", ())

    @property
    def equivalent_names(self) -> tuple[str, ...]:
        return self.names.get("equivalent name", ())

    @property
    def acronyms(self) -> tuple[str, ...]:
        return self.names.get("acronym", ())

    @property
    def rank(self) -> str:
        return self.node.rank

    @property
    def parent(self) -> int:
        return self.node.parent

    @property
    def acronym(self) -> str | None:
        return self.node.acronym

    @property
    def division(self) -> str:
        return self.node.division

    @property
    def rc(self) -> RC:
        """The rank code of this taxon."""
        return self.rankcode_lineage[0]

    @property
    def is_legacy(self) -> bool:
        return self.taxid != self.node.taxid

    @property
    def has_species_level(self) -> bool:
        return "species" in self.rank_lineage

    @property
    def species_taxid(self) -> int | None:
        """Return the species ancestor, or None when the lineage has none."""
        return self.taxid_lineage[self.rank_lineage.index("species")] if self.has_species_level else None

    @cached_property
    def taxid_lineage(self) -> tuple[int, ...]:
        return tuple(node.taxid for node in self.lineage)

    @cached_property
    def rank_lineage(self) -> tuple[str, ...]:
        return tuple(node.rank for node in self.lineage)

    @cached_property
    def name_lineage(self) -> tuple[str, ...]:
        return tuple(node.name for node in self.lineage)

    @cached_property
    def rankcode_lineage(self) -> tuple[RC, ...]:
        """
        Lineage as comparable RC (rank code) objects.

        Canonical ranks: R, D, K, P, C, O, F, G, S
        Non-canonical ranks append depth: R1, F1, F2, G1, S1

        RC objects are comparable: RC("R") < RC("S"), RC("F") < RC("F1")

        Returns:
            Tuple of RC objects from taxon to root
        """
        result: list[RC] = []
        rank_code = "R"
        rank_depth = 0

        # Build from root to taxon first
        for taxid, rank in zip(reversed(self.taxid_lineage), reversed(self.rank_lineage)):
            if taxid == 1:
                rank_code = "R"
                rank_depth = 0
            elif rank in _RANK_CODES:
                rank_code = _RANK_CODES[rank]
                rank_depth = 0
            else:
                rank_depth += 1

            if rank_depth == 0:
                result.append(RC(rank_code))
            else:
                result.append(RC(f"{rank_code}{rank_depth}"))

        # Reverse to match taxon->root order like other lineage properties
        result.reverse()
        return tuple(result)

    @cached_property
    def mpa_repr(self) -> str:
        """
        Lineage in MPA (Metaphlan) style format.

        Format: d__Domain|k__Kingdom|p__Phylum|c__Class|o__Order|f__Family|g__Genus|s__Species
        Only includes canonical ranks that exist in the lineage.

        Returns:
            MPA-style lineage string (e.g., "d__Eukaryota|k__Metazoa|...|s__Homo_sapiens")
        """
        parts = []
        for rank, name in zip(reversed(self.rank_lineage), reversed(self.name_lineage)):
            if rank in _MPA_CODES:
                code = _MPA_CODES[rank]
                clean_name = name.replace(" ", "_")
                parts.append(f"{code}__{clean_name}")
        return "|".join(parts)

    @property
    def _max_tlen(self) -> int:
        return max(len(str(t)) for t in self.taxid_lineage)

    @property
    def _max_rlen(self) -> int:
        return max(len(r) for r in self.rank_lineage)

    @property
    def _max_rclen(self) -> int:
        return max(len(str(rc)) for rc in self.rankcode_lineage)

    def __repr__(self):
        lineage_str_list = []
        rc_width, id_width, rank_width = self._max_rclen, self._max_tlen, self._max_rlen
        for rc, t, r, n in zip(
            self.rankcode_lineage,
            self.taxid_lineage,
            self.rank_lineage,
            self.name_lineage,
        ):
            current_str = f"{str(rc):<{rc_width}}\t{t:<{id_width}}\t{r:<{rank_width}}\t{n}"
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

    def _find_lineage(self, taxdb: TaxonomyDatabase) -> tuple[Node, ...]:
        lineage = [self.node]
        seen = {self.node.taxid}
        current_taxid = lineage[-1].taxid
        while lineage[-1].parent != current_taxid:
            current_taxid = lineage[-1].parent
            if current_taxid in seen:
                raise TaxDbError(
                    "Taxonomy lineage contains a cycle",
                    f"TaxID {current_taxid} was visited more than once while tracing {self.taxid}",
                )
            lineage.append(taxdb.get_node(current_taxid))
            seen.add(current_taxid)
        if lineage[-1].taxid != 1:
            raise TaxDbError(
                "Taxonomy lineage terminates outside the NCBI root",
                f"TaxID {lineage[-1].taxid} is its own parent while tracing {self.taxid}; expected root TaxID 1",
            )
        return tuple(lineage)
