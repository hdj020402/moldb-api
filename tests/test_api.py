"""Tests for API models and validation."""

import pytest
from pydantic import ValidationError

from moldb.server import BatchMoleculeRequest, MoleculeResponse, create_app


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
        from moldb.store import MoleculeStore
        from moldb import __version__
        import tempfile, os

        with tempfile.TemporaryDirectory() as d:
            db_path = os.path.join(d, "test.lmdb")
            app = create_app(
                title="test-app",
                version=__version__,
                store_factory=lambda: MoleculeStore(db_path),
            )
            assert app.title == "test-app"
            assert app.version == __version__
            assert app.router.lifespan_context is not None


class TestApiEndpoints:
    """Integration tests using FastAPI TestClient."""

    @pytest.fixture
    def client(self, tmp_db_path, conf):
        pytest.importorskip("httpx", reason="httpx required for TestClient")
        from fastapi.testclient import TestClient
        from moldb.server import create_app
        from moldb.store import MoleculeStore
        from moldb import __version__

        store = MoleculeStore(tmp_db_path)
        store.put_conformers("InChI=1/H2O/h1H2", [conf])
        store.close()

        app = create_app(
            title="test-api",
            version=__version__,
            store_factory=lambda: MoleculeStore(tmp_db_path),
        )
        with TestClient(app) as c:
            yield c

    def test_health_check(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "database" in data

    def test_get_molecule_found(self, client, xyz_single):
        response = client.get("/molecule/InChI=1/H2O/h1H2")
        assert response.status_code == 200
        data = response.json()
        assert data["inchi"] == "InChI=1/H2O/h1H2"
        assert data["count"] == 1
        assert len(data["conformers"]) == 1
        assert data["conformers"][0]["xyz"] == xyz_single

    def test_get_molecule_not_found(self, client):
        response = client.get("/molecule/InChI=1/NOPE")
        assert response.status_code == 404
        assert response.json() == {"detail": "Molecule not found"}

    def test_batch_query(self, client):
        response = client.post(
            "/molecules/batch",
            json={"inchis": ["InChI=1/H2O/h1H2", "InChI=1/NOPE"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "InChI=1/H2O/h1H2" in data
        assert data["InChI=1/H2O/h1H2"] is not None
        assert data["InChI=1/H2O/h1H2"]["count"] == 1
        assert data["InChI=1/NOPE"] is None

    def test_batch_query_empty_list(self, client):
        response = client.post(
            "/molecules/batch",
            json={"inchis": []},
        )
        assert response.status_code == 422

    def test_get_molecule_url_encoded(self, client):
        response = client.get(
            "/molecule/InChI%3D1%2FH2O%2Fh1H2"
        )
        assert response.status_code == 200
