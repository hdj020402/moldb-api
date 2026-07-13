"""Shared test fixtures for moldb."""

import tempfile
import os
import pytest


@pytest.fixture
def xyz_single():
    """A single-conformer XYZ content string."""
    return "3\ncomment line\nO  0.000  0.000  0.000\nH  0.757  0.586  0.000\nH -0.757  0.586  0.000\n"


@pytest.fixture
def xyz_list():
    """Multiple XYZ content strings for testing conformer batches."""
    return [
        "1\n\nC  0.000  0.000  0.000\n",
        "2\n\nN  0.000  0.000  0.000\nH  0.000  0.000  1.000\n",
        "3\n\nO  0.000  0.000  0.000\nH  0.757  0.586  0.000\nH -0.757  0.586  0.000\n",
    ]


@pytest.fixture
def conf(xyz_single):
    """A minimal conformer dict (just XYZ content)."""
    return {"xyz": xyz_single}


@pytest.fixture
def confs(xyz_list):
    """A list of minimal conformer dicts."""
    return [{"xyz": x} for x in xyz_list]


@pytest.fixture
def conf_with_meta(xyz_single):
    """A conformer dict with arbitrary metadata."""
    return {
        "xyz": xyz_single,
        "energy": -76.4,
        "source": "optimization_run_01.xyz",
        "comment": "B3LYP/6-31G* optimized",
    }


@pytest.fixture
def tmp_lmdb_path():
    """Temporary LMDB database path (cleaned up after test)."""
    with tempfile.TemporaryDirectory() as d:
        yield os.path.join(d, "test.lmdb")


@pytest.fixture
def tmp_sqlite_path():
    """Temporary SQLite database path (cleaned up after test)."""
    with tempfile.TemporaryDirectory() as d:
        yield os.path.join(d, "test.db")
