"""Pytest configuration and shared fixtures."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from taxdumpy import TaxDb, TaxSQLite
from taxdumpy.cli import main


def copy_sources(destination):
    for path in (Path(__file__).parent / "data").glob("*.dmp"):
        shutil.copy2(path, destination / path.name)
    return destination


@pytest.fixture
def raw_source_dir(tmp_path):
    """Taxdump source files without caches, for importer tests."""
    return copy_sources(tmp_path)


@pytest.fixture
def cached_dir(raw_source_dir):
    assert main(["cache", "-d", str(raw_source_dir)]) == 0
    return raw_source_dir


@pytest.fixture
def fast_cache_dir(cached_dir):
    selection = cached_dir / "selected.txt"
    selection.write_text("9606\n561\n")
    assert main(["cache", "-d", str(cached_dir), "-f", str(selection)]) == 0
    return cached_dir


@pytest.fixture(scope="session")
def sample_taxdump_dir() -> Generator[Path, None, None]:
    """Copy test data to a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        taxdump_path = copy_sources(Path(temp_dir))
        assert main(["cache", "-d", str(taxdump_path)]) == 0
        yield taxdump_path


@pytest.fixture
def sample_taxdb(sample_taxdump_dir: Path) -> Generator[TaxDb, None, None]:
    """Create a TaxDb instance with sample data."""
    with TaxDb(sample_taxdump_dir) as db:
        yield db


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
