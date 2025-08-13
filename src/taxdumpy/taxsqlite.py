"""
Description: NCBI Taxonomy toolkit for parsing database, and build up a SQLite database, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import re
import sqlite3

from pathlib   import Path
from rapidfuzz import process, fuzz
from functools import cached_property

from taxdumpy.ansi  import u_str, m_color
from taxdumpy.basic import Node, TaxidError


class TaxSQLite:
    """
    Create an object of the TaxDb class.
    """
    def __init__(self, taxdump_dir: Path|str):
        self._taxdump_dir = Path(taxdump_dir).resolve()

        self._db_path = self._taxdump_dir / "taxdump.sqlite"

        # open a sqlite connection, and use row_factory for element access, r['name'] for example
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        if not self._check_tables():
            self._build_database()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, '_conn'):
            self._conn.close()

    def close(self):
        """Close SQLite connection"""
        if hasattr(self, '_conn'):
            self._conn.close()

    def _check_tables(self) -> bool:
        c = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' and name='nodes'")
        return c.fetchone() is not None

    def __repr__(self):
        repr_str = f"Taxdump (SQLite) Database from {u_str(self._taxdump_dir)}\n"
        nodes_num = self._conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        repr_str += f"\tImported nodes: {nodes_num:,}\n"
        merged_num = self._conn.execute("SELECT COUNT(*) FROM merged").fetchone()[0]
        repr_str += f"\tLegacy nodes:   {merged_num:,}\n"
        delete_num = len(self.delnodes)
        repr_str += f"\tDeleted nodes:  {delete_num:,}"
        return repr_str

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
            old2new   = self._import_merged()
            div2code  = self._import_divcodes()
            sci_names, eq_names, acr_names = self._import_names()

            # 3) Insert Nodes
            rows_nodes = []
            with open(self._taxdump_dir / "nodes.dmp", 'r') as f:
                for line in f:
                    cols   = line.split('\t')
                    taxid  = int(cols[0])
                    parent = int(cols[2])
                    parent = old2new[parent] if parent in old2new else parent
                    rank   = cols[4]
                    divc   = div2code[int(cols[8])]
                    rows_nodes.append((taxid, parent, rank, divc))
            c.executemany(
                    "INSERT INTO nodes VALUES (?,?,?,?)", rows_nodes
                    )

            # 4) Insert Names
            rows_names = []
            for taxid, nm in sci_names.items():
                rows_names.append((taxid, nm, "scientific"))
            for taxid, lst in eq_names.items():
                for nm in lst:
                    rows_names.append((taxid, nm, "equivalent"))
            for taxid, lst in acr_names.items():
                for nm in lst:
                    rows_names.append((taxid, nm, "acronym"))
            c.executemany(
                    "INSERT INTO names VALUES (?,?,?)",
                    rows_names
                    )

            # 5) Insert Legacy Taxids
            rows_legacy = [(old,new) for old,new in old2new.items()]
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
                    "SELECT name FROM names WHERE name_class='scientific'")
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
        row = self._conn.execute(
                "SELECT MAX(LENGTH(rank)) FROM nodes"
                ).fetchone()
        return row[0]

    def _import_merged(self) -> dict[int,int]:
        old2new = {}
        with open(self._taxdump_dir / "merged.dmp", 'r') as f:
            for line in f:
                parts = line.split('\t')
                old2new[int(parts[0])] = int(parts[2])
        return old2new

    def _import_divcodes(self) -> dict[int,str]:
        div2codes = {}
        with open(self._taxdump_dir / "division.dmp", 'r') as f:
            for L in f:
                div, code = L.split('\t')[0], L.split('\t')[2]
                div2codes[int(div)] = code
        return div2codes

    def _import_delnodes(self) -> set[int]:
        s = set()
        with open(self._taxdump_dir / "delnodes.dmp", 'r') as f:
            for L in f:
                s.add(int(L.split('\t')[0]))
        return s

    def _import_names(self):
        sci_names, eq_names, acr_names = {}, {}, {}
        with open(self._taxdump_dir / "names.dmp", 'r') as f:
            for L in f:
                sp = L.split('\t')
                tid = int(sp[0]); name = sp[2]; clas = sp[6]
                if clas == "scientific name":
                    sci_names[tid] = name
                elif clas == "equivalent name":
                    eq_names.setdefault(tid, []).append(name)
                elif clas == "acronym":
                    acr_names.setdefault(tid, []).append(name)
        return sci_names, eq_names, acr_names

    def get_node(self, taxid: int) -> Node:
        r1 = self._conn.execute(
                "SELECT newtid FROM merged WHERE oldtid=?", (taxid,)
                ).fetchone()
        if r1:
            taxid = r1['newtid']

        r = self._conn.execute(
                "SELECT * FROM nodes WHERE taxid=?", (taxid,)
                ).fetchone()
        if not r:
            if taxid in self.delnodes:
                raise TaxidError(f"{taxid=} is a deleted taxonomy identifier")
            else:
                raise TaxidError(f"{taxid=} is a wrong taxonomy identifier")

        name = self._conn.execute(
                "SELECT name FROM names WHERE taxid=? AND name_class='scientific'", (taxid,)
                ).fetchone()["name"]
        eqv  = self._conn.execute(
                "SELECT group_concat(name,'|') AS a FROM names WHERE taxid=? AND name_class='equivalent'",
                (taxid,)
                ).fetchone()["a"]
        acr  = self._conn.execute(
                "SELECT group_concat(name,'|') AS a FROM names WHERE taxid=? AND name_class='acronym'",
                (taxid,)
                ).fetchone()["a"]
        return Node(
                taxid    = r["taxid"],
                parent   = r["parent"],
                rank     = r["rank"],
                name     = name,
                equal    = eqv,
                acronym  = acr,
                division = r["division"]
                )

    def fuzzy_search(self, kw: str, limit: int = 10):
        results = process.extract(kw, self.all_names, scorer=fuzz.WRatio, limit=limit)
        for name, _, _ in results:
            tid  = self.name2taxid[name]
            node = self.get_node(tid)
            col  = re.sub(kw, m_color, name, flags=re.IGNORECASE)
            print(f"{tid:<{self.max_taxid_strlen}}\t{node.rank:<{self.max_rank_strlen}}\t{col}")
