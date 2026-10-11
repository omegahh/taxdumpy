"""
Description: NCBI Taxonomy toolkit for parsing database, and build up a SQLite database, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import logging
import os
import sqlite3
import tempfile
from functools import cached_property
from pathlib import Path

from taxdumpy.ansi import u_str
from taxdumpy.basic import DatabaseCorruptionError, Node, TaxdumpFileError, TaxidError
from taxdumpy.cache import CACHE_FORMAT_VERSION, cache_is_stale, source_signature
from taxdumpy.database import TaxonomyDatabase
from taxdumpy.parsers import check_sources, deleted_rows, division_rows, merged_rows, name_rows, node_rows

# Set up logging
logger = logging.getLogger(__name__)


class TaxSQLite(TaxonomyDatabase):
    """
    Create an object of the TaxSQLite class for NCBI taxonomy database operations.

    Args:
        taxdump_dir: Path to directory containing caches built from NCBI taxdump files
        verbose: If True, print status messages during initialization (default: False)
    """

    # Every table the query methods rely on. Checking all of them (rather than
    # just `nodes`) means an incomplete cache is rejected before queries run.
    REQUIRED_TABLES = ("nodes", "names", "merged", "delnodes")

    def __init__(self, taxdump_dir: Path | str, verbose: bool = False):
        self._configure(taxdump_dir, verbose)
        self._open_cached_database()

    def _configure(self, taxdump_dir: Path | str, verbose: bool) -> None:
        """Set up a database reader without creating cache files."""
        super().__init__(taxdump_dir)
        self._verbose = verbose
        self._db_path = self._taxdump_dir / "taxdump.sqlite"

    @classmethod
    def _build_cache(cls, taxdump_dir: Path | str, verbose: bool = False, *, output: Path | None = None) -> None:
        """Build the SQLite cache for the CLI cache command."""
        database = cls.__new__(cls)
        database._configure(taxdump_dir, verbose)
        if output is not None:
            database._db_path = output
        database._create_database()

    def _open_cached_database(self) -> None:
        """Open an existing cache and reject missing, stale, or invalid files."""
        if not self._db_path.exists():
            raise TaxdumpFileError(
                self._db_path.name,
                "Cache not found",
                f"Run 'taxdumpy cache -d {self._taxdump_dir}' before using the Python API",
            )
        try:
            # Open the cache with row access for query methods.
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
            if not self._check_tables() or self._cache_is_stale():
                raise TaxdumpFileError(
                    self._db_path.name,
                    "Cache is missing required tables or is stale",
                    f"Run 'taxdumpy cache -d {self._taxdump_dir}' to rebuild it",
                )
            if self._conn.execute("PRAGMA user_version").fetchone()[0] != CACHE_FORMAT_VERSION:
                raise TaxdumpFileError(
                    self._db_path.name,
                    "Unsupported cache version; rebuild with the current taxdumpy version",
                    f"Run 'taxdumpy cache -d {self._taxdump_dir}' to rebuild it",
                )
        except TaxdumpFileError:
            self.close()
            raise
        except sqlite3.DatabaseError as e:
            self.close()
            raise TaxdumpFileError(
                self._db_path.name,
                f"Cache is unreadable: {e}",
                f"Run 'taxdumpy cache -d {self._taxdump_dir}' to rebuild it",
            ) from e
        except Exception:
            self.close()
            raise

    def _create_database(self):
        """Build the database at a temporary path, then move it into place.

        `executescript` implicitly commits its DDL, so a failure partway
        through the build cannot be rolled back. Building somewhere else and
        renaming on success means an interrupted build never leaves a
        half-populated database that later looks valid but answers nothing.
        """
        # mkstemp guarantees a unique name even when several processes build
        # concurrently, including across hosts sharing the directory, where
        # PIDs can repeat. Same directory, so the final replace stays atomic.
        fd, tmp_name = tempfile.mkstemp(prefix=f"{self._db_path.name}.", suffix=".tmp", dir=self._db_path.parent)
        os.close(fd)
        tmp_path = Path(tmp_name)
        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        try:
            self._build_database(conn)
            conn.close()
            os.replace(tmp_path, self._db_path)
        except BaseException:
            conn.close()
            tmp_path.unlink(missing_ok=True)
            raise

    def close(self):
        """Close the connection and release materialized global query caches."""
        if hasattr(self, "_conn"):
            self._conn.close()
        super().close()

    def _check_tables(self) -> bool:
        rows = self._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        present = {row[0] for row in rows}
        return all(table in present for table in self.REQUIRED_TABLES)

    def _cache_is_stale(self) -> bool:
        metadata = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='source_files'"
        ).fetchone()
        signature = None
        if metadata:
            signature = {name: (size, mtime) for name, size, mtime in self._conn.execute("SELECT * FROM source_files")}
        return cache_is_stale(self._db_path, signature)

    def __repr__(self):
        repr_str = f"Taxdump (SQLite) Database from {u_str(self._taxdump_dir)}\n"
        repr_str += f"\tImported nodes: {len(self):,}\n"
        merged_num = self._conn.execute("SELECT COUNT(*) FROM merged").fetchone()[0]
        repr_str += f"\tLegacy nodes:   {merged_num:,}\n"
        delete_num = self._conn.execute("SELECT COUNT(*) FROM delnodes").fetchone()[0]
        repr_str += f"\tDeleted nodes:  {delete_num:,}"
        return repr_str

    def __len__(self) -> int:
        """Return number of taxonomy nodes in database."""
        return self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    def _build_database(self, conn: sqlite3.Connection):
        check_sources(self._taxdump_dir)
        signature = source_signature(self._taxdump_dir)
        try:
            if self._verbose:
                print("Build up TAXDUMP SQLite Database...")
            c = conn.cursor()
            # 1) Create Tables
            c.executescript(
                """
                    CREATE TABLE nodes (
                        taxid    INTEGER PRIMARY KEY,
                        parent   INTEGER NOT NULL,
                        rank     TEXT    NOT NULL,
                        division TEXT    NOT NULL
                        );
                    CREATE TABLE names (
                        taxid      INTEGER NOT NULL,
                        name       TEXT    NOT NULL,
                        name_class TEXT    NOT NULL,
                        PRIMARY KEY (taxid, name_class, name)
                        );
                    CREATE TABLE merged (
                        oldtid INTEGER PRIMARY KEY,
                        newtid INTEGER NOT NULL
                        );
                    CREATE TABLE delnodes (
                        taxid INTEGER PRIMARY KEY
                        );
                    CREATE TABLE source_files (
                        name TEXT PRIMARY KEY,
                        size INTEGER NOT NULL,
                        mtime_ns INTEGER NOT NULL
                        );
                    """
            )

            old2new = dict(merged_rows(self._taxdump_dir))
            divisions = dict(division_rows(self._taxdump_dir))
            try:
                c.executemany("INSERT INTO nodes VALUES (?,?,?,?)", node_rows(self._taxdump_dir, old2new, divisions))
            except sqlite3.IntegrityError as error:
                raise TaxdumpFileError("nodes.dmp", "Duplicate TaxID in node records") from error
            c.executemany("INSERT OR IGNORE INTO names VALUES (?,?,?)", name_rows(self._taxdump_dir))
            c.executemany("INSERT INTO merged VALUES (?,?)", old2new.items())
            c.executemany("INSERT OR IGNORE INTO delnodes VALUES (?)", ((t,) for t in deleted_rows(self._taxdump_dir)))
            c.executemany("INSERT INTO source_files VALUES (?,?,?)", ((n, *values) for n, values in signature.items()))
            self._validate_integrity(conn)
            # The names primary key already covers taxid and name-class lookups.
            c.execute("CREATE INDEX idx_nodes_parent ON nodes(parent)")
            c.execute(f"PRAGMA user_version = {CACHE_FORMAT_VERSION}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @cached_property
    def _search_names(self) -> dict[int, str]:
        return {
            row["taxid"]: row["name"]
            for row in self._conn.execute(
                "SELECT taxid, name FROM names WHERE name_class='scientific name' ORDER BY taxid"
            )
        }

    @cached_property
    def delnodes(self) -> frozenset[int]:
        return frozenset(row[0] for row in self._conn.execute("SELECT taxid FROM delnodes"))

    @cached_property
    def max_taxid_strlen(self) -> int:
        max_taxid = self._conn.execute("SELECT MAX(taxid) AS max_taxid FROM nodes").fetchone()["max_taxid"]
        return len(str(max_taxid)) if max_taxid is not None else 0

    @cached_property
    def max_rank_strlen(self) -> int:
        row = self._conn.execute("SELECT MAX(LENGTH(rank)) FROM nodes").fetchone()
        return row[0] or 0

    @staticmethod
    def _validate_integrity(conn: sqlite3.Connection) -> None:
        missing = conn.execute("""
            SELECT n.taxid FROM nodes n LEFT JOIN names s
            ON s.taxid=n.taxid AND s.name_class='scientific name'
            GROUP BY n.taxid HAVING COUNT(s.name) != 1 LIMIT 1
        """).fetchone()
        if missing:
            raise TaxdumpFileError("names.dmp", f"Expected one scientific name for TaxID {missing[0]}")
        conflict = conn.execute("""
            SELECT n.taxid FROM nodes n
            WHERE EXISTS (SELECT 1 FROM merged m WHERE m.oldtid=n.taxid)
            OR EXISTS (SELECT 1 FROM delnodes d WHERE d.taxid=n.taxid) LIMIT 1
        """).fetchone()
        if conflict:
            raise TaxdumpFileError(
                "nodes.dmp", f"Database integrity error: Current taxid {conflict[0]} is merged or deleted"
            )

    def iter_parent_pairs(self):
        return (
            (row[0], row[1])
            for row in self._conn.execute("""
            SELECT n.taxid, n.parent FROM nodes n
            WHERE n.taxid != n.parent
            AND NOT EXISTS (SELECT 1 FROM merged m WHERE m.oldtid=n.taxid)
            AND NOT EXISTS (SELECT 1 FROM delnodes d WHERE d.taxid=n.taxid)
        """)
        )

    def children_for(self, parents: list[int]) -> list[int]:
        if "children_index" in self.__dict__:
            return super().children_for(parents)
        # Respect SQLite's variable limit while querying a whole BFS frontier.
        children = {}
        for start in range(0, len(parents), 900):
            batch = parents[start : start + 900]
            marks = ",".join("?" for _ in batch)
            for taxid, parent in self._conn.execute(
                f"""
                SELECT n.taxid, n.parent FROM nodes n WHERE n.parent IN ({marks})
                AND n.taxid != n.parent
                AND NOT EXISTS (SELECT 1 FROM merged m WHERE m.oldtid=n.taxid)
                AND NOT EXISTS (SELECT 1 FROM delnodes d WHERE d.taxid=n.taxid)
                ORDER BY n.taxid
            """,
                batch,
            ):
                children.setdefault(parent, []).append(taxid)
        return [child for parent in parents for child in children.get(parent, ())]

    def _resolve_node(self, taxid: int | str):
        original = self._validate_taxid(taxid)
        row = self._conn.execute(
            """
            SELECT COALESCE(m.newtid, ?) AS resolved, d.taxid AS deleted,
                   n.taxid, n.parent, n.rank, n.division
            FROM (SELECT ? AS taxid) q
            LEFT JOIN merged m ON m.oldtid=q.taxid
            LEFT JOIN delnodes d ON d.taxid=COALESCE(m.newtid,q.taxid)
            LEFT JOIN nodes n ON n.taxid=COALESCE(m.newtid,q.taxid)
        """,
            (original, original),
        ).fetchone()
        if row["deleted"] is not None:
            raise TaxidError(
                original,
                f"TaxID {original} has been deleted from NCBI taxonomy",
                suggestion="Check NCBI taxonomy for updated taxid or use search function",
            )
        if row["taxid"] is None:
            raise TaxidError(
                original,
                f"TaxID {original} is not found in the database",
                suggestion=self._suggest_similar_taxids(row["resolved"]),
            )
        return row

    def _names_for(self, taxid: int) -> dict[str, tuple[str, ...]]:
        names = {}
        for name, name_class in self._conn.execute(
            "SELECT name, name_class FROM names WHERE taxid=? ORDER BY name_class, name", (taxid,)
        ):
            names.setdefault(name_class, []).append(name)
        if len(names.get("scientific name", ())) != 1:
            raise DatabaseCorruptionError("SQLite", f"Expected one scientific name for TaxID {taxid}")
        return {name_class: tuple(values) for name_class, values in names.items()}

    def get_names(self, taxid: int | str) -> dict[str, tuple[str, ...]]:
        """Resolve the ID and fetch all names without constructing a Node."""
        return self._names_for(self._resolve_node(taxid)["taxid"])

    def get_node(self, taxid: int | str) -> Node:
        """Resolve metadata and fetch sorted names in two indexed statements."""
        row = self._resolve_node(taxid)
        names = self._names_for(row["taxid"])
        return Node(
            row["taxid"],
            row["parent"],
            row["rank"],
            names["scientific name"][0],
            "|".join(names.get("equivalent name", ())) or None,
            "|".join(names.get("acronym", ())) or None,
            row["division"],
        )

    def _suggest_similar_taxids(self, taxid: int) -> str:
        """Suggest similar taxids when lookup fails."""
        # Find taxids within a reasonable range using SQL
        similar_taxids = []
        search_range = 1000

        cursor = self._conn.execute(
            "SELECT taxid FROM nodes WHERE taxid BETWEEN ? AND ? ORDER BY taxid LIMIT 3",
            (max(1, taxid - search_range), taxid + search_range),
        )
        similar_taxids = [row["taxid"] for row in cursor.fetchall()]

        if similar_taxids:
            similar_str = ", ".join(map(str, similar_taxids))
            return f"Try nearby taxids: {similar_str}, or use search function to find organisms"
        else:
            return "Use search function to find organisms by name"
