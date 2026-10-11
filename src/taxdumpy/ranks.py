"""Shared rank names, levels and display codes."""

from typing import Literal, get_args

RankName = Literal[
    "species",
    "genus",
    "family",
    "order",
    "class",
    "phylum",
    "kingdom",
    "domain",
    "superkingdom",
    "realm",
]
RANKNAMES: list[str] = list(get_args(RankName))
RANK_ALIASES = {"domain": "superkingdom"}
_PRIMARY_RANKS = [rank for rank in RANKNAMES if rank not in RANK_ALIASES]
RANK2LEVEL = {rank: level for level, rank in enumerate(_PRIMARY_RANKS)}
RANK2LEVEL.update({alias: RANK2LEVEL[rank] for alias, rank in RANK_ALIASES.items()})
LEVEL2RANK = dict(enumerate(_PRIMARY_RANKS))

# Realm shares the root-level R code to preserve the public RC integer encoding.
# MPA names distinguish realm (r__) from root, which has no MPA entry.
RANKCODE_ORDER = ("R", "D", "K", "P", "C", "O", "F", "G", "S")
RANK_CODES = dict(zip(reversed(_PRIMARY_RANKS), RANKCODE_ORDER))
RANK_CODES.update({alias: RANK_CODES[rank] for alias, rank in RANK_ALIASES.items()})
MPA_CODES = {rank: code.lower() for rank, code in RANK_CODES.items()}

EXTENDED_RANKS = [
    "forma",
    "varietas",
    "subspecies",
    "species",
    "species subgroup",
    "species group",
    "subgenus",
    "genus",
    "subtribe",
    "tribe",
    "subfamily",
    "family",
    "superfamily",
    "parvorder",
    "infraorder",
    "suborder",
    "order",
    "superorder",
    "subcohort",
    "cohort",
    "infraclass",
    "subclass",
    "class",
    "superclass",
    "subphylum",
    "phylum",
    "superphylum",
    "subkingdom",
    "kingdom",
    "domain",
    "superkingdom",
    "realm",
]
