#!/usr/bin/env python3
"""
Release helper script for taxdumpy.

This script helps automate the release process by:
1. Checking that all tests pass
2. Updating the version number
3. Creating a git tag
4. Building the package
5. Optionally uploading to PyPI

Usage:
    python scripts/release.py --version 1.2.3 [--test] [--upload]
"""

import argparse
import subprocess
import sys
import re
from pathlib import Path


def run_command(cmd, check=True, capture_output=False):
    """Run a shell command."""
    print(f"Running: {cmd}")
    result = subprocess.run(
        cmd, shell=True, check=check, capture_output=capture_output, text=True
    )
    if capture_output:
        return result.stdout.strip()
    return result


def validate_version(version):
    """Validate semantic version format."""
    pattern = r"^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$"
    if not re.match(pattern, version):
        raise ValueError(f"Invalid version format: {version}")


def check_working_directory():
    """Ensure working directory is clean."""
    status = run_command("git status --porcelain", capture_output=True)
    if status:
        print("❌ Working directory is not clean:")
        print(status)
        sys.exit(1)
    print("✅ Working directory is clean")


def run_tests():
    """Run the test suite."""
    print("🧪 Running tests...")
    run_command("python -m pytest tests/")
    print("✅ All tests passed")


def check_code_quality():
    """Run code quality checks."""
    print("🎨 Checking code formatting...")
    run_command("black --check src/ tests/")
    print("✅ Code formatting is correct")


def update_version_in_file(file_path, version):
    """Update version in __init__.py."""
    content = file_path.read_text()
    updated = re.sub(
        r'^__version__ = ".*"',
        f'__version__ = "{version}"',
        content,
        flags=re.MULTILINE,
    )
    file_path.write_text(updated)
    print(f"✅ Updated version to {version} in {file_path}")


def create_git_tag(version):
    """Create and push git tag."""
    tag = f"v{version}"

    # Check if tag already exists
    try:
        run_command(f"git rev-parse {tag}", capture_output=True)
        print(f"❌ Tag {tag} already exists")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass  # Tag doesn't exist, which is good

    # Commit version bump
    run_command(f"git add src/taxdumpy/__init__.py")
    run_command(f"git commit -m 'Bump version to {version}'")

    # Create and push tag
    run_command(f"git tag {tag}")
    run_command(f"git push origin main")
    run_command(f"git push origin {tag}")
    print(f"✅ Created and pushed tag {tag}")


def build_package():
    """Build the package."""
    print("📦 Building package...")
    # Clean dist directory manually
    run_command("rm -rf dist/", check=False)
    run_command("python -m build")
    print("✅ Package built successfully")


def upload_to_pypi(test=False):
    """Upload package to PyPI or Test PyPI."""
    repo = "testpypi" if test else "pypi"
    print(f"🚀 Uploading to {'Test ' if test else ''}PyPI...")

    # Check if twine is installed
    try:
        run_command("python -m twine --version", capture_output=True)
    except subprocess.CalledProcessError:
        print("❌ twine not found. Please install it with: pip install twine")
        sys.exit(1)

    if test:
        run_command("python -m twine upload --repository testpypi dist/*")
    else:
        run_command("python -m twine upload dist/*")

    print(f"✅ Successfully uploaded to {'Test ' if test else ''}PyPI")


def main():
    parser = argparse.ArgumentParser(description="Release taxdumpy package")
    parser.add_argument(
        "--version", required=True, help="Version to release (e.g., 1.2.3)"
    )
    parser.add_argument(
        "--test", action="store_true", help="Upload to Test PyPI instead"
    )
    parser.add_argument(
        "--upload", action="store_true", help="Upload to PyPI after building"
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")

    args = parser.parse_args()

    try:
        validate_version(args.version)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"🚀 Starting release process for version {args.version}")

    # Pre-flight checks
    check_working_directory()

    if not args.skip_tests:
        run_tests()
        check_code_quality()

    # Update version
    init_file = Path("src/taxdumpy/__init__.py")
    if not init_file.exists():
        print("❌ src/taxdumpy/__init__.py not found")
        sys.exit(1)

    update_version_in_file(init_file, args.version)

    # Create git tag
    create_git_tag(args.version)

    # Build package
    build_package()

    # Upload if requested
    if args.upload:
        upload_to_pypi(test=args.test)
    else:
        print("📝 Package built. Use --upload to upload to PyPI")
        if args.test:
            print("💡 Use: python -m twine upload --repository testpypi dist/*")
        else:
            print("💡 Use: python -m twine upload dist/*")

    print(f"🎉 Release {args.version} completed successfully!")


if __name__ == "__main__":
    main()
