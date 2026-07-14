"""Tests for builder stream functions."""

import pytest

from moldb.builder.lmdb import build_lmdb_stream
from moldb.builder.sqlite import build_sqlite_stream
from moldb.core.lmdb import LMDBMoleculeStore
from moldb.core.sqlite import SQLiteMoleculeStore


class TestBuildLmdbStream:
    def test_write_new_molecules(self, tmp_lmdb_path, confs):
        items = [
            ("InChI=1/A", [confs[0]]),
            ("InChI=1/B", [confs[1]]),
        ]
        stats = build_lmdb_stream(items, tmp_lmdb_path)
        assert stats["written"] == 2
        assert stats["processed"] == 2

        store = LMDBMoleculeStore(tmp_lmdb_path)
        assert store.exists("InChI=1/A")
        assert store.exists("InChI=1/B")
        store.close()

    def test_write_with_metadata(self, tmp_lmdb_path, conf_with_meta):
        items = [("A", [conf_with_meta])]
        stats = build_lmdb_stream(items, tmp_lmdb_path)
        assert stats["written"] == 1

        store = LMDBMoleculeStore(tmp_lmdb_path)
        data = store.get_conformers("A")
        assert data["conformers"][0]["energy"] == conf_with_meta["energy"]
        store.close()

    def test_skip_existing(self, tmp_lmdb_path, confs):
        build_lmdb_stream([("A", [confs[0]])], tmp_lmdb_path)
        stats = build_lmdb_stream(
            [("A", [confs[1]])],
            tmp_lmdb_path,
            on_conflict="skip",
        )
        assert stats["skipped"] == 1
        assert stats["written"] == 0

    def test_merge_streaming(self, tmp_lmdb_path, confs):
        """Simulate streaming: each conformer arrives separately."""
        for c in confs:
            build_lmdb_stream(
                [("A", [c])],
                tmp_lmdb_path,
                on_conflict="merge",
            )

        store = LMDBMoleculeStore(tmp_lmdb_path)
        data = store.get_conformers("A")
        assert data["count"] == len(confs)
        store.close()

    def test_overwrite_default(self, tmp_lmdb_path, confs):
        build_lmdb_stream([("A", [confs[0], confs[1]])], tmp_lmdb_path)
        build_lmdb_stream([("A", [confs[2]])], tmp_lmdb_path)

        store = LMDBMoleculeStore(tmp_lmdb_path)
        data = store.get_conformers("A")
        assert data["count"] == 1
        store.close()

    def test_large_batch(self, tmp_lmdb_path, conf):
        """Write more molecules than batch_size to force multiple batches."""
        n = 20
        items = [(f"mol_{i}", [conf]) for i in range(n)]
        stats = build_lmdb_stream(items, tmp_lmdb_path, batch_size=5)
        assert stats["written"] == n

    def test_returns_enriched_stats(self, tmp_lmdb_path, conf):
        build_lmdb_stream([("A", [conf])], tmp_lmdb_path)
        stats = build_lmdb_stream(
            [("A", [conf]), ("B", [conf])],
            tmp_lmdb_path,
            on_conflict="skip",
        )
        for key in ("processed", "written", "skipped", "overwritten",
                     "merged", "conformers", "time_seconds"):
            assert key in stats


class TestBuilderCommon:
    """Tests for shared builder utilities in moldb.builder.common."""

    def test_print_progress(self, capsys):
        from moldb.builder.common import print_progress
        result = {"written": 5, "overwritten": 2, "skipped": 1, "merged": 3}
        print_progress(10.5, 100, 9.5, result, 0.5)
        captured = capsys.readouterr()
        assert "W:5" in captured.out
        assert "O:2" in captured.out
        assert "S:1" in captured.out
        assert "M:3" in captured.out

    def test_print_progress_no_optional_fields(self, capsys):
        from moldb.builder.common import print_progress
        result = {"written": 5, "overwritten": 0}
        print_progress(10.5, 100, 9.5, result, 0.5)
        captured = capsys.readouterr()
        assert "W:5" in captured.out
        # Skipped/merged not shown when zero
        assert "S:" not in captured.out
        assert "M:" not in captured.out


class TestBuildSqliteStream:
    def test_write_new_molecules(self, tmp_sqlite_path, confs):
        items = [("A", [confs[0]]), ("B", [confs[1]])]
        stats = build_sqlite_stream(items, tmp_sqlite_path)
        assert stats["written"] == 2

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        assert store.exists("A")
        assert store.exists("B")

    def test_write_with_metadata(self, tmp_sqlite_path, conf_with_meta):
        stats = build_sqlite_stream([("A", [conf_with_meta])], tmp_sqlite_path)
        assert stats["written"] == 1

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        data = store.get_conformers("A")
        assert data["conformers"][0]["energy"] == conf_with_meta["energy"]

    def test_skip_existing(self, tmp_sqlite_path, confs):
        build_sqlite_stream([("A", [confs[0]])], tmp_sqlite_path)
        stats = build_sqlite_stream(
            [("A", [confs[1]])],
            tmp_sqlite_path,
            on_conflict="skip",
        )
        assert stats["skipped"] == 1

    def test_merge_streaming(self, tmp_sqlite_path, confs):
        for c in confs:
            build_sqlite_stream(
                [("A", [c])],
                tmp_sqlite_path,
                on_conflict="merge",
            )

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        data = store.get_conformers("A")
        assert data["count"] == len(confs)

    def test_overwrite_default(self, tmp_sqlite_path, confs):
        build_sqlite_stream([("A", [confs[0], confs[1]])], tmp_sqlite_path)
        build_sqlite_stream([("A", [confs[2]])], tmp_sqlite_path)

        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        data = store.get_conformers("A")
        assert data["count"] == 1
