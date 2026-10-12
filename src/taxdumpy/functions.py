"""
Description: Functions for Taxdumpy
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-07-06 17:07:57
"""

from collections.abc import Mapping

from taxdumpy.basic import TaxDbError, TaxidError, TaxRankError, ValidationError
from taxdumpy.database import TaxonomyDatabase
from taxdumpy.ranks import LEVEL2RANK, RANK2LEVEL, RANK_ALIASES, RANKNAMES, RankName
from taxdumpy.taxon import Taxon


def upper_rank_id(
    tax: Taxon,
    rank: RankName,
) -> int:
    """Return a higher canonical rank (or its subrank), raising if absent.

    Use get_closest_rank when falling back to a different rank is appropriate.
    """
    curr_rank = tax.rank
    if curr_rank not in RANKNAMES:
        raise TaxRankError(
            curr_rank,
            f"TAXID={tax.taxid} ({curr_rank=}) is a non-canonical phylogenetic rank",
            RANKNAMES,
        )
    if rank not in RANKNAMES:
        raise TaxRankError(rank, f"{rank=} is a non-canonical phylogenetic rank", RANKNAMES)
    # and check rank levels
    curr_level = RANK2LEVEL[curr_rank]
    high_level = RANK2LEVEL[rank]
    if high_level <= curr_level:
        raise TaxRankError(rank, f"{rank=} is in lower/equal level than {curr_rank=} in phylogenetic tree")
    taxid = get_rank_taxid(tax, rank)
    if taxid is not None:
        return taxid
    raise TaxRankError(rank, f"Rank '{rank}' is absent from the lineage of TaxID {tax.taxid}")


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
    names = [rank]
    canonical_rank = RANK_ALIASES.get(rank, rank)
    if canonical_rank in RANK2LEVEL:
        names.extend(name for name in RANKNAMES if name != rank and RANK2LEVEL[name] == RANK2LEVEL[canonical_rank])
    for name in names:
        if name in taxon.rank_lineage:
            return taxon.taxid_lineage[taxon.rank_lineage.index(name)]

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

    target_level = RANK2LEVEL[target_rank]

    # Search from target level upwards
    for i in range(target_level, len(LEVEL2RANK)):
        rank = LEVEL2RANK[i]
        taxid = get_rank_taxid(taxon, rank, include_subrank=include_subranks)
        if taxid is not None:
            # Get actual rank name from lineage
            return taxid, taxon.rank_lineage[taxon.taxid_lineage.index(taxid)]

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

    if max_distance is not None and (
        isinstance(max_distance, bool) or not isinstance(max_distance, int) or max_distance < 0
    ):
        raise ValidationError("max_distance", max_distance, "non-negative integer or None")

    target_level = RANK2LEVEL[rank]

    # Determine search range
    end_level = len(LEVEL2RANK)
    if max_distance is not None:
        end_level = min(target_level + max_distance + 1, len(LEVEL2RANK))

    # Search from target level upwards
    for i in range(target_level, end_level):
        search_rank = LEVEL2RANK[i]
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

    level1 = RANK2LEVEL[rank1]
    level2 = RANK2LEVEL[rank2]

    return abs(level1 - level2)


def group_taxids_by_rank(
    taxids: list[int],
    rank: str,
    taxdb: TaxonomyDatabase,
) -> dict[int, list[int]]:
    """
    Group taxids by a target rank, using closest ancestor if exact rank is missing.

    For each taxid, finds the taxid at the target rank level. If the exact rank
    is missing, falls back to the closest canonical ancestor. Subranks and
    unranked clades are excluded; the root is used only when requested explicitly.

    Args:
        taxids: List of taxids to group
        rank: Target rank name ('species', 'genus', 'family', 'order', 'class',
              'phylum', 'superkingdom')
        taxdb: Any taxonomy database backend

    Returns:
        Dictionary mapping group taxid -> list of input taxids belonging to that group

    Example:
        >>> taxdb = TaxDb("/path/to/taxdump")
        >>> species_taxids = [9606, 9598, 9597]
        >>> by_family = group_taxids_by_rank(species_taxids, 'family', taxdb)
        >>> # {9604: [9606, 9598, 9597]}  # All in Hominidae
    """
    valid_ranks = [*RANKNAMES, "root"]
    if rank not in valid_ranks:
        raise TaxRankError(rank, f"'{rank}' is not a valid rank for grouping", valid_ranks)

    groups: dict[int, list[int]] = {}

    for taxid in taxids:
        try:
            taxon = Taxon(taxid, taxdb)
        except (TaxidError, ValidationError):
            continue

        if rank == "root":
            groups.setdefault(taxon.taxid_lineage[-1], []).append(taxid)
            continue
        group_taxid, _ = get_closest_rank(taxon, rank, include_subranks=False)

        if group_taxid is not None:
            if group_taxid not in groups:
                groups[group_taxid] = []
            groups[group_taxid].append(taxid)

    return groups


def build_children_index(taxdb: TaxonomyDatabase) -> Mapping[int, tuple[int, ...]]:
    """Return a cached read-only parent/children index, released by close().

    This explicit operation scans all nodes. SQLite descendants instead use
    indexed child queries, avoiding a global index for small subtrees.
    """
    return taxdb.children_index


def descendants(taxdb: TaxonomyDatabase, taxid: int | str, max_depth: int | None = None) -> list[int]:
    """Get all taxids in the subtree below a taxid.

    Walks *down* the taxonomy tree: the inverse of lineage tracing. The result
    is every node that has `taxid` somewhere among its ancestors.

    Dictionary backends reuse a parent/children index. SQLite queries children
    by indexed, batched frontiers. Traversal is iterative, so deep trees cannot
    exhaust the stack.

    Deleted and superseded (merged) taxids are excluded from results. A merged
    `taxid` argument resolves to its current taxid first, matching `get_node`.

    Args:
        taxdb: Any taxonomy database backend
        taxid: NCBI taxonomy ID (integer or string)
        max_depth: Levels to descend. 1 returns direct children only, 2 also
            their children, and so on. None (default) returns the whole subtree.

    Returns:
        List of descendant taxids, excluding `taxid` itself. Empty for a leaf.
        Ordered breadth-first, so shallower nodes come first.

    Raises:
        ValidationError: If taxid or max_depth is invalid
        TaxidError: If taxid is not found or has been deleted

    Example:
        >>> descendants(taxdb, 561)  # genus Escherichia
        [562, 208962, ...]
        >>> descendants(taxdb, 561, max_depth=1)  # direct children only
        [562, 208962]
    """
    if max_depth is not None:
        if isinstance(max_depth, bool) or not isinstance(max_depth, int):
            raise ValidationError("max_depth", type(max_depth).__name__, "integer or None")
        if max_depth < 1:
            raise ValidationError("max_depth", max_depth, "integer >= 1, or None")

    # Resolves merged taxids and raises TaxidError for unknown/deleted ones.
    root = taxdb.get_node(taxid).taxid

    frontier = taxdb.children_for([root])
    if not frontier:
        return []

    result: list[int] = []
    visited = {root}
    depth = 1
    while frontier:
        for node_taxid in frontier:
            if node_taxid in visited:
                raise TaxDbError(
                    "Taxonomy tree contains a cycle",
                    f"TaxID {node_taxid} was reached more than once below {root}",
                )
            visited.add(node_taxid)
            result.append(node_taxid)
        if max_depth is not None and depth >= max_depth:
            break
        frontier = taxdb.children_for(frontier)
        depth += 1

    return result


def descendant_nodes(taxdb: TaxonomyDatabase, taxid: int | str, max_depth: int | None = None) -> list:
    """Get `Node` objects for the subtree below a taxid.

    Convenience wrapper over `descendants` for callers that need rank, name or
    division. Costs one `get_node` per descendant, so prefer `descendants` when
    taxids alone will do.

    Args:
        taxdb: Any taxonomy database backend
        taxid: NCBI taxonomy ID (integer or string)
        max_depth: See `descendants`

    Returns:
        List of Node objects, excluding the node for `taxid` itself.
    """
    return [taxdb.get_node(t) for t in descendants(taxdb, taxid, max_depth)]
