from dataclasses import dataclass
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from auth import get_current_user, get_current_admin

client = TestClient(app)


@dataclass
class FakeUser:
    id: str = "admin-1"
    email: str = "fake-admin@example.com"


app.dependency_overrides[get_current_user] = lambda: FakeUser()
app.dependency_overrides[get_current_admin] = lambda: FakeUser()


def test_admin_list_documents_joins_pack_names():
    with patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(
            data=[{"pack_id": "aml", "name": "AML Compliance"}]
        )
        mock_sb.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "d1", "pack_id": "aml", "filename": "f.pdf", "status": "ready",
                   "error": None, "chunk_count": 3, "created_at": "2026-01-01T00:00:00Z"}]
        )
        response = client.get("/api/v1/admin/documents")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["pack_name"] == "AML Compliance"


def test_admin_list_data_files_returns_empty_list_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DSSTAR", str(tmp_path / "does-not-exist"))
    response = client.get("/api/v1/admin/data-files")
    assert response.status_code == 200
    assert response.json() == []


def test_admin_list_data_files_lists_files_in_the_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DSSTAR", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "transactions.csv").write_text("a,b\n1,2\n")

    response = client.get("/api/v1/admin/data-files")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "transactions.csv"
    assert body[0]["size_bytes"] > 0
