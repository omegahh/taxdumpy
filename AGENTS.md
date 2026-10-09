# Repository Guidance

Instructions and verified project notes for agents working in this repository.

## Rules

- Do not add "Co-Authored-By" messages in git commits

## Project Overview

**Taxdumpy** is a high-performance Python toolkit for parsing NCBI Taxonomy databases with lineage resolution and fuzzy search capabilities. Designed for metagenomics, phylogenetics, and bioinformatics applications.

- **Version source**: `src/taxdumpy/__init__.py` (Hatch reads the version from this file)
- **Python**: 3.10+
- **License**: MIT

## Development Commands

### Installation and Setup
```bash
# Install in development mode
python -m pip install -e .

# Install with dependencies
python -m pip install -e '.[dev]'
```

### Running the CLI
```bash
# Cache taxonomy database (requires NCBI taxdump files)
taxdumpy cache -d /path/to/taxdump

# Search for organisms with fuzzy matching
taxdumpy search --fast "Escherichia coli"

# Get lineage for a specific taxid
taxdumpy lineage 511145
```

`search --fast` and `lineage --fast` need a filtered pickle cache created with
`cache -f FILE`. Without `--fast`, both commands use SQLite to avoid loading the
full pickle for a single query. Python batch callers should create one `TaxDb`
instance and reuse it for all queries.

### Testing and Quality
```bash
# Run all tests with coverage (requires 80% minimum)
pytest

# Run specific test categories
pytest -m "not slow and not integration"  # Fast tests only
pytest -m "slow"                          # Slow tests only
pytest -m "integration"                   # Integration tests only
pytest -m "unit or not (slow or integration)"  # Unit and unmarked non-slow tests

# Run tests with coverage report
pytest --cov=taxdumpy --cov-report=html --cov-report=term-missing

# Run a focused test file without the repository-wide coverage threshold
pytest tests/test_taxdb.py --no-cov

# Format code and sort imports with ruff
ruff format src/ tests/  # Format code
ruff check src/ tests/ --fix  # Fix import sorting

# Check formatting and imports in CI mode
ruff format --check src/ tests/
ruff check src/ tests/  # Only checks import sorting (I rules)
```

**Note**: Ruff is configured with `line-length = 120`, and only handles formatting and import sorting (I rules). All other linting is disabled.

**Note**: pytest config lives in `pytest.ini` under a `[pytest]` section. It must
not be `[tool:pytest]` — that is the `setup.cfg` spelling, and pytest silently
ignores the whole file, taking `--strict-markers` and the 80% coverage gate with
it. Running `pytest` requires `pytest-cov` to be installed, since `addopts`
passes `--cov` unconditionally.

Test fixtures copy the `.dmp` files into temporary directories, and backend
caches are written there. Pytest also writes coverage reports in the repository
root; those reports and cache filenames are gitignored.

### Build and Release
```bash
# Build an sdist and wheel (requires the `build` package)
python -m build

# A pushed v* tag triggers GitHub Release creation; it does not publish to PyPI.
# Build and upload separately with Twine when a PyPI release is intended.
# python -m twine upload dist/*
```

`scripts/release.py` has remote and repository side effects: it requires a clean
worktree, updates the version, commits it, pushes `origin main` and a version
tag, removes the existing `dist/` directory, and builds the package. Its
`--upload` option publishes to PyPI. Read the script and use it only when those
exact actions are intended.

## Architecture Overview

### Project Structure
```
src/taxdumpy/
├── __init__.py          # Package initialization and exports
├── __main__.py          # CLI entry point
├── ansi.py              # ANSI color formatting utilities
├── basic.py             # Core data structures (Node) and exception hierarchy
├── ranks.py             # Shared canonical rank names, levels and codes
├── database.py          # Abstract base class (TaxonomyDatabase) + factory function
├── cache.py             # Source signatures and atomic pickle replacement
├── taxdb.py             # Dictionary-based in-memory backend with pickle caching
├── taxsqlite.py         # SQLite-based persistent backend
├── taxon.py             # Taxon entity with lineage resolution
├── functions.py         # Rank utilities (upper_rank_id, get_canonical_ranks) + subtree traversal (descendants)
└── cli.py               # CLI commands: cache, search, lineage

tests/
├── conftest.py          # Pytest fixtures
├── data/                # Sample taxdump files for testing
├── test_api_consistency.py
├── test_basic.py
├── test_cache.py
├── test_cli.py
├── test_critical_regressions.py  # Pins previously-shipped critical defects
├── test_descendants.py           # Subtree traversal, parametrized over both backends
├── test_error_handling.py
├── test_fast_cache.py
├── test_functions.py
├── test_integration.py
├── test_taxdb.py
├── test_taxon.py
└── test_taxsqlite.py
```

### Core Components

#### Database Layer

**TaxonomyDatabase** (`database.py`): Abstract base class defining the consistent API
- Abstract methods: `get_node()`, `_rapid_fuzz()`, `__len__()`, `__repr__()`
- Shared `search()` returns structured results; `fuzzy_search()` prints them
- Shared methods: `_validate_taxid()` - validates and converts taxid to integer
- Abstract cached properties: `all_names`, `name2taxid`, `delnodes`, `max_taxid_strlen`, `max_rank_strlen`
- Context manager support for connection management
- Formatting width properties return zero for an empty database

**Important**: these five properties use the module's `abstract_cached_property`
helper, not `@cached_property` over `@abstractmethod`. Stacking those two
silently breaks enforcement — `cached_property` does not propagate
`__isabstractmethod__`, so ABCMeta never sees the member and a subclass omitting
it instantiates fine, returning `None`. Do not "simplify" this back.

**TaxDb** (`taxdb.py`): Dictionary-based in-memory database
- Fast mode (`fast=True`) loads `taxdump_fast.pickle`, built from the taxids in a
  filter file, their ancestors, and their descendants
- Deserializes a pickle once per initialization; reuse the instance for batches
- `build_fast_cache(taxids)` validates selections and writes the filtered cache
- New pickle caches include versioned source signatures; original three-part
  pickles remain readable. Changes in available source sizes or mtimes trigger
  a rebuild; caches remain usable when source files have been removed
- Pickle writes use atomic replacement. `rebuild=True` forces a full rebuild;
  a failed rebuild preserves the previous cache
- Missing, stale or corrupt fast caches require an explicit filtered rebuild
- Data structures: `_taxid2nodes` (dict), `_old2news` (merged taxids), `_delnodes` (set)

**TaxSQLite** (`taxsqlite.py`): SQLite-based persistent database
- Tables: `nodes` (taxid, parent, rank, division), `names` (taxid, name, name_class), `merged` (oldtid, newtid), `delnodes` (taxid)
- All four tables are listed in `REQUIRED_TABLES`; `_check_tables` validates every one, so a cache built by an older version with a narrower schema is rebuilt rather than trusted
- The database is self-contained: no `.dmp` file is read at query time
- Builds go to a `mkstemp` temp path and are `os.replace`d into position, so an interrupted build cannot leave a schema-complete but empty database behind
- Indexed for fast queries
- Deleted-taxid checks use an indexed lookup rather than loading the whole set
- New caches record source signatures in `source_files`; legacy caches use
  source mtimes. `rebuild=True` forces a rebuild with atomic replacement
- Memory-efficient for large datasets

**Factory Function**: `create_database(taxdump_dir, backend="sqlite", ...)`.
Supported backend names are `sqlite`/`sql` and `dict`/`memory`/`pickle`.

#### Data Structures

**Node** (`basic.py`): Dataclass with `__slots__` optimization
- Fields: `taxid`, `parent`, `rank`, `name`, `equal`, `acronym`, `division`

**Taxon** (`taxon.py`): Main entity for taxonomy operations
- Properties: `lineage`, `taxid_lineage`, `rank_lineage`, `name_lineage`
- Properties: `is_legacy`, `has_species_level`, `species_taxid`
- Traces lineage from any taxid to root, handles merged taxids automatically

#### Exception Hierarchy

```
TaxdumpyError (base)
├── TaxDbError          # Database-related issues
│   ├── TaxdumpFileError        # File issues (includes solutions)
│   └── DatabaseCorruptionError
├── TaxidError          # Invalid/unknown taxid (includes suggestions)
├── TaxRankError        # Invalid taxonomic rank (includes valid ranks)
├── TaxdumpyMemoryError
└── ValidationError     # Input validation failures
```

#### Rank Functions (`functions.py`)

- Rank tables live in `ranks.py` and are re-exported by `functions.py`
- `RankName` defines 9 levels plus the `domain` alias of `superkingdom`;
  `RANKNAMES` is derived via `get_args` (species to realm)
- Realm uses the root-level `R` code to preserve existing integer encodings,
  and `r__` in MPA output. Root itself is omitted from MPA output
- `EXTENDED_RANKS`: 32 names including sub-ranks and aliases
- `upper_rank_id()`: Get taxid at specific canonical rank (strict)
- `get_rank_taxid()`: Safely get taxid for rank (returns None if not found)
- `get_canonical_ranks()`: Get all canonical ranks in lineage as dict
- `get_closest_rank()`: Get closest rank at or above target level
- `get_rank_or_closest()`, `get_all_ranks()`, `find_rank_in_lineage()`
- `get_rank_distance()`: Calculate distance between two canonical ranks
- `group_taxids_by_rank()`: Group taxids by rank using their closest ancestor

#### Subtree Traversal (`functions.py`)

Lineage tracing walks *up*; these walk *down*.

- `descendants(taxdb, taxid, max_depth=None)`: every taxid below `taxid`,
  excluding `taxid` itself and excluding deleted/merged taxids. Breadth-first.
  `max_depth=1` gives direct children only
- `descendant_nodes()`: the same as `Node` objects (one `get_node` per result)
- `build_children_index(taxdb)`: inverts child→parent in one pass, cached per
  database in a `WeakKeyDictionary` so a closed database does not pin a
  million-entry index. Traversal is iterative, so deep trees cannot exhaust the
  stack

These reach into `taxdb._taxid2nodes` and `taxsqlite._conn` for speed, so they
dispatch on backend type and raise `TaxDbError` for any third backend. Moving
them onto `TaxonomyDatabase` would remove that coupling.

### Data Flow
1. NCBI taxdump files (nodes.dmp, names.dmp, etc.) are parsed
2. Data is cached as either pickle files (TaxDb) or SQLite database (TaxSQLite)
3. Taxon objects provide lineage tracing and taxonomy operations
4. CLI commands leverage either backend for search/lineage operations

### CLI Commands

| Command | Description | Key Options |
|---------|-------------|-------------|
| `cache` | Build SQLite and full pickle caches; with `-f`, build only a filtered fast pickle | `-d/--directory`, `-f/--filter-file` |
| `search` | Fuzzy organism name search | `-d/--directory`, `--fast`, `--limit` |
| `lineage` | Display taxonomic lineage (SQLite by default, filtered pickle with `--fast`) | `-d/--directory`, `--fast` |

### Environment Variables
- `TAXDB_PATH`: Default path to taxonomy database (defaults to `~/.taxonkit`)

### Performance Features
- Pickle caching for repeated Python queries; `fast=True` loads a filtered cache
- SQLite backend for memory efficiency with large datasets
- Rapidfuzz integration for fuzzy organism name matching
- Fast cache mode for selected taxids and their related lineage/subtree

### Database Requirements
Building a new cache from source requires NCBI taxdump files:
- `nodes.dmp`: Taxonomy tree structure
- `names.dmp`: Scientific names
- `merged.dmp`: Legacy taxid mappings
- `delnodes.dmp`: Deleted nodes
- `division.dmp`: Division information

### Dependencies
- **Core**: `rapidfuzz` (fuzzy matching), `tqdm` (progress bars)
- **Dev**: `ruff`, `pytest`, `pytest-cov`, `pytest-mock`, `build`

## Known Issues

These issues are still present in the checked-in implementation. Recheck this
section when the corresponding code or tests change.

**Test gaps**: `tests/test_functions.py` still needs broader tests for rank
helpers, especially `get_all_ranks` and `find_rank_in_lineage`.
The full suite measured `functions.py` at 68% coverage and the package at 85%
in the repository environment during this audit.
