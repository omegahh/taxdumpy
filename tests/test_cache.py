"""Cache replacement must preserve the previous database after a failed build."""

import os
import pickle
from unittest.mock import patch

import pytest

from taxdumpy import TaxDb, TaxSQLite
from taxdumpy.cache import atomic_pickle_dump


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
def test_failed_rebuild_preserves_existing_cache(source_dir, filename):
    before = (source_dir / filename).read_bytes()
    (source_dir / "nodes.dmp").write_text("invalid nodes file")
    from taxdumpy.cli import main

    assert main(["cache", "-d", str(source_dir)]) == 1
    assert (source_dir / filename).read_bytes() == before
    assert not list(source_dir.glob("*.tmp"))


def test_explicit_rebuild_reports_write_failure(source_dir):
    from taxdumpy.cli import main

    with patch("taxdumpy.taxdb.atomic_pickle_dump", side_effect=PermissionError("read only")):
        assert main(["cache", "-d", str(source_dir)]) == 1


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_changed_sources_require_cli_rebuild_even_with_preserved_mtime(source_dir, backend):
    with backend(source_dir) as db:
        assert db.get_node(9606).name == "Homo sapiens"
    names = source_dir / "names.dmp"
    stat = names.stat()
    names.write_text(names.read_text().replace("Homo sapiens", "Updated Homo sapiens"))
    os.utime(names, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    from taxdumpy.cli import main

    with pytest.raises(Exception):
        backend(source_dir)
    assert main(["cache", "-d", str(source_dir)]) == 0
    with backend(source_dir) as db:
        assert db.get_node(9606).name == "Updated Homo sapiens"


@pytest.mark.parametrize("backend", [TaxDb, TaxSQLite])
def test_cache_can_be_used_without_sources(source_dir, backend):
    with backend(source_dir):
        pass
    for path in source_dir.glob("*.dmp"):
        path.unlink()
    with backend(source_dir) as db:
        assert db.get_node(9606).name == "Homo sapiens"


def test_original_pickle_format_remains_readable(source_dir):
    db = TaxDb(source_dir)
    atomic_pickle_dump(source_dir / "legacy.pickle", [db._taxid2nodes, db._old2news, db.delnodes])
    (source_dir / "taxdump.pickle").unlink()
    (source_dir / "legacy.pickle").replace(source_dir / "taxdump.pickle")
    assert TaxDb(source_dir).get_node(9606).name == "Homo sapiens"


def test_stale_fast_cache_requires_explicit_reselection(fast_cache_dir):
    from taxdumpy import TaxdumpFileError

    names = fast_cache_dir / "names.dmp"
    names.write_text(names.read_text().replace("Homo sapiens", "Updated Homo sapiens"))
    with pytest.raises(TaxdumpFileError, match="stale"):
        TaxDb(fast_cache_dir, fast=True)
