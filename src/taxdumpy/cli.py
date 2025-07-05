"""Taxdumpy command-line interface
"""

import os
import sys
import argparse

from pathlib import Path
from typing import Optional, List

from taxdumpy.taxdb import TaxDb
from taxdumpy.taxon import Taxon

def _params_parser():
    TAXDB_PATH = os.environ.get("TAXDB_PATH", Path.home() / ".taxonkit")
    parser = argparse.ArgumentParser(description="Toolkit for parsing NCBI taxonomy and resolving taxon lineage")
    sub_parsers = parser.add_subparsers(dest='command')

    cache_parser = sub_parsers.add_parser('cache')
    cache_parser.add_argument('-d', dest='taxdb', help=f'path of upzipped taxonomy database, default: {TAXDB_PATH}', default=TAXDB_PATH)

    trace_parser = sub_parsers.add_parser('lineage')
    trace_parser.add_argument('-d', dest='taxdb', help=f'path of upzipped taxonomy database, default: {TAXDB_PATH}', default=TAXDB_PATH)
    trace_parser.add_argument("--fast", action="store_true")
    trace_parser.add_argument("taxid", help=f"NCBI taxonomy id", type=int)

    sname_parser = sub_parsers.add_parser('search')
    sname_parser.add_argument('-d', dest='taxdb', help=f'path of upzipped taxonomy database, default: {TAXDB_PATH}', default=TAXDB_PATH)
    sname_parser.add_argument("--fast", action="store_true")
    sname_parser.add_argument("keyword", help=f"organism name", type=str)

    return parser

# Main Entry Point
def main(args: Optional[List[str]] = None) -> int:
    parsed_args = _params_parser().parse_args(args)
    taxdb_path  = Path(parsed_args.taxdb)
    if not taxdb_path.is_dir():
        print(f"Input Path {taxdb_path=} is not exist. aborting!")
        return 1

    if parsed_args.command == 'cache':
        sqlite_file = taxdb_path / "taxdump.sqlite"
        sqlite_file.unlink(missing_ok=True)
        TAXDB = TaxDb(taxdb_path)
        print(TAXDB)

    elif parsed_args.command == 'lineage':
        TAXDB = TaxDb(taxdb_path)
        taxid = parsed_args.taxid
        taxon = Taxon(taxid, TAXDB)
        print(taxon.__repr__())

    elif parsed_args.command == 'search':
        TAXDB = TaxDb(taxdb_path)
        keyword = parsed_args.keyword
        TAXDB.fuzzy_search(kw=keyword)

    return 0

if __name__ == "__main__":
    sys.exit(main())
