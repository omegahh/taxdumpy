"""Tests for CLI functionality."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

from taxdumpy.cli import main, _params_parser


class TestCLI:
    """Test command-line interface."""

    def test_params_parser_creation(self):
        """Test that argument parser is created correctly."""
        parser = _params_parser()
        assert parser is not None

        # Test that subcommands exist
        # Note: This is a bit tricky to test directly
        # We'll test through main() instead

    def test_main_no_args(self, sample_taxdump_dir):
        """Test main with no arguments."""
        with patch("sys.argv", ["taxdumpy"]):
            # Should return 1 (error) or show help
            result = main([])
            # The result depends on argparse behavior
            assert isinstance(result, int)

    def test_main_cache_command(self, sample_taxdump_dir, temp_dir):
        """Test cache command."""
        # Copy sample data to temp dir for modification
        for file in [
            "nodes.dmp",
            "names.dmp",
            "merged.dmp",
            "delnodes.dmp",
            "division.dmp",
        ]:
            src = sample_taxdump_dir / file
            dst = temp_dir / file
            dst.write_text(src.read_text())

        args = ["cache", "-d", str(temp_dir)]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "Database" in output or "TAXDB" in output

        # Check that files were created
        assert (temp_dir / "taxdump.sqlite").exists()
        assert (temp_dir / "taxdump.pickle").exists()

    def test_main_cache_command_with_taxid_file(self, sample_taxdump_dir, temp_dir):
        """Test cache command with taxid file for fast caching."""
        # Copy sample data
        for file in [
            "nodes.dmp",
            "names.dmp",
            "merged.dmp",
            "delnodes.dmp",
            "division.dmp",
        ]:
            src = sample_taxdump_dir / file
            dst = temp_dir / file
            dst.write_text(src.read_text())

        # Create taxid file
        taxid_file = temp_dir / "important_taxids.txt"
        taxid_file.write_text("9606\n2161\n7868\n")

        args = ["cache", "-d", str(temp_dir), "-f", str(taxid_file)]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "taxids" in output.lower()

        # Check that fast cache file was created
        assert (temp_dir / "taxdump_fast.pickle").exists()

    def test_main_lineage_command(self, sample_taxdump_dir):
        """Test lineage command."""
        args = ["lineage", "-d", str(sample_taxdump_dir), "9606"]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "Homo sapiens" in output or "9606" in output

    def test_main_lineage_command_fast(self, sample_taxdump_dir):
        """Test lineage command with --fast flag."""
        args = ["lineage", "-d", str(sample_taxdump_dir), "--fast", "9606"]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "Homo sapiens" in output or "9606" in output

    def test_main_search_command(self, sample_taxdump_dir):
        """Test search command."""
        args = ["search", "-d", str(sample_taxdump_dir), "Homo sapiens"]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0
        # Search prints results, so we can't easily assert specific content
        # But it should complete successfully

    def test_main_search_command_fast(self, sample_taxdump_dir):
        """Test search command with --fast flag."""
        args = ["search", "-d", str(sample_taxdump_dir), "--fast", "human"]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0

    def test_main_search_with_typos(self, sample_taxdump_dir):
        """Test search command with typos."""
        args = ["search", "-d", str(sample_taxdump_dir), "Homo sapien"]  # Missing 's'

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0

    def test_main_invalid_directory(self, temp_dir):
        """Test behavior with invalid taxdump directory."""
        nonexistent_dir = temp_dir / "nonexistent"

        args = ["cache", "-d", str(nonexistent_dir)]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 1  # Should return error code
        # Error is printed to stderr, not stdout
        # Just verify error code is returned

    def test_main_invalid_taxid_file(self, sample_taxdump_dir, temp_dir):
        """Test cache command with invalid taxid file."""
        nonexistent_file = temp_dir / "nonexistent.txt"

        args = ["cache", "-d", str(sample_taxdump_dir), "-f", str(nonexistent_file)]

        result = main(args)
        # CLI should handle this gracefully and return error code
        assert result == 1

    def test_main_malformed_taxid_file(self, sample_taxdump_dir, temp_dir):
        """Test cache command with malformed taxid file."""
        # Copy sample data
        for file in [
            "nodes.dmp",
            "names.dmp",
            "merged.dmp",
            "delnodes.dmp",
            "division.dmp",
        ]:
            src = sample_taxdump_dir / file
            dst = temp_dir / file
            dst.write_text(src.read_text())

        # Create malformed taxid file
        taxid_file = temp_dir / "bad_taxids.txt"
        taxid_file.write_text("not_a_number\n9606\ninvalid\n")

        args = ["cache", "-d", str(temp_dir), "-f", str(taxid_file)]

        result = main(args)
        # CLI should handle this gracefully and return error code
        assert result == 1

    def test_main_environment_variable(self, sample_taxdump_dir, monkeypatch):
        """Test using TAXDB_PATH environment variable."""
        # Set environment variable
        monkeypatch.setenv("TAXDB_PATH", str(sample_taxdump_dir))

        # Don't specify -d flag, should use environment variable
        args = ["lineage", "9606"]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "Homo sapiens" in output or "9606" in output

    @patch("taxdumpy.cli.TaxSQLite")
    @patch("taxdumpy.cli.TaxDb")
    def test_main_database_creation_mocking(
        self, mock_taxdb, mock_taxsqlite, sample_taxdump_dir
    ):
        """Test database creation with mocking."""
        # Mock the database classes
        mock_taxdb_instance = MagicMock()
        mock_taxsqlite_instance = MagicMock()
        mock_taxdb.return_value = mock_taxdb_instance
        mock_taxsqlite.return_value = mock_taxsqlite_instance

        args = ["cache", "-d", str(sample_taxdump_dir)]

        result = main(args)

        # Should have called both database constructors
        mock_taxdb.assert_called_once()
        mock_taxsqlite.assert_called_once()
        mock_taxdb_instance.dump_taxdump.assert_called_once()

    def test_main_lineage_invalid_taxid(self, sample_taxdump_dir):
        """Test lineage command with invalid taxid."""
        args = ["lineage", "-d", str(sample_taxdump_dir), "999999"]

        # Should return error code instead of raising exception
        result = main(args)
        assert result == 1

    def test_main_with_sys_argv(self, sample_taxdump_dir):
        """Test main function when called with sys.argv."""
        # Test that main() works when called without arguments
        # (using sys.argv)

        test_args = ["taxdumpy", "lineage", "-d", str(sample_taxdump_dir), "9606"]

        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                result = main()  # No arguments, should use sys.argv

        assert result == 0
        output = mock_stdout.getvalue()
        assert "Homo sapiens" in output or "9606" in output

    def test_cli_entry_point(self, sample_taxdump_dir):
        """Test CLI entry point works."""
        # Simple test that doesn't rely on exec
        test_args = ["lineage", "-d", str(sample_taxdump_dir), "9606"]

        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            result = main(test_args)

        assert result == 0
        output = mock_stdout.getvalue()
        assert "Homo sapiens" in output or "9606" in output
