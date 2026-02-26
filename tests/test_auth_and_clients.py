from datetime import datetime, timezone

from app.models import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_required_for_clients(client):
    response = client.get("/api/v1/clients")
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "auth_required"


def test_sync_creates_user(client):
    response = client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is True
    assert body["user"]["firebase_uid"] == "uid-1"


def test_sync_links_legacy_user_by_email(client):
    db = client.app.state.session_factory()
    legacy = User(
        firebase_uid=None,
        email="legacy@example.com",
        first_name="Legacy",
        last_name="Existing",
    )
    db.add(legacy)
    db.commit()
    db.refresh(legacy)
    legacy_id = legacy.id
    db.close()

    response = client.post("/api/v1/auth/sync", headers=_auth("token-link-legacy"))
    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is False
    assert body["user"]["id"] == legacy_id
    assert body["user"]["firebase_uid"] == "uid-legacy-linked"


def test_sync_conflict_when_email_already_linked_to_different_uid(client):
    db = client.app.state.session_factory()
    existing = User(
        firebase_uid="uid-already-linked",
        email="conflict@example.com",
        first_name="Conflict",
        last_name="Existing",
    )
    db.add(existing)
    db.commit()
    db.close()

    response = client.post("/api/v1/auth/sync", headers=_auth("token-conflict"))
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "auth_identity_conflict"


def test_client_ownership_enforced(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    client.post("/api/v1/auth/sync", headers=_auth("token-user-2"))

    create = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "A", "last_name": "Owner"},
    )
    assert create.status_code == 201
    client_id = create.json()["id"]

    forbidden_read = client.get(f"/api/v1/clients/{client_id}", headers=_auth("token-user-2"))
    assert forbidden_read.status_code == 404


def test_clients_pagination_with_query_params(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    for idx in range(3):
        response = client.post(
            "/api/v1/clients",
            headers=_auth("token-user-1"),
            json={"first_name": f"Client{idx}", "last_name": "User"},
        )
        assert response.status_code == 201

    listed = client.get(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        params={"limit": 2, "offset": 1, "sort": "first_name", "order": "asc"},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert len(body["items"]) == 2


def test_formula_crud_flow_scoped_to_owner(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    client.post("/api/v1/auth/sync", headers=_auth("token-user-2"))

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Formula", "last_name": "Owner"},
    )
    client_id = created_client.json()["id"]

    created_formula = client.post(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "color",
            "notes": "test",
            "price_cents": 12000,
            "service_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert created_formula.status_code == 201
    formula_id = created_formula.json()["id"]

    blocked = client.get(f"/api/v1/formulas/{formula_id}", headers=_auth("token-user-2"))
    assert blocked.status_code == 404

    listed = client.get(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        params={"limit": 10, "offset": 0},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
