"""Tests for LMDB core store."""

import pytest

from moldb.store import MoleculeStore


class TestInit:
    def test_create_new_store(self, tmp_db_path):
        store = MoleculeStore(tmp_db_path)
        assert store.env is not None
        store.close()

    def test_create_with_custom_map_size(self, tmp_db_path):
        store = MoleculeStore(tmp_db_path, map_size=1024 ** 3)
        assert store.map_size == 1024 ** 3
        store.close()

    def test_reopen_existing_store(self, tmp_db_path, conf):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("InChI=1/A", [conf])
        store.close()

        store2 = MoleculeStore(tmp_db_path)
        assert store2.exists("InChI=1/A")
        store2.close()


class TestExists:
    def test_exists_true(self, tmp_db_path, conf):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf])
        assert store.exists("A")
        store.close()

    def test_exists_false(self, tmp_db_path):
        store = MoleculeStore(tmp_db_path)
        assert not store.exists("nonexistent")
        store.close()


class TestPutGetConformers:
    def test_write_and_read(self, tmp_db_path, conf, xyz_single):
        store = MoleculeStore(tmp_db_path)
        result = store.put_conformers("InChI=1/A", [conf])
        assert result["action"] == "written"
        assert result["count"] == 1

        data = store.get_conformers("InChI=1/A")
        assert data["inchi"] == "InChI=1/A"
        assert data["count"] == 1
        assert data["conformers"][0]["xyz"] == xyz_single
        store.close()

    def test_write_and_read_with_metadata(self, tmp_db_path, conf_with_meta):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf_with_meta])

        data = store.get_conformers("A")
        c = data["conformers"][0]
        assert c["xyz"] == conf_with_meta["xyz"]
        assert c["energy"] == conf_with_meta["energy"]
        assert c["source"] == conf_with_meta["source"]
        store.close()

    def test_read_nonexistent(self, tmp_db_path):
        store = MoleculeStore(tmp_db_path)
        assert store.get_conformers("nope") is None
        store.close()

    def test_write_multiple_conformers(self, tmp_db_path, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", confs)
        data = store.get_conformers("A")
        assert data["count"] == len(confs)
        assert len(data["conformers"]) == len(confs)
        store.close()


class TestPutManyConformers:
    def test_write_many(self, tmp_db_path, confs):
        store = MoleculeStore(tmp_db_path)
        items = [("A", [confs[0]]), ("B", [confs[1]]), ("C", [confs[2]])]
        stats = store.put_many_conformers(items)
        assert stats["written"] == 3
        assert store.exists("A")
        assert store.exists("B")
        assert store.exists("C")
        store.close()


class TestOnConflict:
    def test_overwrite_replaces(self, tmp_db_path, conf, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf])
        result = store.put_conformers("A", [confs[1]], on_conflict="overwrite")
        assert result["action"] == "overwritten"
        assert result["count"] == 1

        data = store.get_conformers("A")
        assert data["conformers"][0]["xyz"] == confs[1]["xyz"]
        store.close()

    def test_overwrite_cleans_up_stale_conformers(self, tmp_db_path, confs):
        """When overwriting with fewer conformers, old conf keys are deleted."""
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", confs)  # 3 conformers
        store.put_conformers("A", [confs[0]], on_conflict="overwrite")  # 1

        data = store.get_conformers("A")
        assert data["count"] == 1

        with store.env.begin() as txn:
            keys = [k.decode() for k, _ in txn.cursor()]
            conf_keys = [k for k in keys if "conf" in k]
            assert len(conf_keys) == 1
        store.close()

    def test_skip_when_exists(self, tmp_db_path, conf, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf])

        result = store.put_conformers("A", [confs[0]], on_conflict="skip")
        assert result["action"] == "skipped"
        assert result["count"] == 1  # old count preserved

        data = store.get_conformers("A")
        assert data["conformers"][0]["xyz"] == conf["xyz"]  # unchanged
        store.close()

    def test_skip_when_not_exists(self, tmp_db_path, conf):
        store = MoleculeStore(tmp_db_path)
        result = store.put_conformers("A", [conf], on_conflict="skip")
        assert result["action"] == "written"
        store.close()

    def test_merge_appends(self, tmp_db_path, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [confs[0]], on_conflict="merge")
        result = store.put_conformers("A", [confs[1]], on_conflict="merge")
        assert result["action"] == "merged"
        assert result["count"] == 2

        data = store.get_conformers("A")
        assert data["count"] == 2
        assert data["conformers"][0]["xyz"] == confs[0]["xyz"]
        assert data["conformers"][1]["xyz"] == confs[1]["xyz"]
        store.close()

    def test_merge_does_not_touch_existing_keys(self, tmp_db_path, confs):
        """Merge only writes new keys, never rewrites old ones."""
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [confs[0], confs[1]])

        with store.env.begin() as txn:
            old_key = txn.get(b"A::conf_000000")

        store.put_conformers("A", [confs[2]], on_conflict="merge")

        with store.env.begin() as txn:
            assert txn.get(b"A::conf_000000") == old_key
            assert txn.get(b"A::conf_000002") is not None
        store.close()

    def test_put_many_with_skip(self, tmp_db_path, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_many_conformers([("A", [confs[0]])])

        items = [("A", [confs[1]]), ("B", [confs[2]])]
        stats = store.put_many_conformers(items, on_conflict="skip")
        assert stats["skipped"] == 1
        assert stats["written"] == 1
        store.close()

    def test_put_many_with_merge(self, tmp_db_path, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_many_conformers([("A", [confs[0]])])

        items = [("A", [confs[1]]), ("B", [confs[2]])]
        stats = store.put_many_conformers(items, on_conflict="merge")
        assert stats["merged"] == 1
        assert stats["written"] == 1

        data = store.get_conformers("A")
        assert data["count"] == 2
        store.close()


class TestDelete:
    def test_delete_existing(self, tmp_db_path, conf):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf])
        assert store.delete("A")
        assert not store.exists("A")
        assert store.get_conformers("A") is None
        store.close()

    def test_delete_nonexistent(self, tmp_db_path):
        store = MoleculeStore(tmp_db_path)
        assert not store.delete("nope")
        store.close()

    def test_delete_removes_all_conformer_keys(self, tmp_db_path, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", confs)
        store.delete("A")

        with store.env.begin() as txn:
            keys = [k.decode() for k, _ in txn.cursor()]
            a_keys = [k for k in keys if k.startswith("A")]
            assert len(a_keys) == 0
        store.close()


class TestContextManager:
    def test_enter_exit(self, tmp_db_path, conf):
        with MoleculeStore(tmp_db_path) as store:
            store.put_conformers("A", [conf])
            assert store.exists("A")
        # After exit, store should be closed
        with MoleculeStore(tmp_db_path) as store2:
            assert store2.exists("A")

    def test_exception_does_not_leak_resources(self, tmp_db_path, conf):
        try:
            with MoleculeStore(tmp_db_path) as store:
                store.put_conformers("A", [conf])
                raise ValueError("test error")
        except ValueError:
            pass
        # Store should still be closed; reopened store can access data
        with MoleculeStore(tmp_db_path) as store2:
            assert store2.exists("A")


class TestDeleteTransaction:
    def test_delete_nonexistent_no_write_txn(self, tmp_db_path):
        """Delete of non-existent key should not create an empty write txn."""
        with MoleculeStore(tmp_db_path) as store:
            # Verify delete returns False for non-existent
            assert not store.delete("nonexistent")
            # Verify the store is still usable
            assert store.get_conformers("nonexistent") is None


class TestGetManyConformers:
    def test_get_many_mixed(self, tmp_db_path, confs):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [confs[0]])
        store.put_conformers("B", [confs[1]])

        results = store.get_many_conformers(["A", "B", "C"])
        assert len(results) == 3
        assert results[0][1] is not None
        assert results[1][1] is not None
        assert results[2][1] is None
        store.close()

    def test_get_many_empty_list(self, tmp_db_path):
        store = MoleculeStore(tmp_db_path)
        assert store.get_many_conformers([]) == []
        store.close()


class TestGetConformersEdgeCases:
    def test_missing_conformer_key_skipped(self, tmp_db_path, conf):
        """If a conformer slot is missing, it's skipped (not None)."""
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf, conf])

        # Manually delete one conformer key to simulate corruption
        with store.env.begin(write=True) as txn:
            txn.delete(b"A::conf_000000")

        data = store.get_conformers("A")
        assert data is not None
        assert data["count"] == 2  # meta says 2
        assert len(data["conformers"]) == 1  # but only 1 found
        assert data["conformers"][0] is not None
        store.close()

    def test_get_many_with_missing_conformer(self, tmp_db_path, conf):
        """Batch retrieval skips missing conformer slots."""
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf, conf])
        with store.env.begin(write=True) as txn:
            txn.delete(b"A::conf_000000")

        results = store.get_many_conformers(["A"])
        assert len(results) == 1
        _, data = results[0]
        assert data is not None
        assert len(data["conformers"]) == 1
        store.close()


class TestInvalidOnConflict:
    def test_put_conformers_invalid_mode_raises(self, tmp_db_path, conf):
        store = MoleculeStore(tmp_db_path)
        # Write first so the molecule exists — on_conflict only matters on conflict
        store.put_conformers("A", [conf])
        with pytest.raises(ValueError, match="invalid on_conflict"):
            store.put_conformers("A", [conf], on_conflict="append")
        store.close()

    def test_put_many_invalid_mode_raises(self, tmp_db_path, conf):
        store = MoleculeStore(tmp_db_path)
        store.put_conformers("A", [conf])
        with pytest.raises(ValueError, match="invalid on_conflict"):
            store.put_many_conformers([("A", [conf])], on_conflict="replace")
        store.close()
