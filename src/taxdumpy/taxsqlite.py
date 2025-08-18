"""
Description: NCBI Taxonomy toolkit for parsing database, and build up a SQLite database, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import re
import sqlite3

from pathlib import Path
from rapidfuzz import process, fuzz
from functools import cached_property
from typing import Union, List, Dict

from taxdumpy.ansi import u_str, m_color
from taxdumpy.basic import Node, TaxidError, ValidationError
from taxdumpy.database import TaxonomyDatabase


class TaxSQLite(TaxonomyDatabase):
    """
    Create an object of the TaxDb class.
    """

    def __init__(self, taxdump_dir: Path | str):
        # Call parent constructor
        super().__init__(taxdump_dir)

        self._db_path = self._taxdump_dir / "taxdump.sqlite"

        # open a sqlite connection, and use row_factory for element access, r['name'] for example
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        if not self._check_tables():
            self._build_database()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, "_conn"):
            self._conn.close()

    def close(self):
        """Close SQLite connection"""
        if hasattr(self, "_conn"):
            self._conn.close()

    def _check_tables(self) -> bool:
        c = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' and name='nodes'"
        )
        return c.fetchone() is not None

    def __repr__(self):
        repr_str = f"Taxdump (SQLite) Database from {u_str(self._taxdump_dir)}\n"
        repr_str += f"\tImported nodes: {len(self):,}\n"
        merged_num = self._conn.execute("SELECT COUNT(*) FROM merged").fetchone()[0]
        repr_str += f"\tLegacy nodes:   {merged_num:,}\n"
        delete_num = len(self.delnodes)
        repr_str += f"\tDeleted nodes:  {delete_num:,}"
        return repr_str

    def __len__(self) -> int:
        """Return number of taxonomy nodes in database."""
        return self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]

    def _build_database(self):
        try:
            print("Build up TAXDUMP SQLite Database...")
            c = self._conn.cursor()
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
                    CREATE INDEX idx_names_name        ON names(name);
                    CREATE INDEX idx_names_taxid       ON names(taxid);
                    CREATE INDEX idx_names_taxid_class ON names(taxid, name_class);
                    CREATE INDEX idx_nodes_parent ON nodes(parent);
                    """
            )

            # 2) Parsing merged.dmp, division.dmp, delnodes.dmp, names.dmp
            old2new = self._import_merged()
            div2code = self._import_divcodes()
            sci_names, eq_names, acr_names = self._import_names()

            # 3) Insert Nodes
            rows_nodes = []
            with open(self._taxdump_dir / "nodes.dmp", "r") as f:
                for line in f:
                    cols = line.split("\t")
                    taxid = int(cols[0])
                    parent = int(cols[2])
                    parent = old2new[parent] if parent in old2new else parent
                    rank = cols[4]
                    div_id = int(cols[8])
                    divc = div2code.get(div_id, f"UNKNOWN_{div_id}")
                    rows_nodes.append((taxid, parent, rank, divc))
            c.executemany("INSERT INTO nodes VALUES (?,?,?,?)", rows_nodes)

            # 4) Insert Names
            rows_names = []
            for taxid, nm in sci_names.items():
                rows_names.append((taxid, nm, "scientific name"))
            for taxid, lst in eq_names.items():
                for nm in lst:
                    rows_names.append((taxid, nm, "equivalent name"))
            for taxid, lst in acr_names.items():
                for nm in lst:
                    rows_names.append((taxid, nm, "acronym"))
            c.executemany("INSERT INTO names VALUES (?,?,?)", rows_names)

            # 5) Insert Legacy Taxids
            rows_legacy = [(old, new) for old, new in old2new.items()]
            c.executemany("INSERT INTO merged VALUES (?,?)", rows_legacy)
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    @cached_property
    def all_names(self) -> list[str]:
        # Loading all scientific names
        all_names = [
            row["name"]
            for row in self._conn.execute(
                "SELECT name FROM names WHERE name_class='scientific'"
            )
        ]
        return all_names

    @cached_property
    def name2taxid(self) -> dict[str, int]:
        # create name->taxid map
        name2taxid = {
            row["name"]: row["taxid"]
            for row in self._conn.execute(
                "SELECT taxid,name FROM names WHERE name_class='scientific'"
            )
        }
        return name2taxid

    @cached_property
    def delnodes(self) -> set[int]:
        return self._import_delnodes()

    @cached_property
    def max_taxid_strlen(self) -> int:
        max_taxid = self._conn.execute(
            "SELECT MAX(taxid) AS max_taxid FROM nodes"
        ).fetchone()["max_taxid"]
        return len(str(max_taxid))

    @cached_property
    def max_rank_strlen(self) -> int:
        row = self._conn.execute("SELECT MAX(LENGTH(rank)) FROM nodes").fetchone()
        return row[0]

    def _import_merged(self) -> dict[int, int]:
        old2new = {}
        with open(self._taxdump_dir / "merged.dmp", "r") as f:
            for line in f:
                parts = line.split("\t")
                old2new[int(parts[0])] = int(parts[2])
        return old2new

    def _import_divcodes(self) -> dict[int, str]:
        div2codes = {}
        with open(self._taxdump_dir / "division.dmp", "r") as f:
            for L in f:
                div, code = L.split("\t")[0], L.split("\t")[2]
                div2codes[int(div)] = code
        return div2codes

    def _import_delnodes(self) -> set[int]:
        s = set()
        with open(self._taxdump_dir / "delnodes.dmp", "r") as f:
            for L in f:
                s.add(int(L.split("\t")[0]))
        return s

    def _import_names(self):
        sci_names, eq_names, acr_names = {}, {}, {}
        with open(self._taxdump_dir / "names.dmp", "r") as f:
            for L in f:
                sp = L.split("\t")
                tid = int(sp[0])
                name = sp[2]
                clas = sp[6]
                if clas == "scientific name":
                    sci_names[tid] = name
                elif clas == "equivalent name":
                    eq_names.setdefault(tid, []).append(name)
                elif clas == "acronym":
                    acr_names.setdefault(tid, []).append(name)
        return sci_names, eq_names, acr_names

    def get_node(self, taxid: Union[int, str]) -> Node:
        """
        Get a taxonomy node by taxid.

        Args:
            taxid: NCBI taxonomy ID (integer or string)

        Returns:
            Node object containing taxonomy information

        Raises:
            ValidationError: If taxid is invalid format
            TaxidError: If taxid is deleted, not found, or suggests alternatives
        """
        # Validate and convert taxid using the same validation as TaxDb
        validated_taxid = self._validate_taxid(taxid)
        original_taxid = validated_taxid

        # Handle legacy/merged taxids
        r1 = self._conn.execute(
            "SELECT newtid FROM merged WHERE oldtid=?", (validated_taxid,)
        ).fetchone()
        if r1:
            validated_taxid = r1["newtid"]

        # Check if taxid has been deleted
        if validated_taxid in self.delnodes:
            raise TaxidError(
                original_taxid,
                f"TaxID {original_taxid} has been deleted from NCBI taxonomy",
                suggestion="Check NCBI taxonomy for updated taxid or use search function",
            )

        r = self._conn.execute(
            "SELECT * FROM nodes WHERE taxid=?", (validated_taxid,)
        ).fetchone()
        if not r:
            # Try to find similar taxids for suggestions
            suggestion = self._suggest_similar_taxids(validated_taxid)
            raise TaxidError(
                original_taxid,
                f"TaxID {original_taxid} is not found in the database",
                suggestion=suggestion,
            )

        name_result = self._conn.execute(
            "SELECT name FROM names WHERE taxid=? AND name_class='scientific name'",
            (validated_taxid,),
        ).fetchone()
        if not name_result:
            raise TaxidError(
                original_taxid,
                f"Scientific name not found for TaxID {original_taxid}",
                suggestion="Check if taxid exists in database",
            )
        name = name_result["name"]
        eqv = self._conn.execute(
            "SELECT group_concat(name,'|') AS a FROM names WHERE taxid=? AND name_class='equivalent name'",
            (validated_taxid,),
        ).fetchone()["a"]
        acr = self._conn.execute(
            "SELECT group_concat(name,'|') AS a FROM names WHERE taxid=? AND name_class='acronym'",
            (validated_taxid,),
        ).fetchone()["a"]
        return Node(
            taxid=r["taxid"],
            parent=r["parent"],
            rank=r["rank"],
            name=name,
            equal=eqv,
            acronym=acr,
            division=r["division"],
        )

    @staticmethod
    def _validate_taxid(taxid: Union[int, str]) -> int:
        """Validate and convert taxid to integer."""
        if taxid is None:
            raise ValidationError("taxid", taxid, "non-None value")

        # Convert string to int if possible
        if isinstance(taxid, str):
            if not taxid.strip():
                raise ValidationError("taxid", taxid, "non-empty string")
            try:
                taxid = int(taxid.strip())
            except ValueError:
                raise ValidationError("taxid", taxid, "integer or numeric string")

        if not isinstance(taxid, int):
            raise ValidationError("taxid", type(taxid).__name__, "integer")

        if taxid < 1:
            raise ValidationError("taxid", taxid, "positive integer")

        return taxid

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

    def _rapid_fuzz(
        self, query: str, limit: int = 10
    ) -> List[Dict[str, Union[str, int]]]:
        """
        Perform fuzzy search on organism names.

        Args:
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of dictionaries with 'name', 'taxid', and 'score' keys

        Raises:
            ValidationError: If query or limit are invalid
        """
        # Validate inputs (same validation as TaxDb)
        if not isinstance(query, str):
            raise ValidationError("query", type(query).__name__, "string")

        if not query.strip():
            return []

        if not isinstance(limit, int) or limit < 1:
            raise ValidationError("limit", limit, "positive integer")

        if limit > 1000:
            limit = 1000

        try:
            # Perform fuzzy search
            results = process.extract(
                query.strip(), self.all_names, scorer=fuzz.WRatio, limit=limit
            )

            # Format results
            formatted_results = []
            for name, score, _ in results:
                try:
                    taxid = self.name2taxid[name]
                    formatted_results.append(
                        {"name": name, "taxid": taxid, "score": score}
                    )
                except KeyError:
                    continue

            return formatted_results

        except Exception as e:
            from taxdumpy.basic import TaxDbError

            raise TaxDbError(f"Fuzzy search failed: {str(e)}")

    def fuzzy_search(self, query: str, limit: int = 10) -> None:
        """
        Print fuzzy search results to console.

        Args:
            query: Search query string
            limit: Maximum number of results to display
        """
        try:
            results = self._rapid_fuzz(query, limit)

            if not results:
                print(f"No results found for '{query}'")
                return

            for result in results:
                tid = result["taxid"]
                name = str(result["name"])
                try:
                    node = self.get_node(tid)
                    # Highlight matching text
                    col = re.sub(query, m_color, name, flags=re.IGNORECASE)
                    print(
                        f"{tid:<{self.max_taxid_strlen}}\t{node.rank:<{self.max_rank_strlen}}\t{col}"
                    )
                except Exception:
                    # Skip problematic results silently to maintain consistency with TaxDb
                    continue

        except Exception as e:
            print(f"Search error: {e}")
