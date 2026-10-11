"""Strict, streaming readers shared by both cache builders."""

from pathlib import Path

from taxdumpy.basic import TaxdumpFileError
from taxdumpy.cache import SOURCE_FILES


def check_sources(directory: Path) -> None:
    missing = [name for name in SOURCE_FILES if not (directory / name).is_file()]
    if missing:
        raise TaxdumpFileError(
            ", ".join(missing), "Files not found", "Download the NCBI taxdump and extract all required files"
        )
    empty = [name for name in ("nodes.dmp", "names.dmp", "division.dmp") if not (directory / name).stat().st_size]
    if empty:
        raise TaxdumpFileError(
            ", ".join(empty), "Files appear to be corrupted or have invalid format", "Re-download NCBI taxdump files"
        )


def _rows(path: Path, columns: int):
    line_number = 0
    try:
        with path.open("rb") as stream:
            for line_number, raw_line in enumerate(stream, 1):
                line = raw_line.decode("utf-8")
                if not line.strip():
                    continue
                # Split on tabs, preserving literal pipes within names.
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) < columns * 2 or any(part != "|" for part in parts[1::2]):
                    raise ValueError("invalid tab/pipe record format")
                yield line_number, [part.strip() for part in parts[::2]]
    except (OSError, UnicodeError, ValueError) as error:
        raise TaxdumpFileError(
            path.name, f"Cannot parse line {line_number}: {error}", "Check file format and UTF-8 encoding"
        ) from error


def _records(directory: Path, filename: str, columns: int, convert):
    path = directory / filename
    for line_number, fields in _rows(path, columns):
        try:
            yield convert(fields)
        except (ValueError, IndexError) as error:
            raise TaxdumpFileError(
                path.name, f"Invalid record at line {line_number}: {error}", "Re-download NCBI taxdump files"
            ) from error


def _taxid(value: str) -> int:
    result = int(value)
    if result < 1:
        raise ValueError("taxids must be positive integers")
    return result


def merged_rows(directory: Path):
    return _records(directory, "merged.dmp", 2, lambda f: (_taxid(f[0]), _taxid(f[1])))


def deleted_rows(directory: Path):
    return _records(directory, "delnodes.dmp", 1, lambda f: _taxid(f[0]))


def division_rows(directory: Path):
    return _records(directory, "division.dmp", 2, lambda f: (int(f[0]), f[1]))


def node_rows(directory: Path, merged: dict[int, int], divisions: dict[int, str]):
    def convert(fields):
        taxid, parent, division = _taxid(fields[0]), _taxid(fields[1]), int(fields[4])
        if not fields[2]:
            raise ValueError("empty rank")
        return taxid, merged.get(parent, parent), fields[2], divisions.get(division, f"UNKNOWN_{division}")

    return _records(directory, "nodes.dmp", 5, convert)


def name_rows(directory: Path):
    def convert(fields):
        if not fields[1] or not fields[3]:
            raise ValueError("empty name or name class")
        return _taxid(fields[0]), fields[1], fields[3]

    return _records(directory, "names.dmp", 4, convert)
