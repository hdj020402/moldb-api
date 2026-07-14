"""Tests for API models and validation."""

import pytest
from pydantic import ValidationError

from moldb.api.common import BatchMoleculeRequest, MoleculeResponse, create_app


class TestBatchMoleculeRequest:
    def test_valid_request(self):
        req = BatchMoleculeRequest(inchis=["InChI=1/A", "InChI=1/B"])
        assert req.inchis == ["InChI=1/A", "InChI=1/B"]

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            BatchMoleculeRequest(inchis=[])

    def test_none_rejected(self):
        with pytest.raises(ValidationError):
            BatchMoleculeRequest(inchis=None)


class TestMoleculeResponse:
    def test_valid_response(self):
        resp = MoleculeResponse(
            inchi="InChI=1/A",
            count=2,
            conformers=[{"xyz": "..."}, {"xyz": "..."}],
        )
        assert resp.inchi == "InChI=1/A"
        assert resp.count == 2
        assert len(resp.conformers) == 2

    def test_empty_conformers(self):
        resp = MoleculeResponse(inchi="InChI=1/A", count=0, conformers=[])
        assert resp.count == 0


class TestCreateApp:
    def test_creates_fastapi_app(self):
        from moldb.core.lmdb import LMDBMoleculeStore
        import tempfile, os

        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "test.lmdb")
            app = create_app(
                title="test-app",
                version="0.3.0",
                store_factory=lambda: LMDBMoleculeStore(db_path),
            )
            assert app.title == "test-app"
            assert app.version == "0.3.0"
            # Lifespan context manager exists
            assert app.router.lifespan_context is not None
