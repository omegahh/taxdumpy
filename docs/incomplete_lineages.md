# Handling Incomplete Taxonomic Lineages

## The Problem

NCBI taxonomy database contains millions of species, but not all have complete, well-structured lineages following the canonical ranks. This creates challenges when trying to retrieve specific taxonomic levels like genus or family.

### Example Scenarios

**Well-structured lineage (Homo sapiens - TaxID 9606):**
```
species → genus → family → order → class → phylum → superkingdom
```

**Incomplete lineage (some viral or bacterial species):**
```
species → clade → clade → no rank → superkingdom
(missing: genus, family, order, class, phylum)
```

**Lineage with sub-ranks:**
```
species → subgenus → genus → subfamily → family → ...
```

**Lineage with non-canonical ranks:**
```
strain → species group → species subgroup → genus → ...
```

## Why This Happens

1. **Taxonomic uncertainty**: Not all organisms fit neatly into Linnaean classification
2. **Viral taxonomy**: Viruses often lack traditional taxonomic ranks
3. **Emerging species**: Newly discovered species may have incomplete classification
4. **Non-culturable organisms**: Environmental samples with limited information
5. **Reclassification**: Taxonomy is constantly being revised

## Solutions

### 1. Using the `upper_rank_id()` Function

The `upper_rank_id()` function in `functions.py` attempts to find the closest canonical rank:

```python
from taxdumpy import TaxDb, Taxon, upper_rank_id

taxdb = TaxDb("/path/to/taxdump", fast=True)
taxon = Taxon(9606, taxdb)  # Homo sapiens

# Get genus taxid
try:
    genus_id = upper_rank_id(taxon, taxdb, "genus")
    print(f"Genus taxid: {genus_id}")
except (TaxRankError, RuntimeError) as e:
    print(f"Cannot determine genus: {e}")
```

**How it works:**
1. First checks if the exact rank exists in lineage
2. Checks for sub-rank (e.g., "subgenus" for "genus")
3. If neither found, traverses up the tree to find the nearest canonical rank and jumps up

**Limitations:**
- Only works if the starting taxon has a canonical rank (species, genus, etc.)
- Raises `TaxRankError` if starting from non-canonical rank (clade, no rank, etc.)
- May fail for highly incomplete lineages

### 2. Direct Lineage Inspection (Recommended)

For maximum reliability, inspect the lineage directly:

```python
from taxdumpy import TaxDb, Taxon

taxdb = TaxDb("/path/to/taxdump", fast=True)
taxon = Taxon(9606, taxdb)

# Method 1: Check if rank exists
if "genus" in taxon.rank_lineage:
    genus_idx = taxon.rank_lineage.index("genus")
    genus_id = taxon.taxid_lineage[genus_idx]
    print(f"Genus taxid: {genus_id}")
else:
    print("No genus rank in lineage")

# Method 2: Check for sub-rank as fallback
if "genus" in taxon.rank_lineage:
    genus_id = taxon.taxid_lineage[taxon.rank_lineage.index("genus")]
elif "subgenus" in taxon.rank_lineage:
    genus_id = taxon.taxid_lineage[taxon.rank_lineage.index("subgenus")]
else:
    genus_id = None
```

### 3. Safe Wrapper Function (Best Practice)

Create a wrapper that combines multiple strategies:

```python
def get_genus_safely(taxon, taxdb):
    """Get genus taxid with multiple fallback strategies."""
    # Strategy 1: Direct lookup
    if "genus" in taxon.rank_lineage:
        return taxon.taxid_lineage[taxon.rank_lineage.index("genus")]

    # Strategy 2: Use subgenus
    if "subgenus" in taxon.rank_lineage:
        return taxon.taxid_lineage[taxon.rank_lineage.index("subgenus")]

    # Strategy 3: Try upper_rank_id
    try:
        from taxdumpy import upper_rank_id
        return upper_rank_id(taxon, taxdb, "genus")
    except Exception:
        pass

    # Strategy 4: Return None if all fail
    return None

# Usage
genus_id = get_genus_safely(taxon, taxdb)
if genus_id:
    genus_taxon = Taxon(genus_id, taxdb)
    print(f"Genus: {genus_taxon.name}")
else:
    print("Genus not available")
```

### 4. Batch Processing with Error Handling

When processing many species:

```python
from taxdumpy import TaxDb, Taxon

taxdb = TaxDb("/path/to/taxdump", fast=True)
species_taxids = [9606, 511145, 7227, 12345]  # mix of taxids

results = []
for taxid in species_taxids:
    try:
        taxon = Taxon(taxid, taxdb)

        # Get genus
        genus_id = None
        if "genus" in taxon.rank_lineage:
            genus_id = taxon.taxid_lineage[taxon.rank_lineage.index("genus")]

        # Get family
        family_id = None
        if "family" in taxon.rank_lineage:
            family_id = taxon.taxid_lineage[taxon.rank_lineage.index("family")]

        results.append({
            'taxid': taxid,
            'name': taxon.name,
            'genus_id': genus_id,
            'family_id': family_id,
            'has_complete_lineage': genus_id is not None and family_id is not None
        })

    except Exception as e:
        print(f"Error processing {taxid}: {e}")
        results.append({
            'taxid': taxid,
            'error': str(e)
        })

# Analyze results
complete = sum(1 for r in results if r.get('has_complete_lineage'))
incomplete = len(results) - complete
print(f"Complete lineages: {complete}/{len(results)}")
print(f"Incomplete lineages: {incomplete}/{len(results)}")
```

## Practical Recommendations

### For Bioinformatics Pipelines

1. **Always check if rank exists before accessing:**
   ```python
   genus_id = taxon.taxid_lineage[taxon.rank_lineage.index("genus")] if "genus" in taxon.rank_lineage else None
   ```

2. **Use fallback strategies:**
   - Primary: exact rank
   - Secondary: sub-rank
   - Tertiary: `upper_rank_id()`
   - Final: None or use parent taxon

3. **Track incomplete lineages:**
   - Log taxids with missing ranks for manual review
   - Report statistics on lineage completeness
   - Consider filtering or flagging incomplete entries

4. **Consider the biological context:**
   - Viral genomes often lack genus/family
   - Environmental sequences may have uncertain classification
   - Some groups (bacteria, archaea) use different taxonomic systems

### For Data Analysis

1. **Filter by completeness:**
   ```python
   # Only process species with complete lineages
   complete_species = [t for t in taxids
                       if "genus" in Taxon(t, taxdb).rank_lineage
                       and "family" in Taxon(t, taxdb).rank_lineage]
   ```

2. **Use higher taxonomic levels:**
   - If genus is missing, use family or order
   - If family is missing, use order or class
   - Superkingdom is almost always present

3. **Aggregate at available levels:**
   ```python
   # Group by highest available canonical rank
   for taxid in taxids:
       taxon = Taxon(taxid, taxdb)
       for rank in ["genus", "family", "order", "class", "phylum"]:
           if rank in taxon.rank_lineage:
               group_by_rank = taxon.taxid_lineage[taxon.rank_lineage.index(rank)]
               break
   ```

## Common Patterns

### Pattern 1: Get First Available Canonical Rank

```python
def get_first_available_rank(taxon, preferred_ranks=["genus", "family", "order"]):
    """Get the first available rank from a preference list."""
    for rank in preferred_ranks:
        if rank in taxon.rank_lineage:
            idx = taxon.rank_lineage.index(rank)
            return taxon.taxid_lineage[idx], rank
    return None, None

taxid, rank = get_first_available_rank(taxon)
if taxid:
    print(f"Using {rank}: {Taxon(taxid, taxdb).name}")
```

### Pattern 2: Build Rank Dictionary

```python
def get_all_canonical_ranks(taxon):
    """Get dictionary of all canonical ranks present in lineage."""
    canonical = ["species", "genus", "family", "order", "class", "phylum", "superkingdom"]
    ranks = {}
    for rank in canonical:
        if rank in taxon.rank_lineage:
            idx = taxon.rank_lineage.index(rank)
            ranks[rank] = taxon.taxid_lineage[idx]
    return ranks

ranks = get_all_canonical_ranks(taxon)
print(f"Available ranks: {list(ranks.keys())}")
```

### Pattern 3: Closest Ancestor at Target Level

```python
def get_closest_ancestor(taxon, taxdb, target_rank):
    """
    Get the closest ancestor at or above the target rank.
    Useful when exact rank doesn't exist.
    """
    canonical_order = ["species", "genus", "family", "order", "class", "phylum", "superkingdom"]

    if target_rank not in canonical_order:
        return None

    target_level = canonical_order.index(target_rank)

    # Find the closest rank at or above target
    for i in range(target_level, len(canonical_order)):
        rank = canonical_order[i]
        if rank in taxon.rank_lineage:
            idx = taxon.rank_lineage.index(rank)
            return taxon.taxid_lineage[idx]

    return None
```

## Testing Your Data

Use the example script to analyze your specific taxids:

```bash
python examples/get_family_genus.py
```

This will:
1. Show the complete lineage structure
2. Identify which canonical ranks are present
3. Test the retrieval functions
4. Help you understand your data's lineage completeness

## See Also

- `examples/get_family_genus.py` - Interactive example script
- `src/taxdumpy/functions.py` - Source code for `upper_rank_id()`
- `tests/test_functions.py` - Unit tests showing edge cases
