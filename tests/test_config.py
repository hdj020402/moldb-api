"""Tests for config module."""

import json
import pytest


class TestApiSettings:
    def test_default_path(self):
        from moldb.config import ApiSettings
        settings = ApiSettings()
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.lmdb_map_size == 30 * 1024 ** 3

    def test_custom_path(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({
            "storage": {"map_size_gb": 10},
            "api": {
                "host": "127.0.0.1",
                "port": 9000,
            }
        }))
        from moldb.config import ApiSettings
        settings = ApiSettings(config_path=str(cfg))
        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.lmdb_map_size == 10 * 1024 ** 3

    def test_missing_file_uses_defaults(self):
        from moldb.config import ApiSettings
        settings = ApiSettings(config_path="/nonexistent/config.json")
        assert settings.host == "0.0.0.0"
        assert settings.lmdb_path == "molecules.lmdb"

    def test_invalid_port_raises(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"api": {"port": 99999}}))
        from moldb.config import ApiSettings
        with pytest.raises(ValueError, match="port must be 1-65535"):
            ApiSettings(config_path=str(cfg))

    def test_invalid_map_size_raises(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"storage": {"map_size_gb": 0}}))
        from moldb.config import ApiSettings
        with pytest.raises(ValueError, match="map_size"):
            ApiSettings(config_path=str(cfg))

    def test_logging_defaults(self):
        from moldb.config import ApiSettings
        settings = ApiSettings()
        assert settings.log_level == "INFO"
        assert settings.log_file is None

    def test_logging_custom(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({
            "api": {
                "logging": {"level": "DEBUG", "file": "logs/api.log"},
            }
        }))
        from moldb.config import ApiSettings
        settings = ApiSettings(config_path=str(cfg))
        assert settings.log_level == "DEBUG"
        assert settings.log_file == "logs/api.log"

    def test_invalid_log_level_raises(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"api": {"logging": {"level": "TRACE"}}}))
        from moldb.config import ApiSettings
        with pytest.raises(ValueError, match="log_level"):
            ApiSettings(config_path=str(cfg))


class TestUnknownKeyWarning:
    def test_unknown_top_level_key_warns(self, tmp_path, caplog):
        import logging
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"badkey": 1}))
        from moldb.config import ApiSettings
        with caplog.at_level(logging.WARNING, logger="moldb.config"):
            ApiSettings(config_path=str(cfg))
        assert "badkey" in caplog.text
        assert "<root>" in caplog.text

    def test_known_keys_no_warning(self, tmp_path, caplog):
        import logging
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"storage": {"path": "db.lmdb"}}))
        from moldb.config import ApiSettings
        with caplog.at_level(logging.WARNING, logger="moldb.config"):
            ApiSettings(config_path=str(cfg))
        assert caplog.text == ""


class TestBuilderSettings:
    def test_default_path(self):
        from moldb.config import BuilderSettings
        settings = BuilderSettings()
        assert settings.on_conflict == "overwrite"
        assert settings.batch_size == 1000
        assert settings.xyz_path_column == "xyz_path"
        assert settings.inchi_column == "fixed_h_inchi"
        assert settings.mapping_file is None

    def test_custom_path(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({
            "builder": {
                "batch_size": 500,
                "on_conflict": "skip",
                "mapping": {
                    "file": "/data/mapping.csv",
                    "xyz_path_column": "path",
                },
            }
        }))
        from moldb.config import BuilderSettings
        settings = BuilderSettings(config_path=str(cfg))
        assert settings.batch_size == 500
        assert settings.on_conflict == "skip"
        assert settings.mapping_file == "/data/mapping.csv"
        assert settings.xyz_path_column == "path"
        assert settings.inchi_column == "fixed_h_inchi"

    def test_missing_file_uses_defaults(self):
        from moldb.config import BuilderSettings
        settings = BuilderSettings(config_path="/nonexistent/config.json")
        assert settings.lmdb_map_size == 30 * 1024 ** 3

    def test_invalid_batch_size_raises(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"builder": {"batch_size": 0}}))
        from moldb.config import BuilderSettings
        with pytest.raises(ValueError, match="batch_size"):
            BuilderSettings(config_path=str(cfg))

    def test_invalid_on_conflict_raises(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"builder": {"on_conflict": "delete"}}))
        from moldb.config import BuilderSettings
        with pytest.raises(ValueError, match="on_conflict"):
            BuilderSettings(config_path=str(cfg))

    def test_logging_defaults(self):
        from moldb.config import BuilderSettings
        settings = BuilderSettings()
        assert settings.log_level == "INFO"
        assert settings.log_file is None

    def test_logging_custom(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({
            "builder": {
                "logging": {"level": "WARNING", "file": "logs/build.log"},
                "mapping": {"file": "test.csv"},
            }
        }))
        from moldb.config import BuilderSettings
        settings = BuilderSettings(config_path=str(cfg))
        assert settings.log_level == "WARNING"
        assert settings.log_file == "logs/build.log"

    def test_invalid_log_level_raises(self, tmp_path):
        cfg = tmp_path / "cfg.json"
        cfg.write_text(json.dumps({"builder": {"logging": {"level": "OFF"}}}))
        from moldb.config import BuilderSettings
        with pytest.raises(ValueError, match="log_level"):
            BuilderSettings(config_path=str(cfg))
