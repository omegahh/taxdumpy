"""Taxdumpy command-line interface"""

import os
import sys
import pickle
import argparse
import logging
from pathlib import Path
from typing import Optional, List

from tqdm import tqdm

from taxdumpy.taxdb import TaxDb
from taxdumpy.taxsqlite import TaxSQLite
from taxdumpy.taxon import Taxon
from taxdumpy.basic import (
    TaxdumpyError,
    TaxDbError,
    TaxidError,
    TaxdumpFileError,
    ValidationError,
    DatabaseCorruptionError,
)
from taxdumpy import __version__


# Configure logging for CLI
def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def handle_error(error: BaseException, exit_code: int = 1) -> int:
    """
    Handle and display errors in a user-friendly way.

    Args:
        error: The exception that occurred
        exit_code: Exit code to return

    Returns:
        Exit code
    """
    if isinstance(error, ValidationError):
        print(f"❌ Input Error: {error}", file=sys.stderr)

    elif isinstance(error, TaxdumpFileError):
        print(f"❌ File Error: {error}", file=sys.stderr)

    elif isinstance(error, DatabaseCorruptionError):
        print(f"❌ Database Error: {error}", file=sys.stderr)

    elif isinstance(error, TaxidError):
        print(f"❌ TaxID Error: {error}", file=sys.stderr)

    elif isinstance(error, TaxDbError):
        print(f"❌ Database Error: {error}", file=sys.stderr)

    elif isinstance(error, TaxdumpyError):
        print(f"❌ Taxdumpy Error: {error}", file=sys.stderr)

    elif isinstance(error, FileNotFoundError):
        print(f"❌ File not found: {error.filename}", file=sys.stderr)
        print(
            "💡 Make sure the file path is correct and the file exists", file=sys.stderr
        )

    elif isinstance(error, PermissionError):
        print(f"❌ Permission denied: {error.filename}", file=sys.stderr)
        print(
            "💡 Check file permissions or run with appropriate privileges",
            file=sys.stderr,
        )

    elif isinstance(error, MemoryError):
        print(
            f"❌ Memory Error: Not enough memory to complete operation", file=sys.stderr
        )
        print(
            "💡 Try using TaxSQLite instead of TaxDb for better memory efficiency",
            file=sys.stderr,
        )

    elif isinstance(error, KeyboardInterrupt):
        print(f"\n❌ Operation cancelled by user", file=sys.stderr)

    else:
        # Unexpected error
        print(f"❌ Unexpected error: {error}", file=sys.stderr)
        print(
            "💡 Please report this issue at https://github.com/omegahh/taxdumpy/issues",
            file=sys.stderr,
        )
        logging.exception("Unexpected error occurred")

    return exit_code


def _params_parser():
    """Create and configure the argument parser with improved error handling."""
    TAXDB_PATH = os.environ.get("TAXDB_PATH", Path.home() / ".taxonkit")

    parser = argparse.ArgumentParser(
        description="Toolkit for parsing NCBI taxonomy and resolving taxon lineage",
        epilog="Examples:\n"
        "  taxdumpy cache -d ./taxdump\n"
        "  taxdumpy search 'Escherichia coli'\n"
        "  taxdumpy lineage 9606\n"
        "  taxdumpy lineage --fast 511145",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Add global options
    parser.add_argument(
        "--version",
        action="version",
        version=f"taxdumpy {__version__}",
        help="Show program version and exit",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with debugging information",
    )

    # Create subcommands
    sub_parsers = parser.add_subparsers(
        dest="command",
        title="Available commands",
        description="Choose one of the following commands",
        help="Command to execute",
    )

    # Cache command
    cache_parser = sub_parsers.add_parser(
        "cache",
        help="Build and cache taxonomy databases",
        description="Build both SQLite and pickle databases from NCBI taxdump files",
    )
    cache_parser.add_argument(
        "-d",
        "--directory",
        dest="taxdb",
        metavar="PATH",
        help=f"Path to directory containing NCBI taxdump files (default: {TAXDB_PATH})",
        default=TAXDB_PATH,
    )
    cache_parser.add_argument(
        "-f",
        "--filter-file",
        dest="taxidf",
        metavar="FILE",
        help="File containing taxids to include in fast cache (one per line)",
    )

    # Lineage command
    trace_parser = sub_parsers.add_parser(
        "lineage",
        help="Show taxonomic lineage for a taxid",
        description="Display the complete taxonomic lineage for a given NCBI taxonomy ID",
    )
    trace_parser.add_argument(
        "-d",
        "--directory",
        dest="taxdb",
        metavar="PATH",
        help=f"Path to directory containing NCBI taxdump files (default: {TAXDB_PATH})",
        default=TAXDB_PATH,
    )
    trace_parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fast mode with pre-cached data (requires prior fast caching)",
    )
    trace_parser.add_argument(
        "taxid", help="NCBI taxonomy ID (e.g., 9606 for human)", type=int
    )

    # Search command
    sname_parser = sub_parsers.add_parser(
        "search",
        help="Search for organisms by name",
        description="Fuzzy search for organisms by scientific or common name",
    )
    sname_parser.add_argument(
        "-d",
        "--directory",
        dest="taxdb",
        metavar="PATH",
        help=f"Path to directory containing NCBI taxdump files (default: {TAXDB_PATH})",
        default=TAXDB_PATH,
    )
    sname_parser.add_argument(
        "--fast",
        action="store_true",
        help="Use fast mode with pre-cached data (requires prior fast caching)",
    )
    sname_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of search results to display (default: 10)",
    )
    sname_parser.add_argument(
        "keyword",
        help='Search term (organism name, e.g., "Escherichia coli" or "human")',
    )

    return parser


# Main Entry Point
def main(args: Optional[List[str]] = None) -> int:
    """
    Main entry point for the taxdumpy CLI.

    Args:
        args: Command line arguments (None to use sys.argv)

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Parse arguments
        parser = _params_parser()
        parsed_args = parser.parse_args(args)

        # Set up logging based on verbosity
        setup_logging(getattr(parsed_args, "verbose", False))

        # Handle case where no command is provided
        if not parsed_args.command:
            parser.print_help()
            print("\n❌ Error: No command specified", file=sys.stderr)
            print("💡 Use 'taxdumpy --help' for more information", file=sys.stderr)
            return 1

        # Validate and resolve database path
        try:
            taxdb_path = Path(parsed_args.taxdb).resolve()
            if not taxdb_path.exists():
                raise ValidationError(
                    "taxdb_path", str(taxdb_path), "existing directory"
                )
            if not taxdb_path.is_dir():
                raise ValidationError(
                    "taxdb_path", str(taxdb_path), "directory (not file)"
                )
        except Exception as e:
            return handle_error(e)

        # Execute the requested command
        try:
            if parsed_args.command == "cache":
                return _handle_cache_command(parsed_args, taxdb_path)
            elif parsed_args.command == "lineage":
                return _handle_lineage_command(parsed_args, taxdb_path)
            elif parsed_args.command == "search":
                return _handle_search_command(parsed_args, taxdb_path)
            else:
                print(f"❌ Unknown command: {parsed_args.command}", file=sys.stderr)
                return 1

        except KeyboardInterrupt:
            return handle_error(KeyboardInterrupt())
        except Exception as e:
            return handle_error(e)

    except SystemExit as e:
        # argparse calls sys.exit on errors, catch and return exit code
        return int(e.code) if e.code is not None else 1
    except Exception as e:
        return handle_error(e)


def _handle_cache_command(args, taxdb_path: Path) -> int:
    """Handle the cache command."""
    print(f"🗄️ Building taxonomy databases in {taxdb_path}")

    try:
        if not args.taxidf:
            # Build SQLite database
            print("📦 Building SQLite database...")
            sqlite_file = taxdb_path / "taxdump.sqlite"
            sqlite_file.unlink(missing_ok=True)
            taxsqlite = TaxSQLite(taxdb_path)
            print(f"✅ SQLite database created: {sqlite_file}")
            taxsqlite.close()
            # Build full pickle cache
            print("📦 Building full pickle cache...")
            pickle_file = taxdb_path / "taxdump.pickle"
            pickle_file.unlink(missing_ok=True)
            taxdb = TaxDb(taxdb_path)
            taxdb.dump_taxdump()
            print(f"✅ Full pickle cache created with {len(taxdb):,} taxonomy nodes")
        else:
            # Build fast pickle cache with filtered taxids
            print("📦 Building fast pickle cache...")
            return _build_fast_cache(args, taxdb_path)

        print("🎉 Database caching completed successfully!")
        return 0

    except Exception as e:
        return handle_error(e)


def _build_fast_cache(args, taxdb_path: Path) -> int:
    """Build fast cache with specified taxids."""
    try:
        # Validate and read taxid file
        taxid_file = Path(args.taxidf)
        if not taxid_file.exists():
            raise ValidationError("taxid_file", str(taxid_file), "existing file")

        print(f"📄 Reading taxids from {taxid_file}")
        all_taxids = set()
        line_num = 0

        with open(taxid_file, "r") as fin:
            for line_num, line in enumerate(fin, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    taxid = int(line)
                    if taxid < 1:
                        raise ValueError(f"Invalid taxid: {taxid}")
                    all_taxids.add(taxid)
                except ValueError as e:
                    raise ValidationError(
                        f"taxid_file line {line_num}", line, "positive integer"
                    )

        if not all_taxids:
            raise ValidationError(
                "taxid_file", str(taxid_file), "file with at least one valid taxid"
            )

        print(f"📊 Loaded {len(all_taxids):,} unique taxids from {line_num} lines")

        # Build fast cache
        pickle_file = taxdb_path / "taxdump_fast.pickle"
        pickle_file.unlink(missing_ok=True)

        print("🔄 Loading full taxonomy database...")
        taxdb = TaxDb(taxdb_path)
        print(f"📊 Full database contains {len(taxdb):,} taxids")

        print("🔍 Finding lineages for specified taxids...")

        kept_taxids = []
        for taxid in tqdm(
            taxdb._taxid2nodes.keys(), desc="Loop-over all taxids", ncols=80
        ):
            taxon = Taxon(taxid, taxdb)
            lineage_taxids = set(taxon.taxid_lineage)
            if lineage_taxids.intersection(all_taxids):
                kept_taxids.extend(taxon.taxid_lineage)
        kept_taxids = set(kept_taxids)

        print(f"📊 Keeping {len(kept_taxids):,} total taxids (including lineages)")

        # Create filtered database
        kept_taxid2nodes = {
            k: v for k, v in taxdb._taxid2nodes.items() if k in kept_taxids
        }
        # with open("kept_taxids.list", "w") as fout:
        #     for k, _ in kept_taxid2nodes.items():
        #         fout.write(f"{k}\n")

        print(f"💾 Writing fast cache to {pickle_file}")
        with open(pickle_file, "wb") as fout:
            pickle.dump(
                [kept_taxid2nodes, taxdb._old2news, taxdb.delnodes],
                fout,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

        print(f"🎉 Fast cache created with {len(kept_taxid2nodes):,} taxonomy nodes!")
        return 0

    except Exception as e:
        return handle_error(e)


def _handle_lineage_command(args, taxdb_path: Path) -> int:
    """Handle the lineage command."""
    try:
        print(f"🔍 Looking up lineage for TaxID {args.taxid}...")

        with TaxSQLite(taxdb_path) as taxdb:
            taxon = Taxon(args.taxid, taxdb)
            print(taxon.__repr__())

        return 0

    except Exception as e:
        return handle_error(e)


def _handle_search_command(args, taxdb_path: Path) -> int:
    """Handle the search command."""
    try:
        print(f"🔍 Searching for '{args.keyword}'...")

        # Choose database backend
        if args.fast:
            print("⚡ Using fast mode")
            taxdb = TaxDb(taxdb_path, fast=True)
            # Use TaxDb's fuzzy search
            results = taxdb._rapid_fuzz(args.keyword, limit=args.limit)
            if not results:
                print(f"❌ No results found for '{args.keyword}'")
                print("💡 Try a different search term or check spelling")
                return 0

            print(f"\n📊 Found {len(results)} results:")
            print(f"{'TaxID':<10} {'Rank':<15} {'Name'}")
            print("-" * 60)

            for result in results:
                try:
                    taxon = Taxon(int(result["taxid"]), taxdb)
                    score_str = (
                        f"({result['score']:.1f}%)"
                        if float(result["score"]) < 100
                        else ""
                    )
                    print(
                        f"{result['taxid']:<10} {taxon.rank:<15} {result['name']} {score_str}"
                    )
                except Exception as e:
                    logging.warning(f"Error displaying result {result['taxid']}: {e}")
        else:
            taxdb = TaxSQLite(taxdb_path)
            # Use TaxSQLite's fuzzy search (prints directly)
            taxdb.fuzzy_search(args.keyword, limit=args.limit)

        if hasattr(taxdb, "close"):
            taxdb.close()  # pyright: ignore[reportAttributeAccessIssue]

        return 0

    except Exception as e:
        return handle_error(e)


if __name__ == "__main__":
    sys.exit(main())
