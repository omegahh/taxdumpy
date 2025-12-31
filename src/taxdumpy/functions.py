"""
Description: Functions for Taxdumpy
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-07-06 17:07:57
"""

from typing import Literal

from taxdumpy.basic import TaxRankError
from taxdumpy.taxdb import TaxDb
from taxdumpy.taxon import Taxon

# from taxdumpy.taxsqlite import TaxSQLite

RANKNAMES = [
    "species",
    "genus",
    "family",
    "order",
    "class",
    "phylum",
    "superkingdom",
    "realm",
]
RANK2LEVEL = {k: i for i, k in enumerate(RANKNAMES)}
LEVEL2RANK = {i: k for i, k in enumerate(RANKNAMES)}

# Extended rank names including sub-ranks and common non-canonical ranks
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
    "superkingdom",
    "realm",
]


def upper_rank_id(
    tax: Taxon,
    taxdb: TaxDb,
    rank: Literal[
        "species",
        "genus",
        "family",
        "order",
        "class",
        "phylum",
        "superkingdom",
        "realm",
    ],
) -> int:
    curr_rank = tax.rank
    if curr_rank not in RANKNAMES:
        raise TaxRankError(
            curr_rank,
            f"TAXID={tax.taxid} ({curr_rank=}) is a non-canonical phylogenetic rank",
            RANKNAMES,
        )
    if rank not in RANKNAMES:
        raise TaxRankError(
            rank, f"{rank=} is a non-canonical phylogenetic rank", RANKNAMES
        )
    # and check rank levels
    curr_level = RANK2LEVEL[curr_rank]
    high_level = RANK2LEVEL[rank]
    if high_level <= curr_level:
        raise RuntimeError(
            f"{rank=} is in lower/equal level than {curr_rank=} in phylogenetic tree"
        )
    # Get upper rank iteratively
    if rank in tax.rank_lineage:
        return tax.taxid_lineage[tax.rank_lineage.index(rank)]
    elif f"sub{rank}" in tax.rank_lineage:
        return tax.taxid_lineage[tax.rank_lineage.index(f"sub{rank}")]
    else:
        # neither rank nor sub-rank in the lineage
        temp_level = high_level
        temp_rank = LEVEL2RANK[temp_level]
        while temp_level > curr_level:
            temp_level -= 1
            temp_rank = LEVEL2RANK[temp_level]
            if temp_rank in tax.rank_lineage:
                break
        jump_taxid = tax.taxid_lineage[tax.rank_lineage.index(temp_rank)]
        for _ in range(high_level - temp_level):
            jump_taxid = Taxon(jump_taxid, taxdb).parent
        return jump_taxid


def get_rank_taxid(
    taxon: Taxon,
    rank: str,
    include_subrank: bool = True,
) -> int | None:
    """
    Safely get taxid for a specific rank from taxon's lineage.

    This is a simple, safe alternative to upper_rank_id that:
    - Returns None instead of raising exceptions
    - Works with any starting rank (canonical or not)
    - Optionally includes sub-ranks (e.g., subfamily for family)

    Args:
        taxon: Taxon object to query
        rank: Target rank name (e.g., 'genus', 'family')
        include_subrank: If True, will return subrank if exact rank not found

    Returns:
        taxid (int) if rank found, None otherwise

    Example:
        >>> taxon = Taxon(9606, taxdb)  # Homo sapiens
        >>> genus_id = get_rank_taxid(taxon, 'genus')
        >>> family_id = get_rank_taxid(taxon, 'family', include_subrank=True)
    """
    # Direct lookup
    if rank in taxon.rank_lineage:
        idx = taxon.rank_lineage.index(rank)
        return taxon.taxid_lineage[idx]

    # Try sub-rank if requested
    if include_subrank:
        subrank = f"sub{rank}"
        if subrank in taxon.rank_lineage:
            idx = taxon.rank_lineage.index(subrank)
            return taxon.taxid_lineage[idx]

    return None


def get_canonical_ranks(
    taxon: Taxon,
    include_subranks: bool = True,
) -> dict[str, int]:
    """
    Get all canonical ranks present in taxon's lineage.

    Args:
        taxon: Taxon object to query
        include_subranks: If True, includes sub-ranks (subfamily, subgenus, etc.)

    Returns:
        Dictionary mapping rank names to taxids

    Example:
        >>> taxon = Taxon(9606, taxdb)  # Homo sapiens
        >>> ranks = get_canonical_ranks(taxon)
        >>> print(ranks)
        {'species': 9606, 'genus': 9605, 'family': 9604, ...}
    """
    result = {}

    for rank in RANKNAMES:
        taxid = get_rank_taxid(taxon, rank, include_subrank=include_subranks)
        if taxid is not None:
            result[rank] = taxid

    return result


def get_closest_rank(
    taxon: Taxon,
    target_rank: str,
    include_subranks: bool = True,
) -> tuple[int, str] | tuple[None, None]:
    """
    Get the closest rank at or above the target rank level.

    Useful when exact rank doesn't exist in lineage - will return
    the next available higher rank.

    Args:
        taxon: Taxon object to query
        target_rank: Target rank name (e.g., 'genus', 'family')
        include_subranks: If True, considers sub-ranks as valid matches

    Returns:
        Tuple of (taxid, rank_name) if found, (None, None) otherwise

    Example:
        >>> taxon = Taxon(12345, taxdb)  # some virus without genus
        >>> taxid, rank = get_closest_rank(taxon, 'genus')
        >>> # Might return family or order if genus doesn't exist
    """
    if target_rank not in RANKNAMES:
        return None, None

    target_level = RANKNAMES.index(target_rank)

    # Search from target level upwards
    for i in range(target_level, len(RANKNAMES)):
        rank = RANKNAMES[i]
        taxid = get_rank_taxid(taxon, rank, include_subrank=include_subranks)
        if taxid is not None:
            # Get actual rank name from lineage
            if rank in taxon.rank_lineage:
                return taxid, rank
            elif include_subranks and f"sub{rank}" in taxon.rank_lineage:
                return taxid, f"sub{rank}"

    return None, None


def get_rank_or_closest(
    taxon: Taxon,
    rank: str,
    max_distance: int | None = None,
) -> int | None:
    """
    Get taxid for specified rank, or closest available ancestor rank.

    This combines exact matching with fallback to nearest higher rank,
    with optional limit on how far up the tree to search.

    Args:
        taxon: Taxon object to query
        rank: Target rank name (e.g., 'genus', 'family')
        max_distance: Maximum number of rank levels to search upward (None = unlimited)

    Returns:
        taxid (int) if found within max_distance, None otherwise

    Example:
        >>> taxon = Taxon(12345, taxdb)
        >>> # Get genus, or family if genus missing, but not higher
        >>> taxid = get_rank_or_closest(taxon, 'genus', max_distance=2)
    """
    if rank not in RANKNAMES:
        return None

    target_level = RANKNAMES.index(rank)

    # Determine search range
    end_level = len(RANKNAMES)
    if max_distance is not None:
        end_level = min(target_level + max_distance + 1, len(RANKNAMES))

    # Search from target level upwards
    for i in range(target_level, end_level):
        search_rank = RANKNAMES[i]
        taxid = get_rank_taxid(taxon, search_rank, include_subrank=True)
        if taxid is not None:
            return taxid

    return None


def get_all_ranks(
    taxon: Taxon,
) -> dict[str, int]:
    """
    Get all ranks (canonical and non-canonical) from taxon's lineage.

    Unlike get_canonical_ranks(), this returns ALL ranks present in the
    lineage, including non-canonical ranks like 'clade', 'no rank', etc.

    Args:
        taxon: Taxon object to query

    Returns:
        Dictionary mapping all rank names to taxids

    Example:
        >>> taxon = Taxon(9606, taxdb)
        >>> ranks = get_all_ranks(taxon)
        >>> print(ranks)
        {'species': 9606, 'genus': 9605, 'clade': 1234, 'no rank': 5678, ...}
    """
    result = {}

    for taxid, rank in zip(taxon.taxid_lineage, taxon.rank_lineage):
        # Keep first occurrence of each rank (closest to query)
        if rank not in result:
            result[rank] = taxid

    return result


def find_rank_in_lineage(
    taxon: Taxon,
    rank_list: list[str],
) -> tuple[int, str] | tuple[None, None]:
    """
    Find the first occurrence of any rank from a preference list.

    Useful for finding the "best available" rank when you have
    multiple acceptable options.

    Args:
        taxon: Taxon object to query
        rank_list: List of rank names in preference order

    Returns:
        Tuple of (taxid, rank_name) for first match, (None, None) if none found

    Example:
        >>> taxon = Taxon(12345, taxdb)
        >>> # Get genus if available, otherwise family, otherwise order
        >>> taxid, rank = find_rank_in_lineage(taxon, ['genus', 'family', 'order'])
    """
    for rank in rank_list:
        if rank in taxon.rank_lineage:
            idx = taxon.rank_lineage.index(rank)
            return taxon.taxid_lineage[idx], rank

    return None, None


def get_rank_distance(
    rank1: str,
    rank2: str,
) -> int | None:
    """
    Calculate the distance between two canonical ranks.

    Args:
        rank1: First rank name
        rank2: Second rank name

    Returns:
        Absolute distance between ranks (0 = same rank), None if either rank is non-canonical

    Example:
        >>> distance = get_rank_distance('species', 'family')
        >>> print(distance)  # 2 (species -> genus -> family)
    """
    if rank1 not in RANKNAMES or rank2 not in RANKNAMES:
        return None

    level1 = RANKNAMES.index(rank1)
    level2 = RANKNAMES.index(rank2)

    return abs(level1 - level2)
