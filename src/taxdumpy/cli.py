"""Taxdumpy command-line interface
"""

import os
import sys
import pickle
import argparse

from pathlib import Path
from tqdm import tqdm
from typing import Optional, List

from taxdumpy.taxdumpy import TaxDb, Taxon
from taxdumpy.ansi import b_str

def _params_parser():
    TAXDB_PATH = os.environ.get("TAXDB_PATH", Path.home() / ".taxonkit")
    parser = argparse.ArgumentParser(description="Toolkit for parsing NCBI taxonomy and resolving taxon lineage")
    sub_parsers = parser.add_subparsers(dest='command')

    cache_parser = sub_parsers.add_parser('cache')
    cache_parser.add_argument('-d', dest='taxdb', help=f'path of upzipped taxonomy database, default: {TAXDB_PATH}', default=TAXDB_PATH)

    fastc_parser = sub_parsers.add_parser('fast-cache')
    fastc_parser.add_argument('-d', dest='taxdb', help=f'path of upzipped taxonomy database, default: {TAXDB_PATH}', default=TAXDB_PATH)
    fastc_parser.add_argument('-f', '--file', help=f"a file for kept taxids", required=True)

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

    if parsed_args.command   == 'cache':
        pickle_file = taxdb_path / "taxdb.pickle"
        pickle_file.unlink(missing_ok=True)
        TAXDB = TaxDb(taxdb_path)
        TAXDB._dump_taxdump()

    elif parsed_args.command == 'fast-cache':
        taxid_file = Path(parsed_args.file)
        assert taxid_file.is_file(), FileExistsError(f"Input file {b_str(taxid_file)} is not found")
        try:
            all_taxids = []
            with open(taxid_file, 'r') as fin:
                for line in fin:
                    taxid = int(line.strip())
                    all_taxids.append(taxid)
        except Exception as e:
            print(f"Error in parsing taxid file:\n\t{b_str(taxid_file)}")
            raise e
        all_taxids = frozenset(all_taxids)
        print(f"Have loaded {len(all_taxids):,} taxids...")

        pickle_file = taxdb_path / "taxdb_fast.pickle"
        pickle_file.unlink(missing_ok=True)
        TAXDB = TaxDb(taxdb_path)
        print(f"Loading full version of TAXDB, which contains {len(TAXDB):,} taxids.")
        kept_taxids = []
        for taxid in tqdm(TAXDB.taxid2nodes.keys(), ncols=120):
            taxon = Taxon(taxid, TAXDB)
            for lineage_taxid in taxon.taxid_lineage:
                if lineage_taxid in all_taxids:
                    kept_taxids.extend(taxon.taxid_lineage)
                    break
        kept_taxids = frozenset(kept_taxids)
        print(f"Number of kept taxids: {len(kept_taxids):,}")
        kept_taxid2nodes = {k: v for k,v in TAXDB.taxid2nodes.items() if k in kept_taxids}
        print(f"Writing to {b_str(pickle_file)}")
        with open(pickle_file, 'wb') as fout:
            pickle.dump([kept_taxid2nodes,
                         TAXDB.delnodes], fout, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Fast Taxdump dumped!")

    elif parsed_args.command == 'lineage':
        TAXDB = TaxDb(taxdb_path, parsed_args.fast)
        taxid = parsed_args.taxid
        if taxid in TAXDB.delnodes:
            print(f"Error: {taxid=} is deleted in current database")
        else:
            tax = Taxon(taxid, TAXDB)
            print(tax.__repr__())

    elif parsed_args.command == 'search':
        TAXDB = TaxDb(taxdb_path, parsed_args.fast)
        keyword = parsed_args.keyword
        TAXDB._rapid_fuzz(key_word=keyword)

    return 0

if __name__ == "__main__":
    sys.exit(main())
