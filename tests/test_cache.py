"""Cache replacement must preserve the previous database after a failed build."""

import os
import pickle
import stat
from unittest.mock import patch

import pytest

from taxdumpy import TaxDb, TaxdumpFileError, TaxSQLite
from taxdumpy.cache import atomic_pickle_dump


@pytest.mark.parametrize("filename", ["taxdump.pickle", "taxdump.sqlite"])
def test_cache_files_default_to_world_readable(cached_dir, filename):
    assert stat.S_IMODE((cached_dir / filename).stat().st_mode) == 0o644


def test_fast_cache_defaults_to_world_readable(fast_cache_dir):
    assert stat.S_IMODE((fast_cache_dir / "taxdump_fast.pickle").stat().st_mode) == 0o644


def test_interrupted_pickle_write_preserves_previous_cache(tmp_path):
    path = tmp_path / "taxdump.pickle"
    atomic_pickle_dump(path, [1, 2, 3])
    before = path.read_bytes()

    def fail(data, stream, **kwargs):
        stream.write(b"partial pickle")
        raise KeyboardInterrupt

    with patch("taxdumpy.cache.pickle.dump", side_effect=fail):
        with pytest.raises(KeyboardInterrupt):
            atomic_pickle_dump(path, [4, 5, 6])
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
    assert pickle.loads(before) == [1, 2, 3]


@pytest.mark.parametrize("filename", ["taxdump.pickle", "taxdump.sqlite"])
def test_failed_rebuild_preserves_existing_cache(cached_dir, filename):
    before = (cached_dir / filename).read_bytes()
    (cached_dir / "nodes.dmp").write_text("invalid nodes file")
    from taxdumpy.cli import main

    assert main(["cache", "-d", str(cached_dir)]) == 1
    assert (cached_dir / filename).read_bytes() == before
    assert not list(cached_dir.glob("*.tmp"))


def test_explicit_rebuild_reports_write_failure(cached_dir):
    from taxdumpy.cli import main

    with patch("taxdumpy.taxdb.atomic_pickle_dump", side_effect=PermissionError("read only")):
        assert main(["cache", "-d", str(cached_dir)]) == 1


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_changed_sources_require_cli_rebuild_even_with_preserved_mtime(cached_dir, backend):
    with backend(cached_dir) as db:
        assert db.get_node(9606).name == "Homo sapiens"
    names = cached_dir / "names.dmp"
    stat = names.stat()
    names.write_text(names.read_text().replace("Homo sapiens", "Updated Homo sapiens"))
    os.utime(names, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    from taxdumpy.cli import main

    with pytest.raises(TaxdumpFileError, match="stale"):
        backend(cached_dir)
    assert main(["cache", "-d", str(cached_dir)]) == 0
    with backend(cached_dir) as db:
        assert db.get_node(9606).name == "Updated Homo sapiens"


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_cache_can_be_used_without_sources(cached_dir, backend):
    with backend(cached_dir):
        pass
    for path in cached_dir.glob("*.dmp"):
        path.unlink()
    with backend(cached_dir) as db:
        assert db.get_node(9606).name == "Homo sapiens"


@pytest.mark.parametrize("version", [None, 1, 2])
def test_old_pickle_requires_cli_rebuild_for_all_names(cached_dir, version):
    db = TaxDb(cached_dir)
    data = [db._taxid2nodes, db._old2news, db.delnodes]
    if version is not None:
        data = {
            "format_version": version,
            "sources": db._source_signature,
            "nodes": db._taxid2nodes,
            "merged": db._old2news,
            "deleted": db.delnodes,
        }
    path = cached_dir / "taxdump.pickle"
    atomic_pickle_dump(path, data)
    before = path.read_bytes()
    with pytest.raises(TaxdumpFileError, match="taxdumpy cache"):
        TaxDb(cached_dir)
    assert path.read_bytes() == before
    from taxdumpy.cli import main

    assert main(["cache", "-d", str(cached_dir)]) == 0
    assert TaxDb(cached_dir).get_node(9606).name == "Homo sapiens"
    assert TaxDb(cached_dir).get_names(9606)["genbank common name"] == ("human",)


def test_stale_fast_cache_requires_explicit_reselection(fast_cache_dir):
    from taxdumpy import TaxdumpFileError

    names = fast_cache_dir / "names.dmp"
    names.write_text(names.read_text().replace("Homo sapiens", "Updated Homo sapiens"))
    with pytest.raises(TaxdumpFileError, match="stale.*") as error:
        TaxDb(fast_cache_dir, fast=True)
    assert "-f FILE" in str(error.value)
