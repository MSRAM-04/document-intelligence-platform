from fastapi.testclient import TestClient

from app.main import app


def test_health_and_unsupported_upload():
    with TestClient(app) as client:
        api_root = client.get("/api/v1")
        assert api_root.status_code == 200
        assert api_root.json()["health"] == "/api/v1/health"
        assert client.get("/api/v1/health").json()["status"] == "ok"
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("bad.txt", b"not supported", "text/plain")},
            data={"document_type": "invoice"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
