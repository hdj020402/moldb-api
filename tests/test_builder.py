"""Tests for builder stream functions."""

import os
import pytest

from moldb.builder.lmdb import build_lmdb_stream
from moldb.builder.sqlite import build_sqlite_stream
from moldb.core.lmdb import LMDBMoleculeStore
from moldb.core.sqlite import SQLiteMoleculeStore


class TestBuildLmdbStream:
    def test_write_new_molecules(self, tmp_lmdb_path, xyz_list):
        items = [
            ("InChI=1/A", [xyz_list[0]]),
            ("InChI=1/B", [xyz_list[1]]),
        ]
        stats = build_lmdb_stream(items, tmp_lmdb_path)
        assert stats["written"] == 2
        assert stats["processed"] == 2

        store = LMDBMoleculeStore(tmp_lmdb_path)
        assert store.exists("InChI=1/A")
        assert store.exists("InChI=1/B")
        store.close()

    def test_write_dict_conformers(self, tmp_lmdb_path, conf_with_meta):
        items = [("A", [conf_with_meta])]
        stats = build_lmdb_stream(items, tmp_lmdb_path)
        assert stats["written"] == 1

        store = LMDBMoleculeStore(tmp_lmdb_path)
        data = store.get_conformers("A")
        assert data["conformers"][0]["energy"] == conf_with_meta["energy"]
        store.close()

    def test_skip_existing(self, tmp_lmdb_path, xyz_list):
        build_lmdb_stream([("A", [xyz_list[0]])], tmp_lmdb_path)
        stats = build_lmdb_stream(
            [("A", [xyz_list[1]])],
            tmp_lmdb_path,
            on_conflict="skip",
        )
        assert stats["skipped"] == 1
        assert stats["written"] == 0

    def test_merge_streaming(self, tmp_lmdb_path, xyz_list):
        """Simulate streaming: each conformer arrives separately."""
        for conf in xyz_list:
            build_lmdb_stream(
                [("A", [conf])],
                tmp_lmdb_path,
                on_conflict="merge",
            )

        store = LMDBMoleculeStore(tmp_lmdb_path)
        data = store.get_conformers("A")
        assert data["count"] == len(xyz_list)
        store.close()

    def test_overwrite_default(self, tmp_lmdb_path, xyz_list):
        build_lmdb_stream([("A", [xyz_list[0], xyz_list[1]])], tmp_lmdb_path)
        build_lmdb_stream([("A", [xyz_list[2]])], tmp_lmdb_path)

        store = LMDBMoleculeStore(tmp_lmdb_path)
        data = store.get_conformers("A")
        assert data["count"] == 1
        store.close()

    def test_skip_empty_conformers(self, tmp_lmdb_path):
        """Items with empty conformer lists are skipped."""
        stats = build_lmdb_stream(
            [("A", []), ("B", ["1\n\nC 0 0 0\n"])],
            tmp_lmdb_path,
        )
        assert stats["written"] == 1
        assert stats["processed"] == 1

    def test_large_batch(self, tmp_lmdb_path, xyz_single):
        """Write more molecules than batch_size to force multiple batches."""
        n = 20
        items = [(f"mol_{i}", [xyz_single]) for i in range(n)]
        stats = build_lmdb_stream(items, tmp_lmdb_path, batch_size=5)
        assert stats["written"] == n

    def test_returns_enriched_stats(self, tmp_lmdb_path, xyz_single):
        build_lmdb_stream([("A", [xyz_single])], tmp_lmdb_path)
        stats = build_lmdb_stream(
            [("A", [xyz_single]), ("B", [xyz_single])],
            tmp_lmdb_path,
            on_conflict="skip",
        )
        assert "processed" in stats
        assert "written" in stats
        assert "skipped" in stats
        assert "overwritten" in stats
        assert "merged" in stats
        assert "conformers" in stats
        assert "time_seconds" in stats


class TestBuildSqliteStream:
    def test_write_new_molecules(self, tmp_sqlite_path, xyz_list):
        items = [("A", [xyz_list[0]]), ("B", [xyz_list[1]])]
        stats = build_sqlite_stream(items, tmp_sqlite_path)
        assert stats["written"] == 2

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        assert store.exists("A")
        assert store.exists("B")

    def test_write_dict_conformers(self, tmp_sqlite_path, conf_with_meta):
        stats = build_sqlite_stream([("A", [conf_with_meta])], tmp_sqlite_path)
        assert stats["written"] == 1

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        data = store.get_conformers("A")
        assert data["conformers"][0]["energy"] == conf_with_meta["energy"]

    def test_skip_existing(self, tmp_sqlite_path, xyz_list):
        build_sqlite_stream([("A", [xyz_list[0]])], tmp_sqlite_path)
        stats = build_sqlite_stream(
            [("A", [xyz_list[1]])],
            tmp_sqlite_path,
            on_conflict="skip",
        )
        assert stats["skipped"] == 1

    def test_merge_streaming(self, tmp_sqlite_path, xyz_list):
        for conf in xyz_list:
            build_sqlite_stream(
                [("A", [conf])],
                tmp_sqlite_path,
                on_conflict="merge",
            )

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        data = store.get_conformers("A")
        assert data["count"] == len(xyz_list)

    def test_overwrite_default(self, tmp_sqlite_path, xyz_list):
        build_sqlite_stream([("A", [xyz_list[0], xyz_list[1]])], tmp_sqlite_path)
        build_sqlite_stream([("A", [xyz_list[2]])], tmp_sqlite_path)

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        data = store.get_conformers("A")
        assert data["count"] == 1
