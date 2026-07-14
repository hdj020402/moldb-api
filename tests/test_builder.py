"""Tests for builder stream functions."""

import pytest

from moldb.build import build_stream
from moldb.store import MoleculeStore


class TestBuildStream:
    def test_write_new_molecules(self, tmp_db_path, confs):
        items = [
            ("InChI=1/A", [confs[0]]),
            ("InChI=1/B", [confs[1]]),
        ]
        stats = build_stream(items, tmp_db_path)
        assert stats["written"] == 2
        assert stats["processed"] == 2

        store = MoleculeStore(tmp_db_path)
        assert store.exists("InChI=1/A")
        assert store.exists("InChI=1/B")
        store.close()

    def test_write_with_metadata(self, tmp_db_path, conf_with_meta):
        items = [("A", [conf_with_meta])]
        stats = build_stream(items, tmp_db_path)
        assert stats["written"] == 1

        store = MoleculeStore(tmp_db_path)
        data = store.get_conformers("A")
        assert data["conformers"][0]["energy"] == conf_with_meta["energy"]
        store.close()

    def test_skip_existing(self, tmp_db_path, confs):
        build_stream([("A", [confs[0]])], tmp_db_path)
        stats = build_stream(
            [("A", [confs[1]])],
            tmp_db_path,
            on_conflict="skip",
        )
        assert stats["skipped"] == 1
        assert stats["written"] == 0

    def test_merge_streaming(self, tmp_db_path, confs):
        """Simulate streaming: each conformer arrives separately."""
        for c in confs:
            build_stream(
                [("A", [c])],
                tmp_db_path,
                on_conflict="merge",
            )

        store = MoleculeStore(tmp_db_path)
        data = store.get_conformers("A")
        assert data["count"] == len(confs)
        store.close()

    def test_overwrite_default(self, tmp_db_path, confs):
        build_stream([("A", [confs[0], confs[1]])], tmp_db_path)
        build_stream([("A", [confs[2]])], tmp_db_path)

        store = MoleculeStore(tmp_db_path)
        data = store.get_conformers("A")
        assert data["count"] == 1
        store.close()

    def test_large_batch(self, tmp_db_path, conf):
        """Write more molecules than batch_size to force multiple batches."""
        n = 20
        items = [(f"mol_{i}", [conf]) for i in range(n)]
        stats = build_stream(items, tmp_db_path, batch_size=5)
        assert stats["written"] == n

    def test_returns_enriched_stats(self, tmp_db_path, conf):
        build_stream([("A", [conf])], tmp_db_path)
        stats = build_stream(
            [("A", [conf]), ("B", [conf])],
            tmp_db_path,
            on_conflict="skip",
        )
        for key in ("processed", "written", "skipped", "overwritten",
                     "merged", "conformers", "time_seconds"):
            assert key in stats


class TestBuilderCommon:
    """Tests for builder helper functions."""

    def test__log_progress(self, caplog):
        import logging
        from moldb.build import _log_progress
        logger = logging.getLogger("moldb.test.log_progress")
        result = {"written": 5, "overwritten": 2, "skipped": 1, "merged": 3}
        with caplog.at_level(logging.INFO, logger="moldb.test.log_progress"):
            _log_progress(logger, 10.5, 100, 9.5, result, 0.5)
        captured = caplog.text
        assert "W:5" in captured
        assert "O:2" in captured
        assert "S:1" in captured
        assert "M:3" in captured

    def test_log_progress_no_optional_fields(self, caplog):
        import logging
        from moldb.build import _log_progress
        logger = logging.getLogger("moldb.test.log_progress")
        result = {"written": 5, "overwritten": 0}
        with caplog.at_level(logging.INFO, logger="moldb.test.log_progress"):
            _log_progress(logger, 10.5, 100, 9.5, result, 0.5)
        captured = caplog.text
        assert "W:5" in captured
        # Skipped/merged not shown when zero
        assert "S:" not in captured
        assert "M:" not in captured


class TestFlushBatch:
    """Tests for the flush_batch shared helper."""

    def test_flush_batch_updates_stats(self, tmp_db_path, confs):
        from moldb.build import _flush_batch
        from moldb.store import MoleculeStore

        store = MoleculeStore(tmp_db_path)
        stats = {"written": 0, "overwritten": 0, "skipped": 0, "merged": 0}
        batch = [("A", [confs[0]]), ("B", [confs[1]])]
        result, batch_time = _flush_batch(store, batch, "overwrite", stats)
        assert result["written"] == 2
        assert stats["written"] == 2
        assert batch_time >= 0
        store.close()

    def test_flush_batch_merge(self, tmp_db_path, confs):
        from moldb.build import _flush_batch
        from moldb.store import MoleculeStore

        store = MoleculeStore(tmp_db_path)
        stats = {"written": 0, "overwritten": 0, "skipped": 0, "merged": 0}
        _flush_batch(store, [("A", [confs[0]])], "overwrite", stats)
        _flush_batch(store, [("A", [confs[1]])], "merge", stats)
        assert stats["written"] == 1
        assert stats["merged"] == 1
        store.close()


class TestTotalProcessed:
    def test_total_processed(self):
        from moldb.build import _total_processed
        stats = {"written": 3, "overwritten": 1, "skipped": 2, "merged": 4}
        assert _total_processed(stats) == 10


class TestIterMapping:
    """Tests for iter_mapping with real CSV files."""

    def test_reads_csv_mapping(self, tmp_path):
        import csv
        from moldb.build import iter_mapping

        xyz_file = tmp_path / "mol1.xyz"
        xyz_file.write_text("1\n\nC  0.0 0.0 0.0\n")

        mapping_file = tmp_path / "mapping.csv"
        with open(mapping_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["xyz_path", "fixed_h_inchi"])
            writer.writerow([str(xyz_file), "InChI=1/A"])

        results = list(iter_mapping(
            str(mapping_file),
            xyz_path_column="xyz_path",
            inchi_column="fixed_h_inchi",
        ))

        assert len(results) == 1
        inchi, conformers = results[0]
        assert inchi == "InChI=1/A"
        assert len(conformers) == 1
        assert "xyz" in conformers[0]
        assert "C" in conformers[0]["xyz"]

    def test_multi_conformer_grouping(self, tmp_path):
        import csv
        from moldb.build import iter_mapping

        xyz1 = tmp_path / "mol1.xyz"
        xyz2 = tmp_path / "mol2.xyz"
        xyz1.write_text("1\n\nC  0.0 0.0 0.0\n")
        xyz2.write_text("1\n\nC  0.0 0.0 1.0\n")

        mapping_file = tmp_path / "mapping.csv"
        with open(mapping_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["xyz_path", "fixed_h_inchi"])
            writer.writerow([str(xyz1), "InChI=1/A"])
            writer.writerow([str(xyz2), "InChI=1/A"])

        results = list(iter_mapping(
            str(mapping_file),
            xyz_path_column="xyz_path",
            inchi_column="fixed_h_inchi",
        ))

        assert len(results) == 1
        inchi, conformers = results[0]
        assert len(conformers) == 2

    def test_missing_columns_raises(self, tmp_path):
        import csv
        from moldb.build import iter_mapping

        mapping_file = tmp_path / "bad.csv"
        with open(mapping_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["wrong_col", "also_wrong"])
            writer.writerow(["a", "b"])

        with pytest.raises(ValueError):
            list(iter_mapping(
                str(mapping_file),
                xyz_path_column="xyz_path",
                inchi_column="fixed_h_inchi",
            ))

    def test_missing_xyz_file_raises_with_context(self, tmp_path):
        import csv
        from moldb.build import iter_mapping

        mapping_file = tmp_path / "mapping.csv"
        with open(mapping_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["xyz_path", "fixed_h_inchi"])
            writer.writerow(["/nonexistent/path/mol.xyz", "InChI=1/A"])

        with pytest.raises(FileNotFoundError, match="XYZ file not found"):
            list(iter_mapping(
                str(mapping_file),
                xyz_path_column="xyz_path",
                inchi_column="fixed_h_inchi",
            ))


class TestBuildFromMapping:
    """End-to-end tests: CSV mapping file → build_from_mapping → verify DB."""

    def test_full_pipeline(self, tmp_path):
        import csv
        from moldb.build import build_from_mapping
        from moldb.store import MoleculeStore

        # Create XYZ files
        xyz_a = tmp_path / "mol_a.xyz"
        xyz_b1 = tmp_path / "mol_b_conf1.xyz"
        xyz_b2 = tmp_path / "mol_b_conf2.xyz"
        xyz_a.write_text("1\n\nC  0.0 0.0 0.0\n")
        xyz_b1.write_text("1\n\nN  0.0 0.0 0.0\n")
        xyz_b2.write_text("1\n\nN  0.0 0.0 1.0\n")

        # Create CSV mapping
        mapping_file = tmp_path / "mapping.csv"
        with open(mapping_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["xyz_path", "fixed_h_inchi"])
            writer.writerow([str(xyz_a), "InChI=1/A"])
            writer.writerow([str(xyz_b1), "InChI=1/B"])
            writer.writerow([str(xyz_b2), "InChI=1/B"])

        db_path = str(tmp_path / "test.lmdb")
        stats = build_from_mapping(
            str(mapping_file), db_path,
            xyz_path_column="xyz_path",
            inchi_column="fixed_h_inchi",
        )

        assert stats["written"] == 2
        assert stats["conformers"] == 3

        # Verify DB contents
        store = MoleculeStore(db_path)
        data_a = store.get_conformers("InChI=1/A")
        assert data_a["count"] == 1
        assert "C" in data_a["conformers"][0]["xyz"]

        data_b = store.get_conformers("InChI=1/B")
        assert data_b["count"] == 2
        assert len(data_b["conformers"]) == 2
        store.close()

    def test_full_pipeline_with_conflict_skip(self, tmp_path):
        import csv
        from moldb.build import build_from_mapping
        from moldb.store import MoleculeStore

        xyz1 = tmp_path / "mol1.xyz"
        xyz1.write_text("1\n\nC  0.0 0.0 0.0\n")

        mapping1 = tmp_path / "mapping1.csv"
        with open(mapping1, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["path_col", "inchi_col"])
            writer.writerow([str(xyz1), "InChI=1/A"])

        db_path = str(tmp_path / "test.lmdb")

        # First build writes A
        stats1 = build_from_mapping(
            str(mapping1), db_path,
            xyz_path_column="path_col",
            inchi_column="inchi_col",
        )
        assert stats1["written"] == 1

        # Second build with skip should skip A
        xyz2 = tmp_path / "mol2.xyz"
        xyz2.write_text("1\n\nO  0.0 0.0 0.0\n")
        mapping2 = tmp_path / "mapping2.csv"
        with open(mapping2, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["path_col", "inchi_col"])
            writer.writerow([str(xyz2), "InChI=1/A"])  # same InChI, different file
            writer.writerow([str(xyz2), "InChI=1/B"])  # new InChI

        stats2 = build_from_mapping(
            str(mapping2), db_path,
            on_conflict="skip",
            xyz_path_column="path_col",
            inchi_column="inchi_col",
        )
        assert stats2["skipped"] == 1
        assert stats2["written"] == 1

        store = MoleculeStore(db_path)
        assert store.exists("InChI=1/A")
        assert store.exists("InChI=1/B")
        store.close()
