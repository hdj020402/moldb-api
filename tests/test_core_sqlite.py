"""Tests for SQLite core store."""

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
        store.init_db()  # idempotent

    def test_reopen_existing_store(self, tmp_sqlite_path, conf):
        s1 = SQLiteMoleculeStore(tmp_sqlite_path)
        s1.init_db()
        s1.put_conformers("A", [conf])

        s2 = SQLiteMoleculeStore(tmp_sqlite_path)
        s2.init_db()
        assert s2.exists("A")


class TestExists:
    def test_exists_true(self, store, conf):
        store.put_conformers("A", [conf])
        assert store.exists("A")

    def test_exists_false(self, store):
        assert not store.exists("nonexistent")


class TestPutGetConformers:
    def test_write_and_read(self, store, conf, xyz_single):
        result = store.put_conformers("A", [conf])
        assert result["action"] == "written"

        data = store.get_conformers("A")
        assert data["count"] == 1
        assert data["conformers"][0]["xyz"] == xyz_single

    def test_write_and_read_with_metadata(self, store, conf_with_meta):
        store.put_conformers("A", [conf_with_meta])
        data = store.get_conformers("A")
        c = data["conformers"][0]
        assert c["energy"] == conf_with_meta["energy"]
        assert c["source"] == conf_with_meta["source"]

    def test_read_nonexistent(self, store):
        assert store.get_conformers("nope") is None

    def test_write_multiple_conformers(self, store, confs):
        store.put_conformers("A", confs)
        data = store.get_conformers("A")
        assert data["count"] == len(confs)


class TestPutManyConformers:
    def test_write_many(self, store, confs):
        items = [("A", [confs[0]]), ("B", [confs[1]])]
        stats = store.put_many_conformers(items)
        assert stats["written"] == 2


class TestOnConflict:
    def test_overwrite_replaces(self, store, conf, confs):
        store.put_conformers("A", [conf])
        result = store.put_conformers("A", [confs[1]], on_conflict="overwrite")
        assert result["action"] == "overwritten"
        assert result["count"] == 1

    def test_skip_when_exists(self, store, conf, confs):
        store.put_conformers("A", [conf])
        result = store.put_conformers("A", [confs[0]], on_conflict="skip")
        assert result["action"] == "skipped"
        assert result["count"] == 1

    def test_skip_when_not_exists(self, store, conf):
        result = store.put_conformers("A", [conf], on_conflict="skip")
        assert result["action"] == "written"

    def test_merge_appends(self, store, confs):
        store.put_conformers("A", [confs[0]], on_conflict="merge")
        result = store.put_conformers("A", [confs[1]], on_conflict="merge")
        assert result["action"] == "merged"
        assert result["count"] == 2

        data = store.get_conformers("A")
        assert data["count"] == 2

    def test_put_many_all_modes(self, store, confs):
        store.put_many_conformers([("A", [confs[0]])])

        stats = store.put_many_conformers(
            [("A", [confs[1]]), ("B", [confs[2]])],
            on_conflict="skip",
        )
        assert stats["skipped"] == 1
        assert stats["written"] == 1

        stats = store.put_many_conformers(
            [("A", [confs[2]]), ("C", [confs[0]])],
            on_conflict="merge",
        )
        assert stats["merged"] == 1
        assert stats["written"] == 1


class TestDelete:
    def test_delete_existing(self, store, conf):
        store.put_conformers("A", [conf])
        assert store.delete("A")
        assert not store.exists("A")

    def test_delete_nonexistent(self, store):
        assert not store.delete("nope")

    def test_delete_removes_all_rows(self, store, confs):
        store.put_conformers("A", confs)
        store.delete("A")
        count = store.conn.execute(
            "SELECT COUNT(*) FROM molecules WHERE key LIKE ?",
            ("A%",)
        ).fetchone()[0]
        assert count == 0


class TestContextManager:
    def test_enter_exit(self, tmp_sqlite_path, conf):
        with SQLiteMoleculeStore(tmp_sqlite_path) as store:
            store.init_db()
            store.put_conformers("A", [conf])
            assert store.exists("A")
        # After exit, store should be closable and data persisted
        s2 = SQLiteMoleculeStore(tmp_sqlite_path)
        s2.init_db()
        assert s2.exists("A")
        s2.close()

    def test_exception_does_not_leak_resources(self, tmp_sqlite_path, conf):
        try:
            with SQLiteMoleculeStore(tmp_sqlite_path) as store:
                store.init_db()
                store.put_conformers("A", [conf])
                raise ValueError("test error")
        except ValueError:
            pass
        s2 = SQLiteMoleculeStore(tmp_sqlite_path)
        s2.init_db()
        assert s2.exists("A")
        s2.close()


class TestClose:
    def test_close_releases_connection(self, tmp_sqlite_path):
        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        store.close()
        # Should be able to reopen a fresh connection
        s2 = SQLiteMoleculeStore(tmp_sqlite_path)
        s2.init_db()
        s2.close()

    def test_close_before_init_no_error(self, tmp_sqlite_path):
        store = SQLiteMoleculeStore(tmp_sqlite_path)
        # close() before init_db() should not raise
        store.close()

    def test_double_close_no_error(self, tmp_sqlite_path):
        store = SQLiteMoleculeStore(tmp_sqlite_path)
        store.init_db()
        store.close()
        store.close()  # second close should be safe


class TestDeleteTransaction:
    def test_delete_nonexistent_no_side_effects(self, store, conf):
        """Delete of non-existent key should return False without side effects."""
        store.put_conformers("A", [conf])
        assert not store.delete("nonexistent")
        # Existing data should be unaffected
        assert store.exists("A")
        assert store.get_conformers("A") is not None


class TestGetManyConformers:
    def test_get_many_mixed(self, store, confs):
        store.put_conformers("A", [confs[0]])
        store.put_conformers("B", [confs[1]])

        results = store.get_many_conformers(["A", "B", "C"])
        assert len(results) == 3
        assert results[0][1] is not None
        assert results[1][1] is not None
        assert results[2][1] is None

    def test_get_many_empty_list(self, store):
        assert store.get_many_conformers([]) == []
