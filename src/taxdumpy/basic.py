from dataclasses import dataclass
from typing import Any

from taxdumpy.ranks import RANKCODE_ORDER as _RANKCODE_ORDER

_RANKCODE_TO_LEVEL = {code: i for i, code in enumerate(_RANKCODE_ORDER)}


class RC(int):
    """
    A comparable rank code as an int subclass using bit manipulation.

    Encoding: (base_level << 8) | depth (16-bit: high 8 for base, low 8 for depth)
    Lower value = higher rank: R(0) < R1(1) < D(256) < ... < S(2048) < S1(2049)

    Usage:
        >>> RC("S1")
        RC('S1')
        >>> int(RC("S1"))
        2049
        >>> str(RC("S1"))
        'S1'
        >>> RC("R") < RC("S")
        True
        >>> RC(2049)
        RC('S1')
        >>> sorted([RC("S"), RC("G"), RC("R")])
        [RC('R'), RC('G'), RC('S')]
    """

    __slots__ = ()

    def __new__(cls, code: str | int):
        if isinstance(code, int):
            value = code
        elif isinstance(code, str) and code and code[0] in _RANKCODE_TO_LEVEL:
            base_level = _RANKCODE_TO_LEVEL[code[0]]
            suffix = code[1:]
            if suffix and (not suffix.isdigit() or int(suffix) > 255):
                raise ValueError(f"Invalid rank code: {code!r}")
            depth = int(suffix) if suffix else 0
            value = (base_level << 8) | depth
        else:
            raise ValueError(f"Invalid rank code: {code!r}")
        if value < 0 or value >> 8 >= len(_RANKCODE_ORDER):
            raise ValueError(f"Invalid rank code value: {code!r}")
        return super().__new__(cls, value)

    def __str__(self) -> str:
        base = _RANKCODE_ORDER[self >> 8]
        depth = self & 0xFF
        return base if depth == 0 else f"{base}{depth}"

    def __repr__(self) -> str:
        return f"RC({str(self)!r})"


@dataclass(frozen=True, slots=True)
class Node:
    """Immutable taxonomy record shared safely by readers and derived caches."""

    taxid: int
    parent: int
    rank: str
    name: str
    equal: str | None
    acronym: str | None
    division: str


class TaxdumpyError(Exception):
    """Base exception class for all taxdumpy errors."""

    pass


class TaxDbError(TaxdumpyError):
    """Raised when there are issues with the taxonomy database."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with optional details."""
        if self.details:
            return f"{self.message}\nDetails: {self.details}"
        return self.message


class TaxidError(TaxdumpyError):
    """Raised when taxid-related operations fail."""

    def __init__(
        self,
        taxid: int | str,
        message: str | None = None,
        suggestion: str | None = None,
    ):
        self.taxid = taxid
        self.suggestion = suggestion

        if message is None:
            message = f"Invalid or unknown taxid: {taxid}"

        self.message = message
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with suggestions."""
        msg = self.message
        if self.suggestion:
            msg += f"\nSuggestion: {self.suggestion}"
        return msg


class TaxRankError(TaxdumpyError):
    """Raised when taxonomic rank operations fail."""

    def __init__(self, rank: str, message: str | None = None, valid_ranks: list | None = None):
        self.rank = rank
        self.valid_ranks = valid_ranks or []

        if message is None:
            message = f"Invalid taxonomic rank: '{rank}'"

        self.message = message
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format the error message with valid ranks."""
        msg = self.message
        if self.valid_ranks:
            valid_str = ", ".join(self.valid_ranks)
            msg += f"\nValid ranks: {valid_str}"
        return msg


class TaxdumpFileError(TaxDbError):
    """Raised when there are issues with taxdump files."""

    def __init__(self, filename: str, issue: str, solution: str | None = None):
        self.filename = filename
        self.issue = issue
        self.solution = solution

        message = f"Problem with taxdump file '{filename}': {issue}"
        super().__init__(message, solution)


class DatabaseCorruptionError(TaxDbError):
    """Raised when database corruption is detected."""

    def __init__(self, database_type: str, corruption_details: str):
        self.database_type = database_type
        self.corruption_details = corruption_details

        message = f"{database_type} database appears to be corrupted"
        solution = "Try rebuilding the database from original taxdump files"
        super().__init__(message, f"{corruption_details}\nSolution: {solution}")


class ValidationError(TaxdumpyError):
    """Raised when input validation fails."""

    def __init__(self, parameter: str, value: Any, expected: str):
        self.parameter = parameter
        self.value = value
        self.expected = expected

        message = f"Invalid value for '{parameter}': {value} (expected: {expected})"
        super().__init__(message)
