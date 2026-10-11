"""Cache file utilities shared by the backends and CLI."""

import os
import pickle
import tempfile
from pathlib import Path

SOURCE_FILES = ("merged.dmp", "delnodes.dmp", "division.dmp", "nodes.dmp", "names.dmp")


def source_signature(directory: Path) -> dict[str, tuple[int, int]]:
    """Cheap freshness metadata; absent sources allow standalone cache use."""
    result = {}
    for name in SOURCE_FILES:
        try:
            stat = (directory / name).stat()
        except FileNotFoundError:
            continue
        result[name] = (stat.st_size, stat.st_mtime_ns)
    return result


def cache_is_stale(path: Path, signature: dict | None = None) -> bool:
    current = source_signature(path.parent)
    if signature is not None:
        return any(signature.get(name) != value for name, value in current.items())
    # Older caches have no source metadata. Preserve compatibility using mtimes.
    cache_mtime = path.stat().st_mtime_ns
    return any(mtime > cache_mtime for size, mtime in current.values())


def atomic_pickle_dump(path: Path, data) -> None:
    """Replace a cache only after serialization succeeds on the same filesystem."""
    fd, name = tempfile.mkstemp(prefix=f"{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            pickle.dump(data, stream, protocol=pickle.HIGHEST_PROTOCOL)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
