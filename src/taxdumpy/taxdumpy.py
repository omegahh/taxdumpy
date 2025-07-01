"""
Description: NCBI Taxonomy toolkit for parsing database, display taxid, show-lineage, etc,.
Author: Hao Hong (omeganju@gmail.com)
Created: 2025-06-30 19:51:00
"""

import re
import pickle

from pathlib import Path
from dataclasses import dataclass
from rapidfuzz import process, fuzz
from functools import cached_property

from typing import Dict, Set, Tuple, List

from taxdumpy.ansi import m_color

class TaxidError(Exception):
    pass

class TaxidRankError(Exception):
    pass

class TaxidRuntimeError(Exception):
    pass

class LCAError(Exception):
    pass

class TaxdumpError(Exception):
    pass

@dataclass
class Node:
    taxid: int
    parent: int
    rank: str
    name: str
    equal: str|None
    acronym: str|None
    legacy: bool
    division: str


class TaxDb:
    """
    Create an object of the TaxDb class.
    """
    def __init__(self, taxdb_path: Path|str, fast: bool = False) -> None:
        self._taxdb_path = Path(taxdb_path).resolve()
        self._fast = fast

        self._taxdbf = [self._taxdb_path / 'merged.dmp',
                        self._taxdb_path / 'delnodes.dmp',
                        self._taxdb_path / 'division.dmp',
                        self._taxdb_path / 'nodes.dmp',
                        self._taxdb_path / 'names.dmp'
                        ]
        self._mrgef, self._delnf, self._divsf, self._nodef, self._namef = self._taxdbf
        self._pickle = self._taxdb_path / ('taxdb_fast.pickle' if fast else 'taxdb.pickle')

        assert self._check_taxdump(), TaxdumpError("required taxdump files are incomplete")

        self._taxid2nodes, self._delnodes = self._load_taxdump()

    @property
    def taxid2nodes(self) -> Dict[int, Node]:
        return self._taxid2nodes

    @property
    def delnodes(self) -> Set[int]:
        return self._delnodes

    @cached_property
    def _max_taxid_strlen(self) -> int:
        return len(str(max(list(self.taxid2nodes.keys()))))

    @cached_property
    def _max_rank_strlen(self) -> int:
        return max(set([len(n.rank) for n in self.taxid2nodes.values()]))

    @cached_property
    def _allnames(self) -> List[str]:
        return [node.name for node in self.taxid2nodes.values()]

    @cached_property
    def _name2taxid(self) -> Dict[str, int]:
        return {node.name: taxid for taxid,node in self.taxid2nodes.items()}

    def __len__(self) -> int:
        return len(self.taxid2nodes)

    def _check_taxdump(self) -> bool:
        return (self._pickle.is_file() or all([f.is_file() for f in self._taxdbf]))

    def _import_merged(self) -> Dict[int, int]:
        old2newtaxid = {}
        with open(self._mrgef, "r") as f:
            for line in f:
                line = line.split("\t")
                taxid = int(line[0])
                merged = int(line[2])
                old2newtaxid[taxid] = merged
        return old2newtaxid

    def _import_divcodes(self) -> Dict[int, str]:
        div2codes = {}
        with open(self._divsf, 'r') as f:
            for line in f:
                line = line.split('\t')
                div  = int(line[0])
                code = line[2]
                div2codes[div] = code
        return div2codes

    def _import_delnodes(self) -> Set[int]:
        del_taxids = set([])
        with open(self._delnf, 'r') as f:
            for line in f:
                line = line.strip().split('\t')
                taxid = int(line[0])
                del_taxids.add(taxid)
        return del_taxids

    def _import_names(self) -> Tuple[Dict, Dict, Dict]:
        taxid2name  = {}
        taxid2equals = {}
        taxid2acronyms = {}
        with open(self._namef, "r") as f:
            for line in f:
                line = line.split("\t")
                taxid = int(line[0])
                name = line[2]
                if line[6] == "scientific name":
                    taxid2name[taxid] = name
                if line[6] == "equivalent name":
                    if taxid in taxid2equals:
                        taxid2equals[taxid].append(name)
                    else:
                        taxid2equals[taxid] = [name]
                if line[6] == "acronym":
                    if taxid in taxid2acronyms:
                        taxid2acronyms[taxid].append(name)
                    else:
                        taxid2acronyms[taxid] = [name]
        taxid2equal = {k: "|".join(v) for k,v in taxid2equals.items()}
        taxid2acronym = {k: "|".join(v) for k,v in taxid2acronyms.items()}
        return taxid2name, taxid2equal, taxid2acronym

    def _import_nodes(self) -> Tuple[Dict[int, Node], Set[int]]:
        old2news   = self._import_merged()
        div2codes  = self._import_divcodes()
        del_taxids = self._import_delnodes()
        old_taxids = set(old2news.keys())
        taxid2name, taxid2equal, taxid2acronym = self._import_names()
        taxid2nodes  = {}
        with open(self._nodef, "r") as f:
            for line in f:
                line   = line.split('\t')
                taxid  = int(line[0])
                parent = int(line[2])
                rank   = line[4]
                divid  = int(line[8])

                node   = Node(taxid   = taxid,
                              parent  = old2news[parent] if parent in old_taxids else parent,
                              rank    = rank,
                              name    = taxid2name[taxid],
                              equal   = taxid2equal[taxid]   if taxid in taxid2equal.keys() else "",
                              acronym = taxid2acronym[taxid] if taxid in taxid2acronym.keys() else "",
                              legacy  = False,
                              division=div2codes[divid]
                              )

                taxid2nodes[taxid] = node
        # Finished import all current taxid nodes, extending old_taxids (for compact)
        cur_taxids = set(taxid2nodes.keys())
        assert not old_taxids.intersection(cur_taxids), TaxdumpError("current taxids have legacy taxids")
        for old, new in old2news.items():
            new_node = taxid2nodes[new]
            node = Node(taxid   = new,
                        parent  = new_node.parent,
                        rank    = new_node.rank,
                        name    = new_node.name,
                        equal   = new_node.equal,
                        acronym = new_node.acronym,
                        legacy  = True,
                        division=new_node.division
                        )
            taxid2nodes[old] = node

        return taxid2nodes, del_taxids

    def _load_taxdump(self):
        if self._pickle.is_file():
            with open(self._pickle, 'rb') as fin:
                taxid2nodes, del_taxids = pickle.load(fin)
        else:
            taxid2nodes, del_taxids = self._import_nodes()

        return taxid2nodes, del_taxids

    def _dump_taxdump(self):
        print(f"Writing to {self._pickle}")
        with open(self._pickle, 'wb') as fout:
            pickle.dump([self.taxid2nodes,
                         self.delnodes], fout, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Taxdump dumped!")

    def is_delnodes(self, taxid: int) -> bool:
        return taxid in self.delnodes

    def _rapid_fuzz(self, key_word: str="Influenza", limit: int=10):
        results = process.extract(key_word, self._allnames, scorer=fuzz.WRatio, limit=limit,)
        for res in results:
            q_name = res[0]
            q_taid = self._name2taxid[q_name]
            q_node = self.taxid2nodes[q_taid]
            q_colr = re.sub(key_word, m_color, q_name, flags=re.IGNORECASE)
            pt_str = f"{q_taid:<{self._max_taxid_strlen}}\t{q_node.rank:<{self._max_rank_strlen}}\t{q_colr}"
            print(pt_str)


class Taxon:
    """
    Create an object of the Taxon class.
    """
    def __init__(self, taxid: int, taxdb: TaxDb):
        if taxid in taxdb.delnodes:
            raise TaxidError(f"The input {taxid=} is already deleted!")
        if taxid not in taxdb.taxid2nodes.keys():
            raise TaxidError(f"The input {taxid=} is not a valid NCBI taxonomy identifier!")

        # taxid, taxonomy node, and lineage
        self._taxid = taxid
        self._node  = taxdb.taxid2nodes[taxid]
        self._lineage = self._find_lineage(taxdb)

    @property
    def taxid(self) -> int:
        return self._taxid

    @property
    def node(self) -> Node:
        return self._node

    @property
    def lineage(self) -> List[Node]:
        return self._lineage

    # other infered taxon attributes
    @property
    def update_taxid(self) -> int:
        return self.node.taxid

    @property
    def name(self) -> str:
        return self.node.name

    @property
    def rank(self) -> str:
        return self.node.rank

    @property
    def acronym(self) -> str|None:
        return self.node.acronym

    @property
    def legacy_taxid(self) -> bool:
        return self.node.legacy

    @property
    def taxid_lineage(self) -> List[int]:
        return [node.taxid for node in self.lineage]

    @property
    def rank_lineage(self) -> List[str]:
        return [node.rank for node in self.lineage]

    @property
    def name_lineage(self) -> List[str]:
        return [node.name for node in self.lineage]



    def _find_lineage(self, taxdb: TaxDb) -> List[Node]:
        lineage = [self.node]
        current_taxid = lineage[-1].taxid
        while lineage[-1].parent != current_taxid:
            current_taxid = lineage[-1].parent
            lineage.append(taxdb.taxid2nodes[current_taxid])
        return lineage


RANKNAMES  = ["species", "genus", "family", "order", "class", "phylum", "superkingdom", "realm"]
RANK2LEVEL = {k: i for i,k in enumerate(RANKNAMES)}
LEVEL2RANK = {i: k for i,k in enumerate(RANKNAMES)}


