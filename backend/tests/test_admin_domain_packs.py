from dataclasses import dataclass
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

import domain_pack_admin
from main import app
from auth import get_current_user, get_current_admin

client = TestClient(app)


@dataclass
class FakeUser:
    id: str = "00000000-0000-0000-0000-000000000001"
    email: str = "fake-admin@example.com"


app.dependency_overrides[get_current_user] = lambda: FakeUser()
app.dependency_overrides[get_current_admin] = lambda: FakeUser()


# --- domain_pack_admin.py unit tests -----------------------------------------------

def test_create_pack_inserts_row_with_editable_fields_only():
    mock_result = MagicMock()
    mock_result.data = [{"pack_id": "new-pack", "name": "New Pack"}]
    with patch("domain_pack_admin.supabase") as mock_sb:
        mock_sb.table.return_value.insert.return_value.execute.return_value = mock_result
        row = domain_pack_admin.create_pack("new-pack", {"name": "New Pack", "not_a_real_field": "x"})

    inserted = mock_sb.table.return_value.insert.call_args[0][0]
    assert inserted == {"pack_id": "new-pack", "name": "New Pack"}
    assert row == {"pack_id": "new-pack", "name": "New Pack"}


def test_update_pack_only_sends_editable_fields():
    mock_result = MagicMock()
    mock_result.data = [{"pack_id": "p", "name": "Renamed"}]
    with patch("domain_pack_admin.supabase") as mock_sb:
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result
        row = domain_pack_admin.update_pack("p", {"name": "Renamed", "pack_id": "should-be-dropped"})

    updated = mock_sb.table.return_value.update.call_args[0][0]
    assert updated == {"name": "Renamed"}
    assert row == {"pack_id": "p", "name": "Renamed"}


def test_update_pack_returns_none_when_no_row_matched():
    mock_result = MagicMock()
    mock_result.data = []
    with patch("domain_pack_admin.supabase") as mock_sb:
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_result
        assert domain_pack_admin.update_pack("missing", {"name": "x"}) is None


def test_delete_pack_resets_active_pack_to_generic_if_it_was_active():
    active_result = MagicMock()
    active_result.data = [{"value": "p"}]
    with patch("domain_pack_admin.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = active_result
        domain_pack_admin.delete_pack("p")

    mock_sb.table.return_value.delete.return_value.eq.assert_called_once_with("pack_id", "p")
    mock_sb.table.return_value.upsert.assert_called_once_with(
        {"key": "active_domain_pack", "value": "generic"}
    )


def test_delete_pack_leaves_active_setting_alone_if_a_different_pack_is_active():
    active_result = MagicMock()
    active_result.data = [{"value": "some-other-pack"}]
    with patch("domain_pack_admin.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = active_result
        domain_pack_admin.delete_pack("p")

    mock_sb.table.return_value.upsert.assert_not_called()


# --- /api/v1/admin/domain_packs route tests --------------------------------------------

def test_admin_list_domain_packs_works_even_when_the_feature_flag_is_off():
    """The public list endpoint 403s while the domain_packs flag is off — this admin
    variant must not, or an admin can never manage the catalog while the feature is
    disabled (e.g. seeding packs before turning it on)."""
    mock_rows = MagicMock()
    mock_rows.data = [{
        "pack_id": "p", "name": "Pack", "description": "", "tags": [],
        "dataset_generator": None, "example_question": None,
    }]
    with patch("domain_pack._feature_enabled", return_value=False), \
         patch("main.supabase") as mock_sb:
        mock_sb.table.return_value.select.return_value.neq.return_value.order.return_value.execute.return_value = mock_rows
        response = client.get("/api/v1/admin/domain_packs")

    assert response.status_code == 200
    assert response.json() == [{
        "id": "p", "name": "Pack", "description": "", "tags": [],
        "has_dataset_generator": False, "example_question": None, "active": False,
    }]


def test_admin_list_domain_packs_requires_admin():
    app.dependency_overrides.pop(get_current_admin, None)
    try:
        response = client.get("/api/v1/admin/domain_packs")
        assert response.status_code == 403
    finally:
        app.dependency_overrides[get_current_admin] = lambda: FakeUser()


def test_create_domain_pack_rejects_generic_pack_id():
    response = client.post("/api/v1/admin/domain_packs", json={"pack_id": "generic", "name": "x"})
    assert response.status_code == 422


def test_create_domain_pack_rejects_duplicate_pack_id():
    with patch("main._get_domain_pack_row", return_value={"pack_id": "existing"}):
        response = client.post("/api/v1/admin/domain_packs", json={"pack_id": "existing", "name": "x"})
    assert response.status_code == 409


def test_create_domain_pack_succeeds():
    created = {"pack_id": "new-pack", "name": "New Pack"}
    with patch("main._get_domain_pack_row", return_value=None), \
         patch("main.domain_pack_admin.create_pack", return_value=created) as mock_create:
        response = client.post("/api/v1/admin/domain_packs", json={"pack_id": "new-pack", "name": "New Pack"})

    assert response.status_code == 200
    assert response.json() == created
    mock_create.assert_called_once()
    assert mock_create.call_args[0][0] == "new-pack"


def test_update_domain_pack_404s_when_missing():
    with patch("main._get_domain_pack_row", return_value=None):
        response = client.put("/api/v1/admin/domain_packs/missing", json={"name": "x"})
    assert response.status_code == 404


def test_update_domain_pack_only_forwards_fields_the_caller_set():
    with patch("main._get_domain_pack_row", return_value={"pack_id": "p"}), \
         patch("main.domain_pack_admin.update_pack", return_value={"pack_id": "p", "name": "x"}) as mock_update:
        response = client.put("/api/v1/admin/domain_packs/p", json={"name": "x"})

    assert response.status_code == 200
    mock_update.assert_called_once_with("p", {"name": "x"})


def test_delete_domain_pack_rejects_generic():
    response = client.delete("/api/v1/admin/domain_packs/generic")
    assert response.status_code == 422


def test_delete_domain_pack_404s_when_missing():
    with patch("main._get_domain_pack_row", return_value=None):
        response = client.delete("/api/v1/admin/domain_packs/missing")
    assert response.status_code == 404


def test_delete_domain_pack_succeeds():
    with patch("main._get_domain_pack_row", return_value={"pack_id": "p"}), \
         patch("main.domain_pack_admin.delete_pack") as mock_delete:
        response = client.delete("/api/v1/admin/domain_packs/p")

    assert response.status_code == 200
    assert response.json() == {"status": "deleted"}
    mock_delete.assert_called_once_with("p")


def test_create_domain_pack_requires_admin():
    app.dependency_overrides.pop(get_current_admin, None)
    try:
        response = client.post("/api/v1/admin/domain_packs", json={"pack_id": "x", "name": "x"})
        assert response.status_code == 403
    finally:
        app.dependency_overrides[get_current_admin] = lambda: FakeUser()
