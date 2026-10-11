"""Behavioural regressions for the whole-codebase review."""

import os
from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from taxdumpy import DatabaseCorruptionError, TaxDb, TaxdumpFileError, Taxon, TaxSQLite, descendants
from taxdumpy.cache import atomic_pickle_dump
from taxdumpy.cli import main
from taxdumpy.functions import build_children_index, get_closest_rank, group_taxids_by_rank


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
@pytest.mark.parametrize(
    "defect", ["missing_name", "multiple_names", "merged_current", "deleted_current", "duplicate_node"]
)
def test_builders_reject_invalid_taxonomy(raw_source_dir, backend, defect):
    if defect == "missing_name":
        path = raw_source_dir / "names.dmp"
        path.write_text(
            "".join(
                line
                for line in path.read_text().splitlines(True)
                if not (line.startswith("9606\t") and "scientific name" in line)
            )
        )
    elif defect == "multiple_names":
        with (raw_source_dir / "names.dmp").open("a") as stream:
            stream.write("9606\t|\tAnother scientific name\t|\t\t|\tscientific name\t|\n")
    elif defect == "merged_current":
        with (raw_source_dir / "merged.dmp").open("a") as stream:
            stream.write("9606\t|\t9605\t|\n")
    elif defect == "deleted_current":
        with (raw_source_dir / "delnodes.dmp").open("a") as stream:
            stream.write("9606\t|\n")
    else:
        path = raw_source_dir / "nodes.dmp"
        line = next(line for line in path.read_text().splitlines(True) if line.startswith("9606\t"))
        with path.open("a") as stream:
            stream.write(line)
    with pytest.raises(TaxdumpFileError, match="Duplicate TaxID" if defect == "duplicate_node" else "9606"):
        backend._build_cache(raw_source_dir)
    assert not list(raw_source_dir.glob("taxdump.*"))


def test_missing_name_rebuild_preserves_both_caches(cached_dir):
    paths = [cached_dir / name for name in ("taxdump.sqlite", "taxdump.pickle")]
    before = [path.read_bytes() for path in paths]
    names = cached_dir / "names.dmp"
    names.write_text(
        "".join(
            line
            for line in names.read_text().splitlines(True)
            if not (line.startswith("9606\t") and "scientific name" in line)
        )
    )
    assert main(["cache", "-d", str(cached_dir)]) == 1
    assert [path.read_bytes() for path in paths] == before


def test_second_build_failure_preserves_both_caches(cached_dir):
    paths = [cached_dir / name for name in ("taxdump.sqlite", "taxdump.pickle")]
    before = [path.read_bytes() for path in paths]
    with patch("taxdumpy.taxdb.atomic_pickle_dump", side_effect=OSError("disk full")):
        assert main(["cache", "-d", str(cached_dir)]) == 1
    assert [path.read_bytes() for path in paths] == before
    assert not list(cached_dir.glob(".taxdumpy-*"))


@pytest.mark.parametrize("existing", [True, False])
@pytest.mark.parametrize("hardlinks", [True, False])
def test_install_failure_rolls_back_first_replacement(cached_dir, existing, hardlinks):
    paths = [cached_dir / name for name in ("taxdump.sqlite", "taxdump.pickle")]
    before = [path.read_bytes() for path in paths]
    if not existing:
        for path in paths:
            path.unlink()
    replace = os.replace

    def fail_second(source, destination):
        if destination == paths[1]:
            raise OSError("replacement failed")
        return replace(source, destination)

    link = os.link
    with (
        patch("taxdumpy.cache.os.replace", side_effect=fail_second),
        patch("taxdumpy.cache.os.link", side_effect=link if hardlinks else OSError("hardlinks unsupported")),
    ):
        assert main(["cache", "-d", str(cached_dir)]) == 1
    if existing:
        assert [path.read_bytes() for path in paths] == before
        with TaxSQLite(cached_dir) as db:
            assert db.get_node(9606).name == "Homo sapiens"
    else:
        assert all(not path.exists() for path in paths)
    assert not list(cached_dir.glob(".taxdumpy-*"))


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_homonyms_and_returned_objects_are_immutable(sample_taxdump_dir, backend):
    with backend(sample_taxdump_dir) as db:
        assert db.name2taxids["Leishmania"] == (5658, 38568)
        with pytest.raises(TypeError):
            db.name2taxids["Leishmania"] = (5658,)
        node = db.get_node(9606)
        with pytest.raises(FrozenInstanceError):
            node.parent = 1
        taxon = Taxon(9606, db)
        with pytest.raises(TypeError):
            taxon.lineage[0] = db.get_node(1)
        with pytest.raises(TypeError):
            taxon.names["scientific name"] = ("other",)
        assert taxon.name == "Homo sapiens"
        assert db.get_names(9606)["scientific name"] == ("Homo sapiens",)
        index = build_children_index(db)
        with pytest.raises(TypeError):
            index[9605] = ()
        names = db.all_names
        names.clear()
        assert "Homo sapiens" in db.all_names


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_close_releases_global_indexes(sample_taxdump_dir, backend):
    db = backend(sample_taxdump_dir)
    taxon = Taxon(9606, db)  # retains the database after close
    build_children_index(db)
    db.name2taxids
    db.delnodes
    db.close()
    assert taxon.name == "Homo sapiens"
    assert not {"children_index", "_search_names", "name2taxids", "delnodes"}.intersection(db.__dict__)


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_missing_family_groups_by_order_not_clade(raw_source_dir, backend):
    path = raw_source_dir / "nodes.dmp"
    path.write_text(path.read_text().replace("\tfamily\t", "\tclade\t").replace("\tsubfamily\t", "\tclade\t"))
    assert main(["cache", "-d", str(raw_source_dir)]) == 0
    with backend(raw_source_dir) as db:
        assert get_closest_rank(Taxon(9606, db), "family") == (9443, "order")
        assert group_taxids_by_rank([9606], "family", db) == {9443: [9606]}


def test_sqlite_queries_are_bounded_and_subtree_uses_index(sample_taxsqlite):
    db = sample_taxsqlite
    queries = []
    db._conn.set_trace_callback(queries.append)
    assert db.get_node(9606).name == "Homo sapiens"
    assert len(queries) <= 2
    queries.clear()
    assert db.get_names(6043) == db.get_names(6042)
    assert len(queries) <= 4
    queries.clear()
    assert descendants(db, 9606, max_depth=1) == []
    assert len(queries) <= 3
    assert "children_index" not in db.__dict__
    assert "delnodes" not in db.__dict__
    plan = db._conn.execute("EXPLAIN QUERY PLAN SELECT taxid FROM nodes WHERE parent=?", (9606,)).fetchall()
    assert any("idx_nodes_parent" in row[3] for row in plan)
    indexes = {row[1] for row in db._conn.execute("PRAGMA index_list(names)")}
    assert indexes == {"sqlite_autoindex_names_1"}
    db._conn.set_trace_callback(None)


def test_sqlite_detects_corrupt_names(cached_dir):
    with TaxSQLite(cached_dir) as db:
        db._conn.execute("DELETE FROM names WHERE taxid=9606 AND name_class='scientific name'")
        with pytest.raises(DatabaseCorruptionError, match="scientific name"):
            db.get_node(9606)


@pytest.mark.parametrize("existing", [True, False])
def test_filtered_build_leaves_full_caches_untouched(cached_dir, existing):
    paths = [cached_dir / name for name in ("taxdump.sqlite", "taxdump.pickle")]
    before = [path.read_bytes() for path in paths]
    if not existing:
        for path in paths:
            path.unlink()
    selection = cached_dir / "selected.txt"
    for taxid, status in [(999999999, 1), (9606, 0)]:
        selection.write_text(f"{taxid}\n")
        assert main(["cache", "-d", str(cached_dir), "-f", str(selection)]) == status
        if existing:
            assert [path.read_bytes() for path in paths] == before
        else:
            assert all(not path.exists() for path in paths)


def test_filtered_build_reuses_fresh_full_cache(cached_dir):
    selection = cached_dir / "selected.txt"
    selection.write_text("9606\n")
    with patch.object(TaxDb, "_import_database", side_effect=AssertionError("should reuse cache")):
        assert main(["cache", "-d", str(cached_dir), "-f", str(selection)]) == 0


@pytest.mark.parametrize("filtered", [False, True])
def test_source_changes_during_build_preserve_existing_caches(cached_dir, filtered, capsys):
    selection = cached_dir / "selected.txt"
    selection.write_text("9606\n")
    args = ["cache", "-d", str(cached_dir)]
    if filtered:
        args.extend(["-f", str(selection)])
        assert main(args) == 0
    paths = [cached_dir / name for name in ("taxdump.sqlite", "taxdump.pickle", "taxdump_fast.pickle")]
    before = {path: path.read_bytes() for path in paths if path.exists()}

    def change_sources(path, data):
        atomic_pickle_dump(path, data)
        names = cached_dir / "names.dmp"
        names.write_bytes(names.read_bytes() + b"\n")

    with patch("taxdumpy.taxdb.atomic_pickle_dump", side_effect=change_sources):
        assert main(args) == 1
    assert "Sources changed" in capsys.readouterr().err
    assert {path: path.read_bytes() for path in paths if path.exists()} == before
    assert not list(cached_dir.glob(".taxdumpy-*"))


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_invalid_utf8_reports_the_actual_line(raw_source_dir, backend):
    names = raw_source_dir / "names.dmp"
    names.write_bytes(names.read_bytes().splitlines(True)[0] + b"\xff\n")
    with pytest.raises(TaxdumpFileError, match="line 2") as error:
        backend._build_cache(raw_source_dir)
    assert "names.dmp" in str(error.value)


def test_sqlite_wide_frontiers_and_explicit_index(raw_source_dir):
    parents = list(range(3, 1004))
    leaves = [taxid + 2000 for taxid in parents]
    pairs = [(1, 1), (2, 1), *((taxid, 2) for taxid in parents), *zip(leaves, parents)]
    (raw_source_dir / "nodes.dmp").write_text(
        "".join(f"{taxid}\t|\t{parent}\t|\tspecies\t|\t\t|\t0\t|\n" for taxid, parent in pairs)
    )
    (raw_source_dir / "names.dmp").write_text(
        "".join(f"{taxid}\t|\tNode {taxid}\t|\t\t|\tscientific name\t|\n" for taxid, _ in pairs)
    )
    for name in ("merged.dmp", "delnodes.dmp"):
        (raw_source_dir / name).write_text("")
    assert main(["cache", "-d", str(raw_source_dir)]) == 0
    with TaxSQLite(raw_source_dir) as db:
        queries = []
        db._conn.set_trace_callback(queries.append)
        assert descendants(db, 2, max_depth=2) == parents + leaves
        child_queries = [query for query in queries if "n.parent IN" in query]
        assert len(child_queries) == 3  # The 1001-parent frontier is split into two queries.
        assert "children_index" not in db.__dict__
        db._conn.set_trace_callback(None)
        build_children_index(db)
        queries.clear()
        db._conn.set_trace_callback(queries.append)
        assert descendants(db, 2, max_depth=2) == parents + leaves
        assert len(queries) == 2  # Resolve the root; all children come from the explicit index.
        db._conn.set_trace_callback(None)
