# Taxdumpy

_A high-performance Python toolkit for parsing NCBI Taxonomy databases with lineage resolution and fuzzy search_

[![CI](https://github.com/omegahh/taxdumpy/workflows/CI/badge.svg)](https://github.com/omegahh/taxdumpy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxdumpy?color=green)](https://pypi.org/project/taxdumpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Development Status](https://img.shields.io/badge/Development%20Status-5%20Production/Stable-brightgreen)](https://pypi.org/project/taxdumpy/)
[![codecov](https://codecov.io/gh/omegahh/taxdumpy/branch/main/graph/badge.svg)](https://codecov.io/gh/omegahh/taxdumpy)

## Features

- **Fast Parsing**: Optimized loading of NCBI taxdump files with pickle caching for ~3x speedup
- **Dual Backends**: In-memory (`TaxDb`) for speed or SQLite (`TaxSQLite`) for memory efficiency
- **Lineage Resolution**: Complete lineage tracing with automatic handling of merged/deleted nodes
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
pip install -e .[dev]
```

## Quick Start

### Basic Usage

```python
from taxdumpy import TaxDb, Taxon

# Initialize database (uses pickle cache if available)
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
print(f"Division: {human.division}")   # Primates
print(f"Is legacy: {human.is_legacy}") # False
```

### Using the Factory Function

```python
from taxdumpy import create_database, Taxon

# Create database with preferred backend
db = create_database(backend="sqlite", taxdump_dir="/path/to/taxdump")
# Or: backend="dict" for in-memory

taxon = Taxon(9606, db)
print(taxon.name)  # Homo sapiens
```

### Fuzzy Search

```python
# Search with typos and partial matches
results = taxdb._rapid_fuzz("Escherichia coli", limit=5)
for match in results:
    print(f"{match['name']} (TaxID: {match['taxid']}, Score: {match['score']})")
```

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

### Check Version

```bash
taxdumpy --version
```

### Cache Database

```bash
# Cache full NCBI taxonomy database
taxdumpy cache -d /path/to/taxdump

# Create fast cache with specific organisms
taxdumpy cache -d /path/to/taxdump -f important_taxids.txt
```

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

### 2. Initialize Database

```bash
# Create full cache (recommended for regular use)
taxdumpy cache -d ~/.taxonkit

# Or create fast cache with specific organisms
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

# Use SQLite for memory-efficient storage
db = TaxSQLite("/path/to/taxdump")  # Creates taxonomy.db in that directory

# Same API as TaxDb
taxon = Taxon(9606, db)
print(taxon.name_lineage)

# Use as context manager
with TaxSQLite("/path/to/taxdump") as db:
    taxon = Taxon(9606, db)
    print(taxon.name)
```

### Batch Processing

```python
from taxdumpy import TaxDb, Taxon

# Reuse database instance for efficiency
taxdb = TaxDb("/path/to/taxdump", fast=True)

taxids = [9606, 511145, 7227, 4932]  # Human, E.coli, Fly, Yeast
for taxid in taxids:
    taxon = Taxon(taxid, taxdb)
    print(f"{taxon.name}: {' > '.join(taxon.name_lineage[:3])}")
```

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
from taxdumpy import TaxDb, Taxon, TaxidError, TaxRankError, TaxDbError

taxdb = TaxDb("/path/to/taxdump")

try:
    taxon = Taxon(999999999, taxdb)
except TaxidError as e:
    print(f"Invalid taxid: {e}")
    # Includes suggestions for similar taxids

try:
    rank_id = upper_rank_id(9606, "invalid_rank", taxdb)
except TaxRankError as e:
    print(f"Invalid rank: {e}")
    # Includes list of valid ranks
```

## API Reference

### Core Classes

**TaxDb**: In-memory dictionary-based database with pickle caching

```python
TaxDb(taxdump_dir: str, fast: bool = False)
```

**TaxSQLite**: SQLite-based persistent database

```python
TaxSQLite(taxdump_dir: str)
```

**Taxon**: Taxonomic unit with lineage resolution

```python
Taxon(taxid: int, taxdb: TaxDb | TaxSQLite)

# Properties
.name: str               # Scientific name
.rank: str               # Taxonomic rank
.division: str           # NCBI division
.parent: int             # Parent taxid
.lineage: list[Node]     # Complete lineage as Node objects
.name_lineage: list[str] # Names from taxid to root
.rank_lineage: list[str] # Ranks from taxid to root
.taxid_lineage: list[int] # Taxids from taxid to root
.is_legacy: bool         # True if taxid was merged
.has_species_level: bool # True if lineage contains species rank
.species_taxid: int | None # Taxid at species level
```

**Factory Function**

```python
from taxdumpy import create_database

# backend: "sqlite", "sql", "dict", "memory", or "pickle"
db = create_database(backend="sqlite", taxdump_dir="/path/to/taxdump")
```

### Rank Functions

```python
from taxdumpy import (
    upper_rank_id,      # Get taxid at rank (raises TaxRankError if not found)
    get_rank_taxid,     # Get taxid at rank (returns None if not found)
    get_canonical_ranks, # Get dict of all canonical ranks in lineage
    get_closest_rank,   # Get closest rank at or above target level
    get_rank_distance,  # Calculate distance between two ranks
    RANKNAMES,          # 8 canonical ranks: species → realm
    EXTENDED_RANKS,     # 30+ ranks including sub-ranks
)
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

- **Use Fast Mode**: `TaxDb(path, fast=True)` provides ~3x speedup with pre-cached data
- **Reuse Instances**: Create one `TaxDb` instance and reuse for multiple operations
- **Environment Variables**: Set `TAXDB_PATH` to avoid repeating database paths
- **Choose Backend**: Use `TaxSQLite` for large datasets with limited memory
- **Batch Operations**: Process multiple TaxIDs in batches rather than individual calls

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
pip install -e .[dev]
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

```bash
# Automated release
python scripts/release.py --version 1.2.3 --upload

# Or manual: create tag and push (GitHub Actions publishes to PyPI)
git tag v1.2.3 && git push origin v1.2.3
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Related Projects**: [TaxonKit](https://github.com/shenwei356/taxonkit) (Go), [ete3](https://github.com/etetoolkit/ete) (Python), [taxizedb](https://github.com/ropensci/taxizedb) (R)
