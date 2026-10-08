"""Cache replacement must preserve the previous database after a failed build."""

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


@pytest.mark.parametrize("backend,filename", [(TaxDb, "taxdump.pickle"), (TaxSQLite, "taxdump.sqlite")])
def test_failed_rebuild_preserves_existing_cache(source_dir, backend, filename):
    with backend(source_dir):
        pass
    before = (source_dir / filename).read_bytes()
    (source_dir / "nodes.dmp").write_text("invalid nodes file")
    with pytest.raises(Exception):
        backend(source_dir, rebuild=True)
    assert (source_dir / filename).read_bytes() == before
    assert not list(source_dir.glob("*.tmp"))


def test_explicit_rebuild_reports_write_failure(source_dir):
    with patch("taxdumpy.taxdb.atomic_pickle_dump", side_effect=PermissionError("read only")):
        with pytest.raises(PermissionError):
            TaxDb(source_dir, rebuild=True)
