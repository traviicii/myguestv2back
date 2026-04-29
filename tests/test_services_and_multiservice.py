from datetime import UTC, datetime

from app.api.v1.endpoints.formulas import _resolve_image_public_url
from app.models import FormulaImage


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_services_crud_filters_and_scope(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    client.post("/api/v1/auth/sync", headers=_auth("token-user-2"))

    created_first = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "balayage", "default_return_weeks": 10},
    )
    assert created_first.status_code == 201
    first_service = created_first.json()
    assert first_service["name"] == "Balayage"
    assert first_service["is_active"] is True
    assert first_service["default_return_weeks"] == 10

    created_second = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "single process"},
    )
    assert created_second.status_code == 201
    second_service = created_second.json()

    active_services = client.get("/api/v1/services", headers=_auth("token-user-1"))
    assert active_services.status_code == 200
    assert len(active_services.json()["items"]) == 2

    forbidden_patch = client.patch(
        f"/api/v1/services/{first_service['id']}",
        headers=_auth("token-user-2"),
        json={"name": "Not Allowed"},
    )
    assert forbidden_patch.status_code == 404

    deactivated = client.delete(
        f"/api/v1/services/{first_service['id']}",
        headers=_auth("token-user-1"),
    )
    assert deactivated.status_code == 204

    active_only = client.get(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        params={"active": "true"},
    )
    assert active_only.status_code == 200
    assert [item["id"] for item in active_only.json()["items"]] == [second_service["id"]]

    inactive_only = client.get(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        params={"active": "false"},
    )
    assert inactive_only.status_code == 200
    assert [item["id"] for item in inactive_only.json()["items"]] == [first_service["id"]]

    reactivated = client.patch(
        f"/api/v1/services/{first_service['id']}",
        headers=_auth("token-user-1"),
        json={"is_active": True},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["is_active"] is True

    renamed = client.patch(
        f"/api/v1/services/{second_service['id']}",
        headers=_auth("token-user-1"),
        json={"name": "single PROCESS color", "default_return_weeks": 6},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Single Process Color"
    assert renamed.json()["default_return_weeks"] == 6


def test_service_default_return_weeks_validates_range_and_null_updates(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    invalid_low = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "Root Touch Up", "default_return_weeks": 0},
    )
    assert invalid_low.status_code == 422

    invalid_high = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "Gloss", "default_return_weeks": 53},
    )
    assert invalid_high.status_code == 422

    created = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "Haircut", "default_return_weeks": 8},
    )
    assert created.status_code == 201
    service_id = created.json()["id"]

    cleared = client.patch(
        f"/api/v1/services/{service_id}",
        headers=_auth("token-user-1"),
        json={"default_return_weeks": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["default_return_weeks"] is None


def test_formula_multi_service_create_and_update(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Multi", "last_name": "Service"},
    )
    assert created_client.status_code == 201
    client_id = created_client.json()["id"]

    first_service = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "Cut"},
    ).json()
    second_service = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "Color"},
    ).json()

    created_formula = client.post(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_ids": [second_service["id"], first_service["id"]],
            "notes": "multi service",
            "price_cents": 25000,
            "service_at": datetime.now(UTC).isoformat(),
        },
    )
    assert created_formula.status_code == 201
    formula = created_formula.json()
    assert formula["service_type"] == "Color"
    assert [item["service_id"] for item in formula["services"]] == [
        second_service["id"],
        first_service["id"],
    ]
    assert [item["position"] for item in formula["services"]] == [0, 1]

    formula_id = formula["id"]
    patched = client.patch(
        f"/api/v1/formulas/{formula_id}",
        headers=_auth("token-user-1"),
        json={"service_ids": [first_service["id"]]},
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["service_type"] == "Cut"
    assert [item["service_id"] for item in patched_body["services"]] == [
        first_service["id"]
    ]

    cleared = client.patch(
        f"/api/v1/formulas/{formula_id}",
        headers=_auth("token-user-1"),
        json={"service_ids": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["service_type"] is None
    assert cleared.json()["services"] == []


def test_legacy_service_type_backfills_links_without_duplicates(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Legacy", "last_name": "Flow"},
    )
    client_id = created_client.json()["id"]

    first_formula = client.post(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": " single process ",
            "notes": "legacy 1",
            "price_cents": 10000,
            "service_at": datetime.now(UTC).isoformat(),
        },
    )
    assert first_formula.status_code == 201
    assert first_formula.json()["service_type"] == "Single Process"
    assert len(first_formula.json()["services"]) == 1
    assert first_formula.json()["services"][0]["name"] == "Single Process"

    second_formula = client.post(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "single PROCESS",
            "notes": "legacy 2",
            "price_cents": 9000,
            "service_at": datetime.now(UTC).isoformat(),
        },
    )
    assert second_formula.status_code == 201
    assert second_formula.json()["service_type"] == "Single Process"

    listed_services = client.get("/api/v1/services", headers=_auth("token-user-1"))
    assert listed_services.status_code == 200
    assert len(listed_services.json()["items"]) == 1
    assert listed_services.json()["items"][0]["name"] == "Single Process"


def test_formula_image_write_and_replace_flow(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Image", "last_name": "Test"},
    )
    assert created_client.status_code == 201
    client_id = created_client.json()["id"]

    service = client.post(
        "/api/v1/services",
        headers=_auth("token-user-1"),
        json={"name": "Gloss"},
    ).json()

    created_formula = client.post(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_ids": [service["id"]],
            "service_at": datetime.now(UTC).isoformat(),
            "images": [
                {
                    "storage_provider": "firebase",
                    "public_url": "https://cdn.example.com/gallery/final-look.jpg",
                },
                {
                    "storage_provider": "r2",
                    "object_key": "formula-images/client-1/process-shot.png",
                },
            ],
        },
    )
    assert created_formula.status_code == 201
    created_body = created_formula.json()
    assert len(created_body["images"]) == 2
    assert created_body["images"][0]["file_name"] == "final-look.jpg"
    assert created_body["images"][1]["file_name"] == "process-shot.png"

    formula_id = created_body["id"]
    patched = client.patch(
        f"/api/v1/formulas/{formula_id}",
        headers=_auth("token-user-1"),
        json={
            "images": [
                {
                    "storage_provider": "device local",
                    "public_url": "file:///var/mobile/new-photo.jpeg",
                    "file_name": "new-photo.jpeg",
                }
            ]
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert len(patched_body["images"]) == 1
    assert patched_body["images"][0]["storage_provider"] == "device_local"
    assert patched_body["images"][0]["file_name"] == "new-photo.jpeg"

    cleared = client.patch(
        f"/api/v1/formulas/{formula_id}",
        headers=_auth("token-user-1"),
        json={"images": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["images"] == []


def test_resolve_image_public_url_uses_firebase_bucket_for_object_keys(monkeypatch):
    image = FormulaImage(
        id=10,
        formula_id=99,
        storage_provider="firebase",
        public_url=None,
        object_key="formula-images/process-shot.png",
        file_name="process-shot.png",
    )
    seen: dict[str, object] = {}

    class FakeBlob:
        def generate_signed_url(self, *, version: str, expiration, method: str) -> str:
            seen["version"] = version
            seen["method"] = method
            seen["expiration"] = expiration
            return "https://signed.example.com/process-shot.png"

    class FakeBucket:
        def __init__(self, bucket_name: str):
            self.bucket_name = bucket_name

        def blob(self, object_path: str) -> FakeBlob:
            seen["bucket_name"] = self.bucket_name
            seen["object_path"] = object_path
            return FakeBlob()

    class FakeSettings:
        firebase_storage_bucket = "myguest-test-bucket"

    monkeypatch.setattr(
        "app.api.v1.endpoints.formulas.get_settings", lambda: FakeSettings()
    )
    monkeypatch.setattr("app.api.v1.endpoints.formulas.firebase_admin._apps", [object()])
    monkeypatch.setattr(
        "app.api.v1.endpoints.formulas.firebase_storage.bucket",
        lambda bucket_name: FakeBucket(bucket_name),
    )

    assert _resolve_image_public_url(image) == "https://signed.example.com/process-shot.png"
    assert seen["bucket_name"] == "myguest-test-bucket"
    assert seen["object_path"] == "formula-images/process-shot.png"


def test_resolve_image_public_url_prefers_existing_firebase_public_url(monkeypatch):
    legacy_url = (
        "https://firebasestorage.googleapis.com/v0/b/custom-bucket/o/"
        "formula-images%2Fclient-1%2Fafter.jpg?alt=media&token=stale-token"
    )
    image = FormulaImage(
        id=11,
        formula_id=99,
        storage_provider="firebase",
        public_url=legacy_url,
        object_key=None,
        file_name="after.jpg",
    )

    def fail_if_called(bucket_name: str):
        raise AssertionError(f"storage bucket should not be used: {bucket_name}")

    monkeypatch.setattr("app.api.v1.endpoints.formulas.firebase_admin._apps", [object()])
    monkeypatch.setattr(
        "app.api.v1.endpoints.formulas.firebase_storage.bucket",
        fail_if_called,
    )

    assert _resolve_image_public_url(image) == legacy_url
