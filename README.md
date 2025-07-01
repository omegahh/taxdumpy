# Taxdumpy 🧬

#### NCBI Taxonomy Toolkit for Python

*A high-performance parser for NCBI Taxonomy databases with lineage resolution and taxonomy search*

![](https://img.shields.io/badge/license-MIT-blue.svg)
![](https://img.shields.io/badge/python-3.10+-blue.svg)
![](https://img.shields.io/pypi/v/taxdumpy?color=green)

## Features

- **Blazing Fast Parsing**  
  Optimized loading of NCBI taxdump files (`nodes.dmp`, `names.dmp`, etc.) with optional pickle caching

- **Comprehensive Taxon Operations**  
  - TaxID validation and lineage tracing
  - Scientific name resolution
  - Rank-based filtering (species → kingdom)
  - Merged/deleted node handling

- **Fuzzy Search**  
  Rapid approximate name matching using `rapidfuzz` (supports misspellings)

- **Memory Efficient**  
  Lazy loading and optimized data structures for large taxonomies

## Installation

```bash
pip install taxdumpy
```

Or from source:
```bash
git clone https://github.com/yourusername/taxdumpy.git
cd taxdumpy
pip install -e .
```

## Quick Start

```python
from taxdumpy import TaxDb, Taxon

# Initialize database (auto-downloads if needed)
taxdb = TaxDb("/path/to/taxdump")

# Create taxon object
human = Taxon(9606, taxdb)  # Homo sapiens

# Access lineage
print(human.name_lineage)
# ['Homo sapiens', 'Homo', 'Hominidae', ..., 'cellular organisms']

# Search organisms
taxdb._rapid_fuzz("Influenza", limit=5)
```

## Command Line Interface

```bash
# Cache full database
taxdumpy cache -d /path/to/taxdump

# Search organism
taxdumpy search --fast "Escherichia coli"

# Trace lineage
taxdumpy lineage --fast 511145  # E. coli K-12
```

## Database Setup

1. Download NCBI taxdump:  
   ```bash
   mkdir -p ~/.taxonkit
   wget ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz -P ~/.taxonkit
   tar -xzf ~/.taxonkit/taxdump.tar.gz -C ~/.taxonkit
   ```

2. (Optional) Create optimized cache:  
   ```bash
   taxdumpy cache -d ~/.taxonkit
   ```

## Advanced Usage

### Custom Caching
```python
# Fast cache with specific taxids
with open("important_taxids.txt", "w") as f:
    f.write("\n".join(["9606", "511145"]))
    
# CLI
taxdumpy fast-cache -d ~/.taxonkit -f important_taxids.txt
```

### API Reference
```python
class Taxon:
    """Represents a taxonomic unit"""
    
    @property
    def lineage(self) -> List[Node]: ...
    @property
    def rank_lineage(self) -> List[str]: ...
    @property
    def is_legacy(self) -> bool: ...
```

## Performance Tips

- Use `fast=True` when loading for ~3x speedup (requires pre-caching)
- For batch processing, reuse `TaxDb` instances
- Set `TAXDB_PATH` environment variable to avoid path repetition

## Contributing

PRs welcome! Please:
1. Format with `black`
2. Include type hints
3. Add tests under `/tests`

## License

MIT © 2025 [Omega HH](https://github.com/omegahh)
