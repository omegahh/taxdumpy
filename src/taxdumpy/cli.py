"""Taxdumpy command-line interface
"""

import os
import sys
import pickle
import argparse

from tqdm import tqdm
from pathlib import Path
from typing import Optional, List

from taxdumpy.taxdb import TaxDb
from taxdumpy.taxsqlite import TaxSQLite
from taxdumpy.taxon import Taxon
from taxdumpy.ansi  import u_str

def _params_parser():
    TAXDB_PATH = os.environ.get("TAXDB_PATH", Path.home() / ".taxonkit")
    parser = argparse.ArgumentParser(description="Toolkit for parsing NCBI taxonomy and resolving taxon lineage")
    sub_parsers = parser.add_subparsers(dest='command')

    cache_parser = sub_parsers.add_parser('cache')
    cache_parser.add_argument('-d', dest='taxdb', help=f'path of upzipped taxonomy database, default: {TAXDB_PATH}', default=TAXDB_PATH)
    cache_parser.add_argument('-f', dest='taxidf', help=f"If specified, cache a tiny version of TaxDb which only contains taxids in the given file.")

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
        TAXSQL = TaxSQLite(taxdb_path)
        print(TAXSQL)
        if not parsed_args.taxidf:
            pickle_file = taxdb_path / "taxdump.pickle"
            pickle_file.unlink(missing_ok=True)
            TAXDB = TaxDb(taxdb_path)
            TAXDB.dump_taxdump()
        else:
            taxid_file = Path(parsed_args.taxidf)
            assert taxid_file.is_file(), FileExistsError(f"Input file {u_str(taxid_file)} is not found")
            try:
                with open(taxid_file, 'r') as fin:
                    all_taxids = [int(line.strip()) for line in fin]
            except Exception as e:
                print(f"Error in parsing taxid file:\n\t{u_str(taxid_file)}")
                raise e
            all_taxids = frozenset(all_taxids)
            print(f"Loaded {len(all_taxids):,} taxids...")

            pickle_file = taxdb_path / "taxdump_fast.pickle"
            pickle_file.unlink(missing_ok=True)
            TAXDB = TaxDb(taxdb_path)
            print(f"Loading the full version of TAXDB, which contains {len(TAXDB):,} taxids.")
            kept_taxids = []
            for taxid in tqdm(TAXDB._taxid2nodes.keys(), ncols=120):
                taxon = Taxon(taxid, TAXDB)
                for lineage_taxid in taxon.taxid_lineage:
                    if lineage_taxid in all_taxids:
                        kept_taxids.extend(taxon.taxid_lineage)
                        break
            kept_taxids = frozenset(kept_taxids)
            print(f"Number of kept taxids: {len(kept_taxids):,}")
            kept_taxid2nodes = {k: v for k,v in TAXDB._taxid2nodes.items() if k in kept_taxids}
            print(f"Writing to {u_str(pickle_file)}")
            with open(pickle_file, 'wb') as fout:
                pickle.dump([kept_taxid2nodes,
                             TAXDB._old2news,
                             TAXDB.delnodes], fout, protocol=pickle.HIGHEST_PROTOCOL)
            print(f"Fast Taxdump dumped!")

    elif parsed_args.command == 'lineage':
        TAXDB = TaxSQLite(taxdb_path)
        taxid = parsed_args.taxid
        taxon = Taxon(taxid, TAXDB)
        print(taxon.__repr__())

    elif parsed_args.command == 'search':
        TAXDB = TaxSQLite(taxdb_path)
        keyword = parsed_args.keyword
        TAXDB.fuzzy_search(kw=keyword)

    return 0

if __name__ == "__main__":
    sys.exit(main())
