"""
Description: NCBI Taxonomy toolkit for parsing database, display taxid, show-lineage, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import re
import pickle

from pathlib   import Path
from functools import cached_property

from rapidfuzz import process, fuzz

from taxdumpy.basic import Node, TaxDbError, TaxidError
from taxdumpy.ansi  import u_str, m_color


class TaxDb:
    """
    Create an object of the TaxDb class.
    """
    def __init__(self, taxdump_dir: Path|str, fast: bool = False) -> None:
        self._taxdump_dir = Path(taxdump_dir).resolve()
        self._fast = fast

        self._taxdbf = [self._taxdump_dir / 'merged.dmp',
                        self._taxdump_dir / 'delnodes.dmp',
                        self._taxdump_dir / 'division.dmp',
                        self._taxdump_dir / 'nodes.dmp',
                        self._taxdump_dir / 'names.dmp'
                        ]
        self._mrgef, self._delnf, self._divsf, self._nodef, self._namef = self._taxdbf
        self._pickle = self._taxdump_dir / ('taxdump_fast.pickle' if fast else 'taxdump.pickle')

        self._taxid2nodes, self._old2news, self._delnodes = self._load_taxdump()

    def _check_taxdump(self):
        if not (self._pickle.is_file() or all([f.is_file() for f in self._taxdbf])):
            raise TaxDbError("required taxdump files are incomplete")

    def __repr__(self):
        return f"Taxdump (Dict) Database from {u_str(self._taxdump_dir)}"

    def __len__(self) -> int:
        return len(self._taxid2nodes)

    def _load_taxdump(self):
        if self._pickle.is_file():
            with open(self._pickle, 'rb') as fin:
                taxid2nodes, old2news, del_taxids = pickle.load(fin)
        else:
            taxid2nodes, old2news, del_taxids = self._import_nodes()

        return taxid2nodes, old2news, del_taxids

    @cached_property
    def all_names(self) -> list[str]:
        return [node.name for node in self._taxid2nodes.values()]

    @cached_property
    def name2taxid(self) -> dict[str, int]:
        return {node.name:taxid for taxid,node in self._taxid2nodes.items()}

    @property
    def delnodes(self) -> set[int]:
        return self._delnodes

    @cached_property
    def max_taxid_strlen(self) -> int:
        return len(str(max(list(self._taxid2nodes.keys()))))

    @cached_property
    def max_rank_strlen(self) -> int:
        return max(set([len(n.rank) for n in self._taxid2nodes.values()]))

    def _import_merged(self) -> dict[int, int]:
        old2new = {}
        with open(self._mrgef, "r") as f:
            for L in f:
                old, new = L.split('\t')[0], L.split('\t')[2]
                old2new[int(old)] = int(new)
        return old2new

    def _import_divcodes(self) -> dict[int, str]:
        div2codes = {}
        with open(self._divsf, 'r') as f:
            for L in f:
                div, code = L.split('\t')[0], L.split('\t')[2]
                div2codes[int(div)] = code
        return div2codes

    def _import_delnodes(self) -> set[int]:
        del_taxids = set()
        with open(self._delnf, 'r') as f:
            for L in f:
                del_taxids.add(int(L.split('\t')[0]))
        return del_taxids

    def _import_names(self) -> tuple[dict, dict, dict]:
        sci_names, eq_names, acr_names = {}, {}, {}
        with open(self._namef, "r") as f:
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

    def _import_nodes(self) -> tuple[dict[int, Node], dict[int, int], set[int]]:
        old2news   = self._import_merged()
        div2codes  = self._import_divcodes()
        del_taxids = self._import_delnodes()
        old_taxids = set(old2news.keys())
        sci_names, eq_names, acr_names = self._import_names()
        taxid2nodes  = {}
        with open(self._nodef, "r") as f:
            for line in f:
                line   = line.split('\t')
                taxid  = int(line[0])
                parent = int(line[2])
                rank   = line[4]
                divid  = int(line[8])

                node   = Node(
                        taxid   = taxid,
                        parent  = old2news[parent] if parent in old_taxids else parent,
                        rank    = rank,
                        name    = sci_names[taxid],
                        equal   = "|".join(eq_names[taxid])  if taxid in eq_names.keys()  else None,
                        acronym = "|".join(acr_names[taxid]) if taxid in acr_names.keys() else None,
                        division=div2codes[divid]
                        )

                taxid2nodes[taxid] = node
        # Finished import all current taxid nodes, extending old_taxids (for compact)
        cur_taxids = set(taxid2nodes.keys())
        assert not old_taxids.intersection(cur_taxids), TaxDbError("current taxids have legacy taxids")

        return taxid2nodes, old2news, del_taxids

    def dump_taxdump(self):
        print(f"Writing to {self._pickle}")
        with open(self._pickle, 'wb') as fout:
            pickle.dump([self._taxid2nodes,
                         self._old2news,
                         self.delnodes], fout, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Taxdump dumped!")

    def get_node(self, taxid: int) -> Node:
        if taxid in self._old2news:
            taxid = self._old2news[taxid]

        if taxid in self.delnodes:
            raise TaxidError(f"{taxid=} is a deleted taxonomy identifier")
        try:
            return self._taxid2nodes[taxid]
        except KeyError:
            raise TaxidError(f"{taxid=} is not a valid taxonomy identifier")

    def fuzzy_search(self, kw: str, limit: int = 10):
        results = process.extract(kw, self.all_names, scorer=fuzz.WRatio, limit=limit)
        for name, _, _ in results:
            tid  = self.name2taxid[name]
            node = self.get_node(tid)
            col  = re.sub(kw, m_color, name, flags=re.IGNORECASE)
            print(f"{tid:<{self.max_taxid_strlen}}\t{node.rank:<{self.max_rank_strlen}}\t{col}")
