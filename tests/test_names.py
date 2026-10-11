"""Name classes must survive CLI cache builds and agree across backends."""

import pickle
import sqlite3
from contextlib import closing
from unittest.mock import patch

import pytest

from taxdumpy import TaxDb, TaxdumpFileError, TaxidError, Taxon, ValidationError, open_database
from taxdumpy.cache import atomic_pickle_dump
from taxdumpy.cli import main

ALTERNATIVE_NAMES = {
    "synonym": ("Homo sapiens alias", "Homo | sapiens", "homme"),
    "common name": ("human being", "人类"),
    "genbank common name": ("human",),
    "equivalent name": ("H. sapiens", "Homo | sapiens"),
    "acronym": ("HS", "Hs"),
    "authority": ("Homo sapiens Linnaeus, 1758",),
    "blast name": ("primates",),
    "includes": ("included human population",),
    "in-part": ("humans in part",),
    "type material": ("human type material",),
    "new NCBI name class": ("future name",),
}


@pytest.fixture
def names_dir(source_dir):
    # Repeated records and the same text in different classes must be handled
    # independently. A literal pipe is part of a name, not a separator.
    with (source_dir / "names.dmp").open("a", encoding="utf-8") as stream:
        for name_class, values in ALTERNATIVE_NAMES.items():
            for value in reversed(values):
                for _ in range(2):
                    stream.write(f"9606\t|\t{value}\t|\t\t|\t{name_class}\t|\n")
    assert main(["cache", "-d", str(source_dir)]) == 0
    return source_dir


@pytest.mark.parametrize("backend", ["dict", "sqlite"])
def test_all_name_classes_and_multiple_values_survive_cache(names_dir, backend):
    expected = {"scientific name": ("Homo sapiens",), **ALTERNATIVE_NAMES}
    with open_database(names_dir, backend) as db:
        assert db.get_names("9606") == expected
        # Changes to the result must not mutate the cache.
        returned = db.get_names(9606)
        returned["synonym"] = ("changed",)
        returned.clear()
        assert db.get_names(9606) == expected
        assert db.get_node(9606).name == "Homo sapiens"


@pytest.mark.parametrize("backend", ["dict", "sqlite"])
def test_name_properties_load_once_and_keep_classes_separate(names_dir, backend):
    with open_database(names_dir, backend) as db:
        with patch.object(db, "get_names", wraps=db.get_names) as get_names:
            taxon = Taxon(9606, db)
            get_names.assert_not_called()
            assert taxon.synonyms == ALTERNATIVE_NAMES["synonym"]
            assert taxon.common_names == ALTERNATIVE_NAMES["common name"]
            assert taxon.genbank_common_names == ALTERNATIVE_NAMES["genbank common name"]
            assert taxon.equivalent_names == ALTERNATIVE_NAMES["equivalent name"]
            assert taxon.acronyms == ALTERNATIVE_NAMES["acronym"]
            assert taxon.names["authority"] == ALTERNATIVE_NAMES["authority"]
            get_names.assert_called_once_with(9606)
        assert taxon.acronym == "HS|Hs"
        assert taxon.node.equal == "H. sapiens|Homo | sapiens"
    # Once read, the names remain available after closing SQLite.
    assert taxon.common_names == ALTERNATIVE_NAMES["common name"]


@pytest.mark.parametrize("backend", ["dict", "sqlite"])
def test_missing_name_classes_return_empty_tuples(sample_taxdump_dir, backend):
    with open_database(sample_taxdump_dir, backend) as db:
        human = Taxon(9606, db)
        assert human.synonyms == ()
        assert human.common_names == ()
        assert human.equivalent_names == ()
        assert human.acronyms == ()
        assert human.acronym is None
        assert human.genbank_common_names == ("human",)
        assert "common name" not in human.names


@pytest.mark.parametrize("backend", ["dict", "sqlite"])
def test_merged_taxid_uses_current_taxids_names(sample_taxdump_dir, backend):
    with open_database(sample_taxdump_dir, backend) as db:
        expected = db.get_names(6042)
        assert db.get_names(6043) == expected
        taxon = Taxon(6043, db)
        assert taxon.is_legacy
        assert taxon.names == expected
        assert "Ceractinomorpha" in taxon.synonyms


@pytest.mark.parametrize("backend", ["dict", "sqlite"])
@pytest.mark.parametrize(
    "taxid, error", [(True, ValidationError), ("bad", ValidationError), (3451490, TaxidError), (999999999, TaxidError)]
)
def test_name_lookup_preserves_taxid_errors(sample_taxdump_dir, backend, taxid, error):
    with open_database(sample_taxdump_dir, backend) as db:
        with pytest.raises(error):
            db.get_names(taxid)


@pytest.mark.parametrize("backend", ["dict", "sqlite"])
def test_all_names_available_without_source_files(names_dir, backend):
    for path in names_dir.glob("*.dmp"):
        path.unlink()
    with open_database(names_dir, backend) as db:
        assert db.get_names(9606) == {"scientific name": ("Homo sapiens",), **ALTERNATIVE_NAMES}


def test_filtered_pickle_keeps_only_selected_taxids_names(names_dir):
    selection = names_dir / "selected.txt"
    selection.write_text("9606\n")
    assert main(["cache", "-d", str(names_dir), "-f", str(selection)]) == 0
    for path in names_dir.glob("*.dmp"):
        path.unlink()
    with TaxDb(names_dir, fast=True) as db:
        assert db.get_names(9606) == {"scientific name": ("Homo sapiens",), **ALTERNATIVE_NAMES}
        assert "human" in Taxon(9606, db).genbank_common_names
        assert all(set(names) <= set(db._taxid2nodes) for names in db._names_by_class.values())
        with pytest.raises(TaxidError):
            db.get_names(562)


def test_sqlite_old_name_cache_requires_explicit_cli_rebuild(source_dir):
    path = source_dir / "taxdump.sqlite"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("DELETE FROM names WHERE name_class NOT IN ('scientific name', 'equivalent name', 'acronym')")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    before = path.read_bytes()
    with pytest.raises(TaxdumpFileError, match="taxdumpy cache"):
        open_database(source_dir)
    assert path.read_bytes() == before
    assert main(["cache", "-d", str(source_dir)]) == 0
    with open_database(source_dir) as db:
        assert db.get_names(9606)["genbank common name"] == ("human",)


@pytest.mark.parametrize("names", [None, {"synonym": []}])
def test_pickle_with_invalid_name_maps_requires_cli_rebuild(source_dir, names):
    path = source_dir / "taxdump.pickle"
    with path.open("rb") as stream:
        data = pickle.load(stream)
    data["names_by_class"] = names
    atomic_pickle_dump(path, data)
    with pytest.raises(TaxdumpFileError, match="taxdumpy cache"):
        TaxDb(source_dir)


def test_old_filtered_cache_requires_filter_file_to_rebuild(fast_cache_dir):
    path = fast_cache_dir / "taxdump_fast.pickle"
    with path.open("rb") as stream:
        data = pickle.load(stream)
    data["format_version"] = 1
    data.pop("names_by_class")
    atomic_pickle_dump(path, data)
    before = path.read_bytes()
    with pytest.raises(TaxdumpFileError, match="-f FILE"):
        TaxDb(fast_cache_dir, fast=True)
    assert path.read_bytes() == before
