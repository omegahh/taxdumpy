# Taxdumpy 🧬

_A high-performance Python toolkit for parsing NCBI Taxonomy databases with lineage resolution and fuzzy search_

[![CI](https://github.com/omegahh/taxdumpy/workflows/CI/badge.svg)](https://github.com/omegahh/taxdumpy/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/taxdumpy?color=green)](https://pypi.org/project/taxdumpy/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Development Status](https://img.shields.io/badge/Development%20Status-5%20Production/Stable-brightgreen)](https://pypi.org/project/taxdumpy/)
[![codecov](https://codecov.io/gh/omegahh/taxdumpy/branch/main/graph/badge.svg)](https://codecov.io/gh/omegahh/taxdumpy)

## Features

- **🚀 Blazing Fast Parsing**
  Optimized loading of NCBI taxdump files (`nodes.dmp`, `names.dmp`, etc.) with pickle caching for 3x speedup

- **🔬 Comprehensive Taxon Operations**
  - TaxID validation and complete lineage tracing
  - Scientific name resolution and rank-based filtering
  - Handle merged/deleted nodes and legacy taxonomies
  - Access to division information and metadata

- **🔍 Fuzzy Search**
  Rapid approximate name matching using `rapidfuzz` - find organisms even with typos

- **⚡ High Performance**
  - Memory-efficient data structures for large taxonomies
  - Dual backend support: in-memory (TaxDb) and SQLite (TaxSQLite)
  - Lazy loading and optimized caching strategies

- **🖥️ Command Line Interface**
  Ready-to-use CLI for caching, searching, and lineage resolution

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

# Initialize database
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
print(f"Division: {human.division}")   # Mammals
print(f"Is legacy: {human.is_legacy}") # False
```

### Fuzzy Search

```python
# Search with typos and partial matches
results = taxdb._rapid_fuzz("Escherichia coli", limit=5)
for match in results:
    print(f"{match['name']} (TaxID: {match['taxid']}, Score: {match['score']})")

# Search influenza strains
flu_results = taxdb._rapid_fuzz("Influenza A", limit=10)
```

## Command Line Interface

### Check Version

```bash
# Display current version
taxdumpy --version
# Output: taxdumpy 0.1.1
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
from taxdumpy import TaxSQLite

# Use SQLite for memory-efficient storage
db = TaxSQLite("/path/to/database.sqlite")
db.build_database("/path/to/taxdump")

# Same API as TaxDb
taxon = Taxon(9606, db)
print(taxon.name_lineage)
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

### Custom Utilities

```python
from taxdumpy import upper_rank_id

# Find parent at specific taxonomic rank
kingdom_id = upper_rank_id(9606, "kingdom", taxdb)
print(f"Human kingdom TaxID: {kingdom_id}")  # 33208 (Metazoa)
```

## API Reference

### Core Classes

**TaxDb**: In-memory dictionary-based database

```python
TaxDb(taxdump_dir: str, fast: bool = False)
```

**TaxSQLite**: SQLite-based persistent database

```python
TaxSQLite(db_path: str)
```

**Taxon**: Taxonomic unit with lineage resolution

```python
Taxon(taxid: int, taxdb: TaxDb | TaxSQLite)

# Properties
.name: str              # Scientific name
.rank: str              # Taxonomic rank
.division: str          # NCBI division
.lineage: List[Node]    # Complete lineage
.name_lineage: List[str] # Names only
.rank_lineage: List[str] # Ranks only
.is_legacy: bool        # Legacy/merged node
```

## Performance Tips

- **Use Fast Mode**: `TaxDb(path, fast=True)` provides ~3x speedup with pre-cached data
- **Reuse Instances**: Create one `TaxDb` instance and reuse for multiple operations
- **Environment Variables**: Set `TAXDB_PATH` to avoid repeating database paths
- **Choose Backend**: Use `TaxSQLite` for large datasets with limited memory
- **Batch Operations**: Process multiple TaxIDs in batches rather than individual calls

## Use Cases

- **🧬 Metagenomics**: Classify and annotate environmental sequences
- **🔬 Phylogenetics**: Build taxonomic trees and study evolutionary relationships
- **📊 Bioinformatics**: Pipeline integration for taxonomy-aware analysis
- **🔍 Data Validation**: Verify and standardize organism names in datasets
- **📈 Research**: Large-scale taxonomic studies and biodiversity analysis

## Requirements

- **Python**: 3.10+
- **Dependencies**: `rapidfuzz`, `tqdm`
- **Data**: NCBI taxdump files (~300MB compressed, ~2GB extracted)
- **Memory**: ~500MB RAM for full database (less with SQLite backend)

## Development & Contributing

### Development Setup

```bash
# Clone repository
git clone https://github.com/omegahh/taxdumpy.git
cd taxdumpy

# Install in development mode
pip install -e .[dev]

# Run tests
pytest

# Format code
black src/ tests/

# Check types and linting
make lint
```

### CI/CD Pipeline

The project uses GitHub Actions for automated testing and deployment:

- **CI Workflow**: Tests across Python 3.10-3.13, code formatting, and coverage
- **PyPI Publishing**: Automatic releases on version tags (`v*`)
- **Test PyPI**: Pre-release testing with tags like `v1.2.3-beta.1`

### Release Process

```bash
# Automated release (recommended)
python scripts/release.py --version 1.2.3 --upload

# Manual tagging triggers GitHub Actions
git tag v1.2.3
git push origin v1.2.3
```

### Contributing Guidelines

1. **Code Style**: Use `black` for formatting
2. **Type Hints**: Include comprehensive type annotations
3. **Testing**: Maintain >80% test coverage
4. **Documentation**: Update README and docstrings
5. **Commits**: Use conventional commit messages

## License

MIT © 2025 [Omega HH](https://github.com/omegahh)

---

**Related Projects**: [TaxonKit](https://github.com/shenwei356/taxonkit) (Go), [ete3](https://github.com/etetoolkit/ete) (Python), [taxizedb](https://github.com/ropensci/taxizedb) (R)
