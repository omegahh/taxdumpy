#!/usr/bin/env python3
"""Prepare a release locally; --publish pushes a tag for GitHub's OIDC publisher.

--test-pypi uploads only to TestPyPI and never commits, tags, or pushes.
Production uploads are performed exclusively by .github/workflows/release.yml.
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(cmd, *, capture_output=False, env=None):
    """Run an argument list without shell expansion."""
    print(f"Running: {' '.join(map(str, cmd))}")
    result = subprocess.run(cmd, check=True, capture_output=capture_output, text=True, env=env)
    return result.stdout.strip() if capture_output else result


def validate_version(version):
    """Require canonical PyPI version spelling, including a/b/rc prereleases."""
    if not re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:(?:a|b|rc)(?:0|[1-9]\d*))?", version):
        raise ValueError(f"Invalid version: {version}; use 1.2.3 or 1.2.3rc1")


def check_working_directory():
    if run_command(["git", "status", "--porcelain"], capture_output=True):
        raise ValueError("Working directory must be clean before preparing a release")


def check_production_branch(version):
    if run_command(["git", "branch", "--show-current"], capture_output=True) != "main":
        raise ValueError("Production releases must be prepared on main")
    run_command(["git", "fetch", "origin", "main"])
    run_command(["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"])
    result = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/tags/v{version}"])
    if result.returncode == 0:
        raise ValueError(f"Tag v{version} already exists")
    if result.returncode != 1:
        raise ValueError("Could not check existing release tags")


def run_tests():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path("src").resolve()) + os.pathsep + env.get("PYTHONPATH", "")
    run_command([sys.executable, "-m", "pytest"], env=env)
    run_command(["ruff", "format", "--check", "src/", "tests/", "scripts/"])
    run_command(["ruff", "check", "src/", "tests/", "scripts/"])


def update_version_in_file(file_path, version):
    content = file_path.read_text(encoding="utf-8")
    updated, count = re.subn(r'^__version__ = ".*"$', f'__version__ = "{version}"', content, flags=re.MULTILINE)
    if count != 1:
        raise ValueError("Expected exactly one __version__ assignment")
    file_path.write_text(updated, encoding="utf-8")


def build_package(version):
    """Build and check only fresh artifacts, preserving previous builds."""
    Path("dist").mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix=f"v{version}-", dir="dist"))
    run_command([sys.executable, "-m", "build", "--outdir", str(output)])
    artifacts = sorted([*output.glob("*.whl"), *output.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise ValueError("Expected one wheel and one sdist")
    run_command([sys.executable, "-m", "twine", "check", *map(str, artifacts)])
    return artifacts


def publish_tag(version):
    """Commit and push the checked release; GitHub handles production publishing."""
    run_command(["git", "add", "src/taxdumpy/__init__.py"])
    if run_command(["git", "diff", "--cached", "--name-only"], capture_output=True):
        run_command(["git", "commit", "-m", f"Bump version to {version}"])
    run_command(["git", "tag", f"v{version}"])
    run_command(["git", "push", "--atomic", "origin", "main", f"refs/tags/v{version}"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--version", required=True, help="Version to prepare, e.g. 1.2.3 or 1.2.3rc1")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--publish", action="store_true", help="Commit and push main and a tag for production OIDC publishing"
    )
    mode.add_argument(
        "--test-pypi", action="store_true", help="Upload fresh artifacts to TestPyPI without pushing tags"
    )
    args = parser.parse_args(argv)
    try:
        validate_version(args.version)
        check_working_directory()
        if args.publish:
            check_production_branch(args.version)
        init_file = Path("src/taxdumpy/__init__.py")
        original = init_file.read_bytes()
        try:
            update_version_in_file(init_file, args.version)
            run_tests()
            artifacts = build_package(args.version)
        except BaseException:
            init_file.write_bytes(original)
            raise
        if args.publish:
            publish_tag(args.version)
            print(f"Pushed v{args.version}; follow the GitHub Release workflow for publication status")
        elif args.test_pypi:
            run_command([sys.executable, "-m", "twine", "upload", "--repository", "testpypi", *map(str, artifacts)])
        else:
            print(f"Prepared {args.version} locally: {artifacts[0].parent}")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Release failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
