"""Regression tests for previously-fixed critical defects.

Each test here pins a specific bug that shipped once and was silent in normal
use. They are deliberately behavioural: none of them inspect private state.
"""

import shutil
import sqlite3
from pathlib import Path

import pytest

from taxdumpy import TaxDb, TaxSQLite
from taxdumpy.cli import main
from taxdumpy.database import TaxonomyDatabase


@pytest.fixture
def taxdump_copy(tmp_path: Path) -> Path:
    """A private, writable copy of the sample taxdump files."""
    src = Path(__file__).parent / "data"
    dst = tmp_path / "taxdump"
    dst.mkdir()
    for f in src.glob("*.dmp"):
        shutil.copy2(f, dst)
    assert main(["cache", "-d", str(dst)]) == 0
    return dst


class TestSQLiteSelfContained:
    """The SQLite database must not read .dmp files at query time."""

    def test_queries_work_after_dmp_files_removed(self, taxdump_copy: Path):
        with TaxSQLite(taxdump_copy) as db:
            expected_len = len(db)
            expected_delnodes = db.delnodes

        for f in taxdump_copy.glob("*.dmp"):
            f.unlink()

        with TaxSQLite(taxdump_copy) as db:
            assert len(db) == expected_len
            assert db.delnodes == expected_delnodes
            assert db.get_node(9606).name == "Homo sapiens"

    def test_delnodes_stored_in_database(self, taxdump_copy: Path):
        with TaxSQLite(taxdump_copy) as db:
            assert len(db.delnodes) > 0
            row = db._conn.execute("SELECT COUNT(*) FROM delnodes").fetchone()
            assert row[0] == len(db.delnodes)


class TestFailedBuildDoesNotPoison:
    """A failed build must not leave a valid-looking empty database behind."""

    def test_build_failure_is_repeatable(self, tmp_path: Path):
        # No .dmp files present, so the build must fail every time rather than
        # succeeding on the second attempt against a half-built database.
        for _ in range(2):
            with pytest.raises((FileNotFoundError, Exception)):
                TaxSQLite(tmp_path)

    def test_build_failure_leaves_no_database_file(self, tmp_path: Path):
        with pytest.raises(Exception):
            TaxSQLite(tmp_path)
        assert not (tmp_path / "taxdump.sqlite").exists()
        assert list(tmp_path.iterdir()) == []

    def test_existing_file_without_schema_is_rebuilt(self, taxdump_copy: Path):
        # A truncated/corrupt database should be replaced, not trusted.
        db_path = taxdump_copy / "taxdump.sqlite"
        db_path.unlink()
        sqlite3.connect(db_path).close()  # valid sqlite file, no tables
        with pytest.raises(Exception, match="required tables|stale"):
            TaxSQLite(taxdump_copy)
        assert main(["cache", "-d", str(taxdump_copy)]) == 0
        with TaxSQLite(taxdump_copy) as db:
            assert len(db) > 0
            assert db.get_node(9606).name == "Homo sapiens"

    def test_cache_from_older_version_is_rebuilt(self, taxdump_copy: Path):
        """A cache predating the delnodes table must be upgraded, not trusted.

        Older versions built nodes/names/merged only and read delnodes.dmp at
        query time, so such a file is schema-incomplete for current code.
        """
        db_path = taxdump_copy / "taxdump.sqlite"
        db_path.unlink()
        conn = sqlite3.connect(db_path)
        conn.executescript(
            """
            CREATE TABLE nodes (taxid INTEGER PRIMARY KEY, parent INTEGER NOT NULL,
                                rank TEXT NOT NULL, division TEXT NOT NULL);
            CREATE TABLE names (taxid INTEGER NOT NULL, name TEXT NOT NULL,
                                name_class TEXT NOT NULL, PRIMARY KEY (taxid, name_class, name));
            CREATE TABLE merged (oldtid INTEGER PRIMARY KEY, newtid INTEGER NOT NULL);
            """
        )
        conn.execute("INSERT INTO nodes VALUES (9606,9605,'species','MAM')")
        conn.commit()
        conn.close()

        with pytest.raises(Exception, match="required tables|stale"):
            TaxSQLite(taxdump_copy)
        assert main(["cache", "-d", str(taxdump_copy)]) == 0
        with TaxSQLite(taxdump_copy) as db:
            assert len(db) > 1  # rebuilt, not the single stub row
            assert len(db.delnodes) > 0
            assert db.get_node(9606).name == "Homo sapiens"
            assert "Deleted nodes" in repr(db)

    def test_no_temp_files_left_after_build(self, taxdump_copy: Path):
        with TaxSQLite(taxdump_copy) as db:
            assert len(db) > 0
        assert [p.name for p in taxdump_copy.iterdir() if p.name.endswith(".tmp")] == []


class TestAbstractContractEnforced:
    """The ABC must actually reject incomplete subclasses."""

    def test_cached_properties_are_abstract(self):
        for name in ("all_names", "name2taxid", "delnodes", "max_taxid_strlen", "max_rank_strlen"):
            assert name in TaxonomyDatabase.__abstractmethods__

    def test_incomplete_subclass_cannot_be_instantiated(self, tmp_path: Path):
        class Incomplete(TaxonomyDatabase):
            def get_node(self, taxid):
                raise NotImplementedError

            def fuzzy_search(self, query, limit=10):
                raise NotImplementedError

            def _rapid_fuzz(self, query, limit=10):
                raise NotImplementedError

            def __len__(self):
                return 0

            def __repr__(self):
                return ""

        with pytest.raises(TypeError, match="abstract"):
            Incomplete(tmp_path)

    def test_concrete_backends_are_instantiable(self):
        assert not TaxDb.__abstractmethods__
        assert not TaxSQLite.__abstractmethods__


class TestSearchQueryIsNotARegex:
    """User queries are escaped before being used as a regex pattern."""

    @pytest.mark.parametrize("query", ["Escherichia (coli", "coli)", "Homo [sapiens", "e+coli", "*coli"])
    def test_metacharacters_do_not_break_display(self, taxdump_copy: Path, capsys, query: str):
        for factory in (TaxDb, TaxSQLite):
            with factory(taxdump_copy) as db:
                db.fuzzy_search(query, limit=3)
            captured = capsys.readouterr().out
            assert "unterminated" not in captured
            assert "nothing to repeat" not in captured
            assert "Error displaying result" not in captured
            assert "Search error" not in captured


def test_lineage_fast_uses_filtered_pickle(fast_cache_dir, capsys):
    from taxdumpy.cli import main

    assert main(["lineage", "-d", str(fast_cache_dir), "--fast", "9606"]) == 0
    assert "Homo sapiens" in capsys.readouterr().out
