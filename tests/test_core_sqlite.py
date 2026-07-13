"""Tests for SQLite core store."""

import json
import pytest

from moldb.core.sqlite import SQLiteMoleculeStore


@pytest.fixture
def store(tmp_sqlite_path):
    """A fresh initialized SQLite store."""
    s = SQLiteMoleculeStore(tmp_sqlite_path)
    s.init_db()
    return s


class TestInit:
    def test_create_new_store(self, tmp_sqlite_path):
        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        # Should be idempotent
        store.init_db()

    def test_reopen_existing_store(self, tmp_sqlite_path, xyz_single):
        s1 = SQLiteMoleculeStore(tmp_sqlite_path)
        s1.init_db()
        s1.put_conformers("A", [xyz_single])

        s2 = SQLiteMoleculeStore(tmp_sqlite_path)
        s2.init_db()
        assert s2.exists("A")


class TestExists:
    def test_exists_true(self, store, xyz_single):
        store.put_conformers("A", [xyz_single])
        assert store.exists("A")

    def test_exists_false(self, store):
        assert not store.exists("nonexistent")


class TestPutGetConformers:
    def test_write_and_read_bare_string(self, store, xyz_single):
        result = store.put_conformers("InChI=1/A", [xyz_single])
        assert result["action"] == "written"

        data = store.get_conformers("InChI=1/A")
        assert data["count"] == 1
        assert data["conformers"][0]["xyz"] == xyz_single

    def test_write_and_read_dict_with_metadata(self, store, conf_with_meta):
        store.put_conformers("A", [conf_with_meta])
        data = store.get_conformers("A")
        c = data["conformers"][0]
        assert c["energy"] == conf_with_meta["energy"]
        assert c["source"] == conf_with_meta["source"]

    def test_read_nonexistent(self, store):
        assert store.get_conformers("nope") is None

    def test_write_multiple_conformers(self, store, xyz_list):
        store.put_conformers("A", xyz_list)
        data = store.get_conformers("A")
        assert data["count"] == 3


class TestPutManyConformers:
    def test_write_many(self, store, xyz_list):
        items = [("A", [xyz_list[0]]), ("B", [xyz_list[1]])]
        stats = store.put_many_conformers(items)
        assert stats["written"] == 2


class TestOnConflict:
    def test_overwrite_replaces(self, store, xyz_single, xyz_list):
        store.put_conformers("A", [xyz_single])
        result = store.put_conformers("A", [xyz_list[1]], on_conflict="overwrite")
        assert result["action"] == "overwritten"
        assert result["count"] == 1

    def test_skip_when_exists(self, store, xyz_single, xyz_list):
        store.put_conformers("A", [xyz_single])
        result = store.put_conformers("A", [xyz_list[0]], on_conflict="skip")
        assert result["action"] == "skipped"
        assert result["count"] == 1

    def test_skip_when_not_exists(self, store, xyz_single):
        result = store.put_conformers("A", [xyz_single], on_conflict="skip")
        assert result["action"] == "written"

    def test_merge_appends(self, store, xyz_list):
        store.put_conformers("A", [xyz_list[0]], on_conflict="merge")
        result = store.put_conformers("A", [xyz_list[1]], on_conflict="merge")
        assert result["action"] == "merged"
        assert result["count"] == 2

        data = store.get_conformers("A")
        assert data["count"] == 2
        assert data["conformers"][0]["xyz"] == xyz_list[0]
        assert data["conformers"][1]["xyz"] == xyz_list[1]

    def test_put_many_all_modes(self, store, xyz_list):
        store.put_many_conformers([("A", [xyz_list[0]])])

        stats = store.put_many_conformers(
            [("A", [xyz_list[1]]), ("B", [xyz_list[2]])],
            on_conflict="skip",
        )
        assert stats["skipped"] == 1
        assert stats["written"] == 1

        stats = store.put_many_conformers(
            [("A", [xyz_list[2]]), ("C", [xyz_list[0]])],
            on_conflict="merge",
        )
        assert stats["merged"] == 1  # A already exists, C is new
        assert stats["written"] == 1


class TestDelete:
    def test_delete_existing(self, store, xyz_single):
        store.put_conformers("A", [xyz_single])
        assert store.delete("A")
        assert not store.exists("A")

    def test_delete_nonexistent(self, store):
        assert not store.delete("nope")

    def test_delete_removes_all_rows(self, store, xyz_list):
        store.put_conformers("A", xyz_list)
        store.delete("A")
        count = store.conn.execute(
            "SELECT COUNT(*) FROM molecules WHERE key LIKE ?",
            ("A%",)
        ).fetchone()[0]
        assert count == 0


class TestLegacyFormatReadback:
    def test_legacy_bare_string(self, store, xyz_single):
        # Simulate old-format bare XYZ string in DB
        store.conn.execute(
            "INSERT INTO molecules VALUES (?, ?)",
            ("X::meta", json.dumps({"count": 1}))
        )
        store.conn.execute(
            "INSERT INTO molecules VALUES (?, ?)",
            ("X::conf_000000", xyz_single)
        )
        store.conn.commit()

        data = store.get_conformers("X")
        assert data["conformers"][0]["xyz"] == xyz_single


class TestGetManyConformers:
    def test_get_many_mixed(self, store, xyz_list):
        store.put_conformers("A", [xyz_list[0]])
        store.put_conformers("B", [xyz_list[1]])

        results = store.get_many_conformers(["A", "B", "C"])
        assert len(results) == 3
        assert results[0][1] is not None
        assert results[1][1] is not None
        assert results[2][1] is None

    def test_get_many_empty_list(self, store):
        assert store.get_many_conformers([]) == []
