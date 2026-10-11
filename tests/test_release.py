"""Release helper side effects are tested with subprocess and publishing mocked."""

import importlib.util
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def release(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
    spec = importlib.util.spec_from_file_location("release_helper", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)
    init = tmp_path / "src" / "taxdumpy" / "__init__.py"
    init.parent.mkdir(parents=True)
    init.write_text('__version__ = "1.3.0"\n')
    return module


@pytest.mark.parametrize("mode", [[], ["--test-pypi"], ["--publish"]])
def test_release_modes_and_order(release, monkeypatch, mode):
    events = []
    commands = []

    def command(args, **kwargs):
        commands.append(args)
        return "src/taxdumpy/__init__.py" if args[:3] == ["git", "diff", "--cached"] else ""

    monkeypatch.setattr(release, "run_command", command)
    monkeypatch.setattr(release, "check_production_branch", lambda version: events.append("branch"))
    monkeypatch.setattr(release, "run_tests", lambda: events.append("tests"))

    def build(version):
        assert Path("src/taxdumpy/__init__.py").read_text() == '__version__ = "1.4.0"\n'
        events.append("build")
        return [Path("dist/fresh.whl"), Path("dist/fresh.tar.gz")]

    monkeypatch.setattr(release, "build_package", build)
    actual_publish = release.publish_tag

    def publish(version):
        events.append("publish")
        actual_publish(version)

    monkeypatch.setattr(release, "publish_tag", publish)
    assert release.main(["--version", "1.4.0", *mode]) == 0
    if mode == ["--publish"]:
        assert events == ["branch", "tests", "build", "publish"]
        assert ["git", "push", "--atomic", "origin", "main", "refs/tags/v1.4.0"] in commands
        assert not any("twine" in args for args in commands)
    else:
        assert events == ["tests", "build"]
        assert all(args[:2] not in (["git", "push"], ["git", "tag"], ["git", "commit"]) for args in commands)
        uploads = [args for args in commands if "upload" in args]
        if mode:
            assert len(uploads) == 1
            assert uploads[0][3:] == ["upload", "--repository", "testpypi", "dist/fresh.whl", "dist/fresh.tar.gz"]
        else:
            assert uploads == []


@pytest.mark.parametrize("failure", ["run_tests", "build_package"])
def test_failed_validation_never_pushes_and_restores_version(release, monkeypatch, failure):
    command = Mock(return_value="")
    monkeypatch.setattr(release, "run_command", command)
    monkeypatch.setattr(release, "check_production_branch", Mock())
    monkeypatch.setattr(release, "run_tests", Mock())
    monkeypatch.setattr(release, "build_package", Mock())
    monkeypatch.setattr(release, failure, Mock(side_effect=subprocess.CalledProcessError(1, failure)))
    assert release.main(["--version", "1.4.0", "--publish"]) == 1
    assert Path("src/taxdumpy/__init__.py").read_text() == '__version__ = "1.3.0"\n'
    assert not any(call.args[0][:2] == ["git", "push"] for call in command.call_args_list)


def test_production_requires_main(release, monkeypatch):
    command = Mock(return_value="feature")
    monkeypatch.setattr(release, "run_command", command)
    with pytest.raises(ValueError, match="main"):
        release.check_production_branch("1.4.0")
    assert command.call_count == 1


def test_production_rejects_divergent_main(release, monkeypatch):
    command = Mock(side_effect=["main", None, subprocess.CalledProcessError(1, "merge-base")])
    monkeypatch.setattr(release, "run_command", command)
    with pytest.raises(subprocess.CalledProcessError):
        release.check_production_branch("1.4.0")
    assert command.call_args.args[0] == ["git", "merge-base", "--is-ancestor", "origin/main", "HEAD"]


@pytest.mark.parametrize("mode", [["--test", "--upload"], ["--upload"], ["--skip-tests"], ["--publish", "--test-pypi"]])
def test_legacy_or_conflicting_modes_rejected_before_side_effects(release, monkeypatch, mode):
    command = Mock()
    monkeypatch.setattr(release, "run_command", command)
    with pytest.raises(SystemExit) as error:
        release.main(["--version", "1.4.0", *mode])
    assert error.value.code == 2
    command.assert_not_called()


@pytest.mark.parametrize("version", ["1.2.3", "1.2.3rc1", "1.2.3a0", "1.2.3b2"])
def test_canonical_pypi_versions(release, version):
    release.validate_version(version)


@pytest.mark.parametrize("version", ["1.2", "1.2.3-rc.1", "01.2.3", "1.2.3;touch pwned", "1.2.3\n"])
def test_invalid_versions(release, version):
    with pytest.raises(ValueError):
        release.validate_version(version)


def test_command_uses_no_shell(release, monkeypatch):
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout="main\n"))
    monkeypatch.setattr(release.subprocess, "run", run)
    assert release.run_command(["git", "branch", "--show-current"], capture_output=True) == "main"
    assert "shell" not in run.call_args.kwargs
    assert run.call_args.args[0] == ["git", "branch", "--show-current"]


def test_build_checks_only_new_artifacts(release, monkeypatch):
    stale = Path("dist/stale.whl")
    stale.parent.mkdir()
    stale.write_bytes(b"previous build")
    commands = []

    def command(args, **kwargs):
        commands.append(args)
        if "build" in args:
            directory = Path(args[-1])
            (directory / "taxdumpy.whl").write_bytes(b"wheel")
            (directory / "taxdumpy.tar.gz").write_bytes(b"sdist")

    monkeypatch.setattr(release, "run_command", command)
    artifacts = release.build_package("1.4.0")
    assert len(artifacts) == 2
    assert stale.read_bytes() == b"previous build"
    assert commands[-1][2:4] == ["twine", "check"]
    assert str(stale) not in commands[-1]
    assert all(str(path) in commands[-1] for path in artifacts)
