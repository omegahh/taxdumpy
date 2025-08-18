# Testing Guide for Taxdumpy

This document explains how to run and manage tests for the taxdumpy package.

## Quick Start

### 1. Install Development Dependencies
```bash
# Install package in development mode with test dependencies
pip install -e .[dev]
```

### 2. Run All Tests
```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=taxdumpy --cov-report=term-missing
```

## Test Categories

### Unit Tests
Test individual components in isolation:
```bash
# Run only unit tests (fast)
pytest -m "unit or not (slow or integration)"

# Or use the Makefile
make test-fast
```

### Integration Tests
Test components working together:
```bash
pytest -m "integration"
make test-integration
```

### Slow Tests
Tests that take longer to run (database rebuilding, etc.):
```bash
pytest -m "slow"
make test-slow
```

## Using Make Commands

The project includes a Makefile with convenient commands:

```bash
make help              # Show all available commands
make install           # Install in development mode
make test              # Run all tests
make test-fast         # Run only fast tests
make test-integration  # Run only integration tests
make coverage          # Run tests with HTML coverage report
make lint              # Check code formatting
make format            # Format code with black
make clean             # Clean build artifacts
```

## Test Structure

```
tests/
├── __init__.py           # Test package marker
├── conftest.py          # Shared fixtures and configuration
├── test_basic.py        # Tests for basic data structures
├── test_taxdb.py        # Tests for TaxDb class
├── test_taxsqlite.py    # Tests for TaxSQLite class  
├── test_taxon.py        # Tests for Taxon class
├── test_functions.py    # Tests for utility functions
├── test_cli.py          # Tests for command-line interface
└── test_integration.py  # Integration tests
```

## Fixtures and Sample Data

The test suite includes automatically generated sample taxdump data for testing:

- **sample_taxdump_dir**: Creates minimal NCBI taxdump files
- **sample_taxdb**: TaxDb instance with sample data
- **sample_taxsqlite**: TaxSQLite instance with sample data
- **sample_taxids**: Dictionary of common test taxids

Sample organisms included:
- Human (Homo sapiens) - 9606
- E. coli strain K-12 - 511145  
- E. coli species - 83333
- Bacteria superkingdom - 2
- Root - 1
- Legacy taxid example - 12345 → 511145

## Coverage Reporting

### Generate Coverage Reports
```bash
# Terminal report
pytest --cov=taxdumpy --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=taxdumpy --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest --cov=taxdumpy --cov-report=xml
```

### Coverage Goals
- Target: ≥80% overall coverage
- Core classes (TaxDb, TaxSQLite, Taxon) should have ≥90% coverage
- CLI functionality should have ≥70% coverage

## Running Specific Tests

### By file:
```bash
pytest tests/test_taxdb.py              # All TaxDb tests
pytest tests/test_cli.py::TestCLI       # Specific test class
```

### By pattern:
```bash
pytest -k "test_search"                 # All search-related tests
pytest -k "taxdb and not integration"   # TaxDb tests, excluding integration
```

### By markers:
```bash
pytest -m "not slow"                    # Skip slow tests
pytest -m "integration"                 # Only integration tests
```

## Debugging Tests

### Verbose output:
```bash
pytest -v -s                           # Show print statements
pytest --tb=short                      # Shorter traceback
pytest --tb=long                       # Detailed traceback
```

### Run single test with debugging:
```bash
pytest -v -s tests/test_taxdb.py::TestTaxDb::test_get_node_valid_taxid
```

### PDB debugging:
```bash
pytest --pdb                           # Drop to debugger on failure
pytest --pdb-trace                     # Start debugger immediately
```

## Continuous Integration

### Local CI simulation:
```bash
# Run the same tests as CI
make ci-test
make ci-lint

# Or manually:
pytest --cov=taxdumpy --cov-report=xml --cov-fail-under=80
black --check --diff src/ tests/
```

## Using Tox for Multiple Python Versions

If you have tox installed:
```bash
tox                    # Test on all Python versions
tox -e py311           # Test on Python 3.11 only
tox -e lint            # Run linting
tox -e coverage        # Run coverage analysis
```

## Test Data Management

### Sample data is automatically created
The test fixtures automatically generate minimal sample taxdump data. No external data files are required.

### Custom test data
To test with real NCBI data:
```bash
# Download real taxdump
wget ftp://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz
tar -xzf taxdump.tar.gz

# Run tests with real data (requires environment variable)
TAXDB_PATH=./taxdump pytest tests/test_integration.py
```

## Writing New Tests

### Test file naming:
- Test files: `test_*.py`
- Test classes: `Test*`  
- Test methods: `test_*`

### Using fixtures:
```python
def test_my_feature(sample_taxdb, sample_taxids):
    """Test my feature with sample data."""
    taxon = Taxon(sample_taxids['human'], sample_taxdb)
    assert taxon.name == "Homo sapiens"
```

### Marking tests:
```python
@pytest.mark.slow
def test_slow_operation():
    """This test takes a long time."""
    pass

@pytest.mark.integration  
def test_components_together():
    """Test multiple components working together."""
    pass
```

## Troubleshooting

### Common issues:

1. **Import errors**: Make sure package is installed in development mode
   ```bash
   pip install -e .[dev]
   ```

2. **Missing dependencies**: Install test dependencies
   ```bash
   pip install pytest pytest-cov pytest-mock
   ```

3. **Fixtures not found**: Check that `conftest.py` is in the tests directory

4. **Coverage too low**: Add more tests or exclude non-testable code in `.coveragerc`

### Getting help:
```bash
pytest --help                 # Pytest options
make help                     # Available make commands
```