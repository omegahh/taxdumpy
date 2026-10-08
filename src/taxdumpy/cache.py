"""Cache file utilities shared by the backends and CLI."""

import os
import pickle
import tempfile
from pathlib import Path


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
