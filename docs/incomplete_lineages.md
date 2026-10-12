# Handling Incomplete Taxonomic Lineages

NCBI lineages may omit canonical ranks or contain clades, strains, and subranks.
Choose whether a missing rank should produce `None`, accept a subrank, or fall
back to a higher rank. Build caches first with `taxdumpy cache -d PATH`, then
reuse one reader for batch operations.

## Exact Rank and Subrank Lookup

`get_rank_taxid` works from any starting rank and returns `None` when absent.
It prefers the exact rank; by default it accepts a subrank only when the exact
rank is missing. `domain` and `superkingdom` are aliases of the same level.

```python
from taxdumpy import TaxDb, Taxon, get_rank_taxid

with TaxDb("/path/to/taxdump") as db:
    human = Taxon(9606, db)
    assert get_rank_taxid(human, "genus") == 9605
    family_id = get_rank_taxid(human, "family", include_subrank=False)
    missing = get_rank_taxid(human, "absent rank")  # None
```

`upper_rank_id(taxon, rank)` is strict. It requires a canonical starting rank
and a strictly higher canonical target. It accepts the target's subrank when
necessary but raises `TaxRankError` if neither is present. Asking for an equal
or lower rank also raises `TaxRankError`; it does not fall back to another rank.

```python
from taxdumpy import TaxDb, Taxon, TaxRankError, upper_rank_id

with TaxDb("/path/to/taxdump") as db:
    human = Taxon(9606, db)
    try:
        upper_rank_id(human, "absent rank")
    except TaxRankError as error:
        print(error)
```

## Closest Available Rank

`get_closest_rank` starts at the target level and searches higher canonical
levels. It returns `(taxid, actual_rank)` or `(None, None)`. Keep the actual rank
in results so an order is not labelled as a family. Set `include_subranks=False`
when only canonical ranks are acceptable.

```python
from taxdumpy import TaxDb, Taxon, get_closest_rank, get_rank_or_closest

with TaxDb("/path/to/taxdump") as db:
    human = Taxon(9606, db)
    taxid, actual_rank = get_closest_rank(human, "family", include_subranks=False)
    assert (taxid, actual_rank) == (9604, "family")
    genus_or_family = get_rank_or_closest(human, "genus", max_distance=1)
```

`get_rank_or_closest` returns only the taxid and can bound the upward search by
canonical levels. With `max_distance=1`, genus may fall back to family but not
order. It accepts subranks. Unranked clades never establish a canonical rank
merely because their computed `RC` inherits an ancestor's code.

## Inventory and Preference Lists

Canonical levels are species, genus, family, order, class, phylum, kingdom,
superkingdom/domain, and realm. `get_canonical_ranks` handles this list and its
aliases; `get_all_ranks` includes every rank, retaining the nearest occurrence
when ranks repeat. Root is distinct from realm and is omitted from MPA output.

```python
from taxdumpy import TaxDb, Taxon, get_canonical_ranks, find_rank_in_lineage

with TaxDb("/path/to/taxdump") as db:
    human = Taxon(9606, db)
    canonical = get_canonical_ranks(human, include_subranks=False)
    chosen_id, chosen_rank = find_rank_in_lineage(human, ["genus", "family", "order"])
    assert (chosen_id, chosen_rank) == (9605, "genus")
```

`find_rank_in_lineage` follows the supplied preference order and matches exact
rank names. It returns `(None, None)` if none are present.

## Batch Processing

Use a single `TaxDb` for in-memory batches or `TaxSQLite` for indexed lookups.
Catch expected invalid/deleted taxids explicitly, allowing database errors to
stop processing instead of silently discarding a corrupted lineage.

```python
from taxdumpy import TaxDb, Taxon, TaxidError, get_rank_taxid

results = []
with TaxDb("/path/to/taxdump") as db:
    for taxid in [9606, 511145, 7227, 999999999]:
        try:
            taxon = Taxon(taxid, db)
        except TaxidError as error:
            results.append({"taxid": taxid, "error": str(error)})
            continue
        results.append({
            "taxid": taxid,
            "name": taxon.name,
            "genus_id": get_rank_taxid(taxon, "genus", include_subrank=False),
            "family_id": get_rank_taxid(taxon, "family", include_subrank=False),
        })
```

`group_taxids_by_rank(taxids, rank, db)` groups by the exact canonical rank or
the closest higher canonical ancestor, excluding subranks and clades. It skips
invalid, unknown, or deleted input IDs and propagates database errors. Request
`root` explicitly to group all valid taxa under taxid 1.

See the [README](../README.md) for cache and backend guidance and
[rank tests](../tests/test_functions.py) for missing-rank and alias cases.
