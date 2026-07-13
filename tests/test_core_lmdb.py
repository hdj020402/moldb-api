"""Tests for LMDB core store."""

import json
import pytest

from moldb.core.lmdb import LMDBMoleculeStore


class TestInit:
    def test_create_new_store(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        assert store.env is not None
        store.close()

    def test_create_with_custom_map_size(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path, map_size=1024 ** 3)
        assert store.map_size == 1024 ** 3
        store.close()

    def test_reopen_existing_store(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        inchi = "InChI=1/CH4/h1H4"
        store.put_conformers(inchi, ["1\n\nC 0 0 0\n"])
        store.close()

        store2 = LMDBMoleculeStore(tmp_lmdb_path)
        assert store2.exists(inchi)
        store2.close()


class TestExists:
    def test_exists_true(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", ["1\n\nC 0 0 0\n"])
        assert store.exists("A")
        store.close()

    def test_exists_false(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        assert not store.exists("nonexistent")
        store.close()


class TestPutGetConformers:
    def test_write_and_read_bare_string(self, tmp_lmdb_path, xyz_single):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        result = store.put_conformers("InChI=1/A", [xyz_single])
        assert result["action"] == "written"
        assert result["count"] == 1

        data = store.get_conformers("InChI=1/A")
        assert data["inchi"] == "InChI=1/A"
        assert data["count"] == 1
        assert data["conformers"][0]["xyz"] == xyz_single
        store.close()

    def test_write_and_read_dict_with_metadata(self, tmp_lmdb_path, conf_with_meta):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("InChI=1/A", [conf_with_meta])

        data = store.get_conformers("InChI=1/A")
        c = data["conformers"][0]
        assert c["xyz"] == conf_with_meta["xyz"]
        assert c["energy"] == conf_with_meta["energy"]
        assert c["source"] == conf_with_meta["source"]
        store.close()

    def test_read_nonexistent(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        assert store.get_conformers("nope") is None
        store.close()

    def test_write_multiple_conformers(self, tmp_lmdb_path, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", xyz_list)
        data = store.get_conformers("A")
        assert data["count"] == 3
        assert len(data["conformers"]) == 3
        store.close()

    def test_skip_empty_conformers(self, tmp_lmdb_path):
        """Empty conformer list — the stream builder skips these,
        but direct put_conformers creates a zero-count entry."""
        store = LMDBMoleculeStore(tmp_lmdb_path)
        result = store.put_conformers("A", [])
        assert result["count"] == 0
        data = store.get_conformers("A")
        assert data["count"] == 0
        assert data["conformers"] == []
        store.close()


class TestPutManyConformers:
    def test_write_many(self, tmp_lmdb_path, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        items = [("A", [xyz_list[0]]), ("B", [xyz_list[1]]), ("C", [xyz_list[2]])]
        stats = store.put_many_conformers(items)
        assert stats["written"] == 3
        assert store.exists("A")
        assert store.exists("B")
        assert store.exists("C")
        store.close()


class TestOnConflict:
    """Tests for all three on_conflict modes."""

    def test_overwrite_replaces(self, tmp_lmdb_path, xyz_single, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", [xyz_single])

        new = xyz_list[1]
        result = store.put_conformers("A", [new], on_conflict="overwrite")
        assert result["action"] == "overwritten"
        assert result["count"] == 1

        data = store.get_conformers("A")
        assert data["conformers"][0]["xyz"] == new
        store.close()

    def test_overwrite_cleans_up_stale_conformers(self, tmp_lmdb_path, xyz_list):
        """When overwriting with fewer conformers, old conf keys are deleted."""
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", xyz_list)  # 3 conformers
        store.put_conformers("A", [xyz_list[0]], on_conflict="overwrite")  # 1 conformer

        data = store.get_conformers("A")
        assert data["count"] == 1
        assert len(data["conformers"]) == 1

        # Verify no stale keys remain
        with store.env.begin() as txn:
            keys = [k.decode() for k, _ in txn.cursor()]
            conf_keys = [k for k in keys if "conf" in k]
            assert len(conf_keys) == 1
        store.close()

    def test_skip_when_exists(self, tmp_lmdb_path, xyz_single, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", [xyz_single])

        result = store.put_conformers("A", [xyz_list[0]], on_conflict="skip")
        assert result["action"] == "skipped"
        assert result["count"] == 1  # old count preserved

        data = store.get_conformers("A")
        assert data["conformers"][0]["xyz"] == xyz_single  # unchanged
        store.close()

    def test_skip_when_not_exists(self, tmp_lmdb_path, xyz_single):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        result = store.put_conformers("A", [xyz_single], on_conflict="skip")
        assert result["action"] == "written"
        store.close()

    def test_merge_appends(self, tmp_lmdb_path, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", [xyz_list[0]], on_conflict="merge")
        result = store.put_conformers("A", [xyz_list[1]], on_conflict="merge")
        assert result["action"] == "merged"
        assert result["count"] == 2

        data = store.get_conformers("A")
        assert data["count"] == 2
        assert data["conformers"][0]["xyz"] == xyz_list[0]
        assert data["conformers"][1]["xyz"] == xyz_list[1]
        store.close()

    def test_merge_does_not_touch_existing_keys(self, tmp_lmdb_path, xyz_list):
        """Merge only writes new keys, never rewrites old ones."""
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", [xyz_list[0], xyz_list[1]])

        with store.env.begin() as txn:
            old_key = txn.get(b"A::conf_000000")

        store.put_conformers("A", [xyz_list[2]], on_conflict="merge")

        with store.env.begin() as txn:
            # Old key unchanged
            assert txn.get(b"A::conf_000000") == old_key
            # New key exists
            assert txn.get(b"A::conf_000002") is not None
        store.close()

    def test_put_many_with_skip(self, tmp_lmdb_path, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_many_conformers([("A", [xyz_list[0]])], on_conflict="overwrite")

        items = [("A", [xyz_list[1]]), ("B", [xyz_list[2]])]
        stats = store.put_many_conformers(items, on_conflict="skip")
        assert stats["skipped"] == 1
        assert stats["written"] == 1
        store.close()

    def test_put_many_with_merge(self, tmp_lmdb_path, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_many_conformers([("A", [xyz_list[0]])])

        items = [("A", [xyz_list[1]]), ("B", [xyz_list[2]])]
        stats = store.put_many_conformers(items, on_conflict="merge")
        assert stats["merged"] == 1
        assert stats["written"] == 1

        data = store.get_conformers("A")
        assert data["count"] == 2
        store.close()


class TestDelete:
    def test_delete_existing(self, tmp_lmdb_path, xyz_single):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", [xyz_single])
        assert store.delete("A")
        assert not store.exists("A")
        assert store.get_conformers("A") is None
        store.close()

    def test_delete_nonexistent(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        assert not store.delete("nope")
        store.close()

    def test_delete_removes_all_conformer_keys(self, tmp_lmdb_path, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", xyz_list)  # 3 conformers
        store.delete("A")

        with store.env.begin() as txn:
            keys = [k.decode() for k, _ in txn.cursor()]
            a_keys = [k for k in keys if k.startswith("A")]
            assert len(a_keys) == 0
        store.close()


class TestLegacyFormatReadback:
    """Ensure old bare-XYZ format is readable."""

    def test_legacy_bare_string(self, tmp_lmdb_path, xyz_single):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        # Simulate old-format write (bare XYZ string, no JSON wrapper)
        with store.env.begin(write=True) as txn:
            txn.put(b"A::meta", json.dumps({"count": 1}).encode())
            txn.put(b"A::conf_000000", xyz_single.encode())

        data = store.get_conformers("A")
        assert data["conformers"][0]["xyz"] == xyz_single
        store.close()


class TestGetManyConformers:
    def test_get_many_mixed(self, tmp_lmdb_path, xyz_list):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        store.put_conformers("A", [xyz_list[0]])
        store.put_conformers("B", [xyz_list[1]])

        results = store.get_many_conformers(["A", "B", "C"])
        assert len(results) == 3
        assert results[0][1] is not None  # A found
        assert results[1][1] is not None  # B found
        assert results[2][1] is None       # C not found
        store.close()

    def test_get_many_empty_list(self, tmp_lmdb_path):
        store = LMDBMoleculeStore(tmp_lmdb_path)
        assert store.get_many_conformers([]) == []
        store.close()
