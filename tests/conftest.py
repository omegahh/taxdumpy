"""Pytest configuration and shared fixtures."""

import os
import tempfile
import pytest
import shutil
from pathlib import Path
from typing import Generator

import taxdumpy
from taxdumpy import TaxDb, TaxSQLite


@pytest.fixture(scope="session")
def sample_taxdump_dir() -> Generator[Path, None, None]:
    """Copy test data to a temporary directory for testing."""
    test_data_path = Path(__file__).parent / "data"

    with tempfile.TemporaryDirectory() as temp_dir:
        taxdump_path = Path(temp_dir)

        # Copy all files from test data directory
        for file_path in test_data_path.glob("*.dmp"):
            shutil.copy2(file_path, taxdump_path)

        yield taxdump_path


@pytest.fixture
def sample_taxdb(sample_taxdump_dir: Path) -> TaxDb:
    """Create a TaxDb instance with sample data."""
    return TaxDb(sample_taxdump_dir)


@pytest.fixture
def sample_taxsqlite(sample_taxdump_dir: Path) -> Generator[TaxSQLite, None, None]:
    """Create a TaxSQLite instance with sample data."""
    taxsqlite = TaxSQLite(sample_taxdump_dir)
    yield taxsqlite
    taxsqlite.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_taxids():
    """Common taxids for testing based on actual test data."""
    return {
        "root": 1,
        "bacteria": 2,
        "archaea": 2157,
        "eukaryota": 2759,
        "cellular_organisms": 131567,
        "human": 9606,
        "homo": 9605,
        "primates": 9443,
        "mammals": 40674,
        "methanobacterium_bryantii": 2161,
        "nocardioides_plantarum": 29299,
        "halichondria_panicea": 6063,
        "callorhinchus_milii": 7868,
        "plasmopara_halstedii": 4781,
        "orthoflavivirus_apoiense": 3047370,
        # Legacy mappings from merged.dmp (actual data)
        "legacy_6043": 6043,  # maps to 6042
        "legacy_6048": 6048,  # maps to 6042
        "legacy_13770": 13770,  # maps to 2161
        # Deleted nodes from delnodes.dmp (actual data)
        "deleted_3451490": 3451490,
        "deleted_3451488": 3451488,
        "deleted_3451474": 3451474,
    }
