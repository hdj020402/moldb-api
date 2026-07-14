"""Tests for CLI argument parsing."""

import subprocess
import sys


def _run_moldb(args: str) -> subprocess.CompletedProcess:
    """Run the moldb CLI with given arguments."""
    return subprocess.run(
        [sys.executable, "-m", "moldb.cli"] + args.split(),
        capture_output=True,
        text=True,
    )


class TestCLIHelp:
    def test_help_flag(self):
        result = _run_moldb("--help")
        assert result.returncode == 0
        assert "moldb" in result.stdout

    def test_api_help(self):
        result = _run_moldb("api --help")
        assert result.returncode == 0

    def test_builder_help(self):
        result = _run_moldb("builder --help")
        assert result.returncode == 0


class TestCLIErrors:
    def test_missing_command(self):
        result = _run_moldb("")
        assert result.returncode != 0

    def test_builder_missing_mapping(self):
        result = _run_moldb("builder")
        assert result.returncode != 0

    def test_builder_invalid_on_conflict(self):
        result = _run_moldb("builder --on-conflict invalid --mapping test.csv")
        assert result.returncode != 0


class TestCLIInfo:
    def test_info_help(self):
        result = _run_moldb("info --help")
        assert result.returncode == 0

    def test_info_missing_path(self):
        result = _run_moldb("info /nonexistent/path.lmdb")
        assert result.returncode != 0

    def test_info_real_db(self, tmp_db_path, conf):
        from moldb.store import MoleculeStore
        with MoleculeStore(tmp_db_path) as store:
            store.put_conformers("InChI=1/A", [conf])
        result = _run_moldb(f"info {tmp_db_path}")
        assert result.returncode == 0
        assert "Molecules:" in result.stdout
        assert "Conformers:" in result.stdout


class TestCLIVersion:
    def test_version_via_module(self):
        """Ensure importlib.metadata version works."""
        from moldb import __version__
        assert isinstance(__version__, str)
        assert len(__version__) > 0
        assert "." in __version__
