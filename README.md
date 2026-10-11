# Taxdumpy

_A high-performance Python toolkit for parsing NCBI Taxonomy databases with lineage resolution and fuzzy search_

[![CI](https://github.com/omegahh/taxdumpy/workflows/CI/badge.svg)](https://github.com/omegahh/taxdumpy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxdumpy?color=green)](https://pypi.org/project/taxdumpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Development Status](https://img.shields.io/badge/Development%20Status-5%20Production/Stable-brightgreen)](https://pypi.org/project/taxdumpy/)
[![codecov](https://codecov.io/gh/omegahh/taxdumpy/branch/main/graph/badge.svg)](https://codecov.io/gh/omegahh/taxdumpy)

## Features

- **Cached Loading**: Parse NCBI taxdump files once, then reuse pickle or SQLite caches
- **Dual Backends**: In-memory (`TaxDb`) for speed or SQLite (`TaxSQLite`) for memory efficiency
- **Lineage Resolution**: Complete lineage tracing with automatic handling of merged/deleted nodes
- **Subtree Traversal**: Walk *down* the tree with `descendants` — every taxid below a given one
- **Rank Codes**: Comparable `RC` class for efficient rank-based operations and grouping
- **Fuzzy Search**: Rapid approximate name matching using `rapidfuzz`
- **Batch Grouping**: Group taxids by rank level with `group_taxids_by_rank`
- **CLI**: Ready-to-use commands for caching, searching, and lineage resolution

## Installation

```bash
pip install taxdumpy
```

**Development Installation:**

```bash
git clone https://github.com/omegahh/taxdumpy.git
cd taxdumpy
pip install -e .
```

**With Development Dependencies:**

```bash
pip install -e '.[dev]'
```

## Quick Start

Build the taxonomy caches from the NCBI taxdump files with the CLI before
opening a database from Python or running query commands:

```bash
taxdumpy cache -d /path/to/taxdump
```

### Basic Usage

```python
from taxdumpy import TaxDb, Taxon

# Open the cache built by `taxdumpy cache`; API constructors never build caches.
taxdb = TaxDb("/path/to/taxdump")

# Create taxon objects
human = Taxon(9606, taxdb)  # Homo sapiens
ecoli = Taxon(511145, taxdb)  # E. coli K-12

# Access lineage information
print(human.name_lineage)
# ['Homo sapiens', 'Homo', 'Hominidae', 'Primates', ..., 'cellular organisms']

print(human.rank_lineage)
# ['species', 'genus', 'family', 'order', ..., 'superkingdom']

# Check taxonomic properties
print(f"Rank: {human.rank}")           # species
print(f"Division: {human.division}")   # PRI (division code, not full name)
print(f"Is legacy: {human.is_legacy}") # False
```

### Choosing a Backend for Batch Queries

Use `TaxSQLite` for memory-efficient queries or `TaxDb` for in-memory queries.
Open the cache once and reuse the same instance throughout the batch:

```python
from taxdumpy import TaxSQLite, Taxon

# Build the cache first with: taxdumpy cache -d /path/to/taxdump
with TaxSQLite("/path/to/taxdump") as db:
    for taxid in [9606, 511145, 7227]:
        taxon = Taxon(taxid, db)
        print(taxon.name)
```

### Scientific and Alternative Names

Both backends preserve all name classes from `names.dmp`, including synonyms,
common names, GenBank common names, equivalent names, acronyms, authorities,
and type material. Names stay grouped by their original NCBI class, with each
class holding a sorted tuple of distinct names.

```python
from taxdumpy import Taxon, open_database

with open_database("/path/to/taxdump") as db:
    human = Taxon(9606, db)
    print(human.name)                  # Homo sapiens (scientific name)
    print(human.genbank_common_names)  # ('human',)
    print(human.synonyms)              # Tuple of synonyms, or () if absent
    print(human.common_names)
    print(human.equivalent_names)
    print(human.acronyms)
    print(human.names.get("authority", ()))

    # Query names directly without constructing a Taxon or tracing its lineage.
    names = db.get_names(9606)  # dict[str, tuple[str, ...]]
```

Merged taxids use the current taxid's names. `get_names()` omits absent classes;
the convenience properties return `()` for them. `Taxon.names` loads once on
first access, so read it while the database is open. The existing singular
`acronym` property returns a pipe-separated string or `None`; `acronyms` keeps
each name as a separate value, including names containing a literal pipe.

Rebuild caches made by earlier versions with `taxdumpy cache -d PATH` to include
the additional names. For a filtered cache, run `taxdumpy cache -d PATH -f FILE`
again. Older cache formats are rejected with a rebuild instruction. Scientific
names remain the candidates used by `search()`, `all_names`, and `name2taxid`.

### Subtree Traversal

```python
from taxdumpy import TaxDb, descendants

taxdb = TaxDb("/path/to/taxdump")

# Every taxid below genus Escherichia (transitively, not just children)
descendants(taxdb, 561)
# [562, 208962, 511145, ...]

# Direct children only
descendants(taxdb, 561, max_depth=1)

# Deleted and merged taxids are excluded; the queried taxid itself is not
# included. Combine with existing helpers to filter:
species = [t for t in descendants(taxdb, 2) if taxdb.get_node(t).rank == "species"]
```

The first call builds a parent-to-children index in one pass over the database
and caches it, so later queries cost time proportional to the subtree returned
rather than to the database size.

### Fuzzy Search

```python
# Print formatted, highlighted matches to the console
taxdb.fuzzy_search("Escherichia coli", limit=5)

# Or get the matches as data
results = taxdb.search("Escherichia coli", limit=5)
for match in results:
    print(f"{match['name']} (TaxID: {match['taxid']}, Score: {match['score']})")
```

`search` returns dictionaries containing `name`, `taxid`, and a `score` from
0 to 100. It preserves separate taxa sharing a name and reuses its candidate
index across queries. `fuzzy_search` prints the results. Both methods propagate
validation and database errors to callers.

### Rank Codes and Grouping

```python
from taxdumpy import TaxDb, Taxon, RC, group_taxids_by_rank

taxdb = TaxDb("/path/to/taxdump")
human = Taxon(9606, taxdb)

# RC (Rank Code) - comparable rank representation
print(human.rc)              # RC('S') for species
print(human.rankcode_lineage)  # [RC('S'), RC('G'), RC('F1'), RC('F'), ...]

# RC comparison (lower value = higher rank)
RC("R") < RC("D") < RC("G") < RC("S")  # True
RC("F") < RC("F1")  # True (F1 is below F)

# Group taxids by rank
taxids = [9606, 9598, 9597]  # Human, Chimp, Bonobo
by_family = group_taxids_by_rank(taxids, "family", taxdb)
# {9604: [9606, 9598, 9597]}  # All in Hominidae

by_genus = group_taxids_by_rank(taxids, "genus", taxdb)
# {9605: [9606], 9598: [9598], 9597: [9597]}  # Different genera

# MPA-style lineage representation
print(human.mpa_repr)
# 'd__Eukaryota|k__Metazoa|p__Chordata|...|g__Homo|s__Homo_sapiens'
```

## Command Line Interface

By default, `search` and `lineage` use SQLite so individual queries do not load
the full pickle into memory. `--fast` loads a smaller, filtered pickle instead;
create that cache first with `cache -f FILE`.

### Check Version

```bash
taxdumpy --version
```

### Cache Database

```bash
# Rebuild both taxdump.sqlite and taxdump.pickle from source files
taxdumpy cache -d /path/to/taxdump

# Build taxdump_fast.pickle from selected taxids (one per line), their
# ancestors, and their descendants; blank lines and # comments are allowed.
# This command is also the only supported cache-building path.
taxdumpy cache -d /path/to/taxdump -f important_taxids.txt
```

The filtered command rebuilds the filtered pickle cache and does not rebuild
SQLite. Queries outside the subset require the full database.

### Search Operations

```bash
# Search for organisms (with fuzzy matching)
taxdumpy search --fast "Escherichia coli"
taxdumpy search "Homo sapiens"

# Limit search results
taxdumpy search --limit 5 "Influenza A"

# Search with custom database path
taxdumpy search -d /custom/path "Influenza A"
```

### Lineage Tracing

```bash
# Get complete lineage for TaxID
taxdumpy lineage --fast 511145  # E. coli K-12 MG1655
taxdumpy lineage 9606           # Homo sapiens

# With custom database path
taxdumpy lineage -d /custom/path 9606
```

## Database Setup

### 1. Download NCBI Taxonomy Data

```bash
# Create directory for taxonomy data
mkdir -p ~/.taxonkit

# Download latest taxdump
wget ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz -P ~/.taxonkit

# Extract files
tar -xzf ~/.taxonkit/taxdump.tar.gz -C ~/.taxonkit
```

### 2. Build the Caches

```bash
# Create the SQLite and full pickle caches (required before API use)
taxdumpy cache -d ~/.taxonkit

# Or create a filtered pickle cache with specific organisms
echo -e "9606\n511145\n7227" > important_species.txt
taxdumpy cache -d ~/.taxonkit -f important_species.txt
```

### 3. Set Environment Variable (Optional)

```bash
export TAXDB_PATH=~/.taxonkit
```

## Advanced Usage

### SQLite Backend

```python
from taxdumpy import TaxSQLite, Taxon

# Use the SQLite cache for memory-efficient batch processing.
# The cache must already exist from `taxdumpy cache`.
db = TaxSQLite("/path/to/taxdump")

# Same API as TaxDb
taxon = Taxon(9606, db)
print(taxon.name_lineage)

# Use as context manager
with TaxSQLite("/path/to/taxdump") as db:
    taxon = Taxon(9606, db)
    print(taxon.name)
```

### Batch Processing

Load the full pickle once and reuse the same instance for all Python queries.
Its startup cost is paid once per instance, rather than once per taxid.

```python
from taxdumpy import TaxDb, Taxon

# Load all taxa for arbitrary batch queries
taxdb = TaxDb("/path/to/taxdump")

taxids = [9606, 511145, 7227, 4932]  # Human, E.coli, Fly, Yeast
for taxid in taxids:
    taxon = Taxon(taxid, taxdb)
    print(f"{taxon.name}: {' > '.join(taxon.name_lineage[:3])}")
```

For a known subset, build a filtered cache with the CLI, then load that smaller
cache in subsequent processes:

```bash
printf '9606\n511145\n7227\n4932\n' > important_taxids.txt
taxdumpy cache -d /path/to/taxdump -f important_taxids.txt
```

```python
subset = TaxDb("/path/to/taxdump", fast=True)
human = Taxon(9606, subset)
```

### Cache Freshness and Rebuilding

New caches record source file sizes and modification times. Opening a stale
full pickle or SQLite cache reports an error instead of rebuilding it. Missing, stale,
or unreadable filtered caches raise an error; recreate them with
`taxdumpy cache -f FILE` so the selection is explicit.

Original three-part pickles remain readable, and legacy caches use source
modification times to detect changes. Valid caches remain usable after the
source `.dmp` files are removed. Rebuilding requires the source files again.

To rebuild caches, run the CLI again:

```bash
taxdumpy cache -d /path/to/taxdump
```

Each cache is replaced atomically only after its new contents are written
successfully. A failed rebuild preserves the previous file. Database API
constructors only read existing caches and report the CLI command when a cache
is missing, stale, or unreadable.

### Handling Merged/Legacy TaxIDs

```python
from taxdumpy import TaxDb, Taxon

taxdb = TaxDb("/path/to/taxdump")

# Merged taxids are automatically resolved
taxon = Taxon(old_taxid, taxdb)
print(taxon.is_legacy)  # True if taxid was merged
print(taxon.taxid)      # Original taxid
print(taxon.node.taxid) # Current/resolved taxid
```

### Exception Handling

```python
from taxdumpy import TaxDb, Taxon, TaxidError, TaxRankError, upper_rank_id

taxdb = TaxDb("/path/to/taxdump")

try:
    taxon = Taxon(999999999, taxdb)
except TaxidError as e:
    print(f"Invalid taxid: {e}")
    # Includes suggestions for similar taxids

try:
    # Signature is (tax, taxdb, rank) — a Taxon, not a bare taxid
    rank_id = upper_rank_id(Taxon(9606, taxdb), taxdb, "invalid_rank")
except TaxRankError as e:
    print(f"Invalid rank: {e}")
    # Includes list of valid ranks
```

## API Reference

### Core Classes

**TaxDb**: In-memory dictionary-based database loaded from a pickle cache

```python
TaxDb(taxdump_dir: Path | str, fast: bool = False, verbose: bool = False)
```

**TaxSQLite**: SQLite-backed database loaded from an existing cache

```python
TaxSQLite(taxdump_dir: Path | str, verbose: bool = False)
```

**Taxon**: Taxonomic unit with lineage resolution

```python
Taxon(taxid: int | str, taxdb: TaxDb | TaxSQLite)

# Properties
.name: str                # Scientific name
.rank: str                # Taxonomic rank
.division: str            # NCBI division
.parent: int              # Parent taxid
.acronym: str | None      # Acronym, if any
.names: dict[str, tuple[str, ...]]  # All names grouped by NCBI name class (lazy)
.synonyms: tuple[str, ...]
.common_names: tuple[str, ...]
.genbank_common_names: tuple[str, ...]
.equivalent_names: tuple[str, ...]
.acronyms: tuple[str, ...]
.node: Node               # Underlying node (resolved, if merged)
.rc: RC                   # Rank code for this taxon
.lineage: list[Node]      # Complete lineage as Node objects
.name_lineage: list[str]  # Names from taxid to root
.rank_lineage: list[str]  # Ranks from taxid to root
.taxid_lineage: list[int] # Taxids from taxid to root
.rankcode_lineage: list[RC]  # Rank codes from taxid to root
.mpa_repr: str            # MetaPhlAn-style lineage string
.is_legacy: bool          # True if taxid was merged
.has_species_level: bool  # True if lineage contains species rank
.species_taxid: int | None # Taxid at species level, or None if absent (previously 0)
```

**Opening a Backend for Batch Programs**

`open_database()` selects a reader backend and opens its existing cache.
Build that cache first with `taxdumpy cache`.

```python
from taxdumpy import Taxon, open_database

# Run `taxdumpy cache -d PATH` before this call.
# backend: "sqlite", "sql", "dict", "memory", or "pickle"
with open_database("/path/to/taxdump", backend="sqlite") as db:
    for taxid in [9606, 511145, 7227]:
        print(Taxon(taxid, db).name)
```

### Rank Functions

```python
from taxdumpy import (
    upper_rank_id,       # Get taxid at rank (raises TaxRankError if not found)
    get_rank_taxid,      # Get taxid at rank (returns None if not found)
    get_canonical_ranks, # Get dict of all canonical ranks in lineage
    get_closest_rank,    # Get closest rank at or above target level
    get_rank_or_closest, # Same, returning the taxid alone
    get_all_ranks,       # Every rank in the lineage as a dict
    find_rank_in_lineage,# First of several candidate ranks present
    get_rank_distance,   # Calculate distance between two ranks
    group_taxids_by_rank,# Group a list of taxids at a given rank
)

# The rank tables live in taxdumpy.functions, not the package root:
from taxdumpy.functions import RANKNAMES, EXTENDED_RANKS
# RANKNAMES:      9 canonical levels, species → realm (domain/superkingdom are aliases)
# EXTENDED_RANKS: 32 names including sub-ranks and aliases
```

`domain` and `superkingdom` resolve to the same rank level. Realm uses `r__` in
MPA output and the root-level `R` rank code, preserving existing integer `RC`
values. Grouping by `root` always selects taxid 1, including viral lineages.

`upper_rank_id` requires the requested higher rank or its subrank to exist in
the lineage; otherwise it raises `TaxRankError`. Use `get_closest_rank` or
`get_rank_or_closest` when fallback to a higher canonical rank is desired.

### Subtree Traversal

```python
from taxdumpy import descendants, descendant_nodes, build_children_index

descendants(taxdb, taxid, max_depth=None) -> list[int]
# Every taxid below `taxid`. Excludes `taxid` itself, and excludes deleted
# and merged taxids. max_depth=1 gives direct children only. Breadth-first.

descendant_nodes(taxdb, taxid, max_depth=None) -> list[Node]
# Same, as Node objects. Costs one get_node per result.

build_children_index(taxdb) -> dict[int, list[int]]
# The parent-to-children index the above build and cache. Read-only.
```

### Exceptions

```python
from taxdumpy import (
    TaxdumpyError,          # Base exception
    TaxDbError,             # Database issues
    TaxidError,             # Invalid/unknown taxid
    TaxRankError,           # Invalid rank
    TaxdumpFileError,       # Taxdump file issues
    DatabaseCorruptionError, # Corrupted database
    ValidationError,        # Input validation failures
)
```

## Performance Tips

- **Single CLI Queries**: Use the default SQLite backend to avoid loading the full pickle
- **Python Batches**: Load one `TaxDb` instance and reuse it for multiple operations
- **Filtered Data**: Use `TaxDb(path, fast=True)` after building a subset cache;
  startup cost and memory use depend on the subset size
- **Environment Variables**: Set `TAXDB_PATH` to avoid repeating database paths
- **Choose Backend**: Use `TaxSQLite` for large datasets with limited memory
- **Batch Operations**: Process multiple TaxIDs in batches rather than individual calls
- **Subtree Queries**: Reuse one database instance so `descendants` shares its
  cached children index. Building it costs one pass over the database
  (~0.4 s for 1M nodes); every query afterwards is proportional to the subtree,
  and small subtrees resolve in microseconds

## Use Cases

- **Metagenomics**: Classify and annotate environmental sequences
- **Phylogenetics**: Build taxonomic trees and study evolutionary relationships
- **Bioinformatics**: Pipeline integration for taxonomy-aware analysis
- **Data Validation**: Verify and standardize organism names in datasets
- **Research**: Large-scale taxonomic studies and biodiversity analysis

## Requirements

- **Python**: 3.10+
- **Dependencies**: `rapidfuzz`, `tqdm`
- **Data**: NCBI taxdump files (~300MB compressed, ~2GB extracted)
- **Memory**: ~500MB RAM for full database (less with SQLite backend)

## Development & Contributing

### Development Setup

```bash
git clone https://github.com/omegahh/taxdumpy.git
cd taxdumpy
pip install -e '.[dev]'
```

### Testing

```bash
# Run all tests (requires 80% coverage)
pytest

# Run specific test categories
pytest -m "not slow and not integration"  # Fast tests only
pytest -m integration                      # Integration tests only

# With coverage report
pytest --cov=taxdumpy --cov-report=html
```

### Code Quality

```bash
# Format code and sort imports
ruff format src/ tests/
ruff check src/ tests/ --fix
```

### Release Process

A pushed `v*` tag creates a GitHub Release and publishes the package to PyPI
through the protected `pypi` GitHub Actions environment using OIDC. The tag
must match `__version__` in `src/taxdumpy/__init__.py`, and PyPI versions cannot
be overwritten.

The release helper remains available for maintainers who explicitly want its
local version bump and remote side effects. It requires a clean worktree, runs
tests and Ruff, updates and commits the version, pushes `origin main` and a
version tag, removes `dist/`, and builds the package. `--upload` publishes
through Twine. Run it only when those repository and remote changes are intended:

```bash
python scripts/release.py --version 1.2.3 --upload
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Related Projects**: [TaxonKit](https://github.com/shenwei356/taxonkit) (Go), [ete3](https://github.com/etetoolkit/ete) (Python), [taxizedb](https://github.com/ropensci/taxizedb) (R)
