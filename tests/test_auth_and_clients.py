from datetime import UTC, datetime

from app.models import ColorChart, User


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


def test_sync_rejects_revoked_sessions(client):
    client.app.state.fake_token_verifier.REVOKED_UIDS.add("uid-1")

    response = client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth_session_revoked"


def test_sync_rejects_disabled_firebase_users(client):
    client.app.state.fake_token_verifier.DISABLED_UIDS.add("uid-1")

    response = client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth_user_disabled"


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


def test_client_groups_can_be_created_assigned_and_archived(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    created_group = client.post(
        "/api/v1/client-groups",
        headers=_auth("token-user-1"),
        json={"name": "Extensions"},
    )
    assert created_group.status_code == 201
    group = created_group.json()

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={
            "first_name": "Riley",
            "last_name": "Rows",
            "group_ids": [group["id"]],
        },
    )
    assert created_client.status_code == 201
    assert created_client.json()["groups"][0]["name"] == "Extensions"

    listed = client.get("/api/v1/client-groups", headers=_auth("token-user-1"))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["client_count"] == 1

    archived = client.delete(
        f"/api/v1/client-groups/{group['id']}",
        headers=_auth("token-user-1"),
    )
    assert archived.status_code == 204

    active = client.get("/api/v1/client-groups", headers=_auth("token-user-1"))
    assert active.json()["items"] == []

    all_groups = client.get(
        "/api/v1/client-groups?active=all",
        headers=_auth("token-user-1"),
    )
    assert all_groups.json()["items"][0]["archived_at"] is not None


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
            "service_at": datetime.now(UTC).isoformat(),
        },
    )
    assert created_formula.status_code == 201
    formula_id = created_formula.json()["id"]
    assert created_formula.json()["images"] == []

    blocked = client.get(f"/api/v1/formulas/{formula_id}", headers=_auth("token-user-2"))
    assert blocked.status_code == 404

    listed = client.get(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        params={"limit": 10, "offset": 0},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["images"] == []


def test_list_formulas_returns_only_owner_rows(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    client.post("/api/v1/auth/sync", headers=_auth("token-user-2"))

    owner_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Owner", "last_name": "Client"},
    )
    owner_client_id = owner_client.json()["id"]

    other_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-2"),
        json={"first_name": "Other", "last_name": "Client"},
    )
    other_client_id = other_client.json()["id"]

    owner_formula = client.post(
        f"/api/v1/clients/{owner_client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "cut",
            "notes": "owner formula",
            "price_cents": 9000,
            "service_at": datetime.now(UTC).isoformat(),
        },
    )
    assert owner_formula.status_code == 201

    other_formula = client.post(
        f"/api/v1/clients/{other_client_id}/formulas",
        headers=_auth("token-user-2"),
        json={
            "service_type": "color",
            "notes": "other formula",
            "price_cents": 15000,
            "service_at": datetime.now(UTC).isoformat(),
        },
    )
    assert other_formula.status_code == 201

    listed = client.get(
        "/api/v1/formulas",
        headers=_auth("token-user-1"),
        params={"limit": 100, "offset": 0},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["client_id"] == owner_client_id
    assert body["items"][0]["notes"] == "owner formula"


def test_create_client_does_not_prepopulate_color_chart(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    created = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "No", "last_name": "Chart"},
    )
    assert created.status_code == 201
    created_client_id = created.json()["id"]

    db = client.app.state.session_factory()
    try:
        color_chart = (
            db.query(ColorChart)
            .filter(ColorChart.client_id == created_client_id)
            .one_or_none()
        )
        assert color_chart is None
    finally:
        db.close()


def test_color_chart_upsert_and_get_for_owner(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Color", "last_name": "Chart"},
    )
    assert created_client.status_code == 201
    client_id = created_client.json()["id"]

    missing = client.get(
        f"/api/v1/clients/{client_id}/color-chart",
        headers=_auth("token-user-1"),
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "color_chart_not_found"

    upsert = client.patch(
        f"/api/v1/clients/{client_id}/color-chart",
        headers=_auth("token-user-1"),
        json={
            "porosity": "Low",
            "hair_texture": "Straight",
            "elasticity": "Medium",
            "natural_level": "4",
            "desired_level": "8",
            "gray_front": "25%",
        },
    )
    assert upsert.status_code == 200
    upsert_body = upsert.json()
    assert upsert_body["client_id"] == client_id
    assert upsert_body["porosity"] == "Low"
    assert upsert_body["hair_texture"] == "Straight"
    assert upsert_body["desired_level"] == "8"

    fetched = client.get(
        f"/api/v1/clients/{client_id}/color-chart",
        headers=_auth("token-user-1"),
    )
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["client_id"] == client_id
    assert fetched_body["gray_front"] == "25%"

    listed = client.get(
        "/api/v1/color-charts",
        headers=_auth("token-user-1"),
        params={"limit": 20, "offset": 0},
    )
    assert listed.status_code == 200
    assert any(item["client_id"] == client_id for item in listed.json()["items"])


def test_color_chart_ownership_enforced(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    client.post("/api/v1/auth/sync", headers=_auth("token-user-2"))

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Owned", "last_name": "Client"},
    )
    assert created_client.status_code == 201
    client_id = created_client.json()["id"]

    forbidden_patch = client.patch(
        f"/api/v1/clients/{client_id}/color-chart",
        headers=_auth("token-user-2"),
        json={"porosity": "High"},
    )
    assert forbidden_patch.status_code == 404
    assert forbidden_patch.json()["error"]["code"] == "client_not_found"

    forbidden_get = client.get(
        f"/api/v1/clients/{client_id}/color-chart",
        headers=_auth("token-user-2"),
    )
    assert forbidden_get.status_code == 404
    assert forbidden_get.json()["error"]["code"] == "client_not_found"
