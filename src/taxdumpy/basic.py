from dataclasses import dataclass

@dataclass
class Node:
    __slots__ = ("taxid","parent","rank","name","equal","acronym","legacy","division")
    taxid:    int
    parent:   int
    rank:     str
    name:     str
    equal:    str|None
    acronym:  str|None
    division: str

class TaxDbError(Exception):
    pass

class TaxidError(Exception):
    pass

class TaxRankError(Exception):
    pass
