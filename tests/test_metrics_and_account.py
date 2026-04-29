import io
import zipfile
from datetime import UTC, datetime, timedelta

import app.api.v1.endpoints.account as account_endpoint
from app.models import FormulaImage
from app.services.storage_cleanup import (
    StorageCleanupSummary,
    delete_firebase_images,
    extract_storage_target,
)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_overview_metrics_aggregate_only_current_user_data(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    client.post("/api/v1/auth/sync", headers=_auth("token-user-2"))

    now = datetime.now(UTC)

    color_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Nova", "last_name": "Color", "client_type": "Color"},
    ).json()
    cut_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Mina", "last_name": "Cut", "client_type": "Cut"},
    ).json()
    client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Sage", "last_name": "Blend", "client_type": "Cut & Color"},
    )
    other_user_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-2"),
        json={"first_name": "Other", "last_name": "User", "client_type": "Color"},
    ).json()

    client.patch(
        f"/api/v1/clients/{color_client['id']}/color-chart",
        headers=_auth("token-user-1"),
        json={"porosity": "Low", "natural_level": "4"},
    )

    client.post(
        f"/api/v1/clients/{color_client['id']}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "Color",
            "price_cents": 20000,
            "service_at": now.isoformat(),
            "images": [
                {
                    "storage_provider": "firebase",
                    "public_url": "https://cdn.example.com/final-look.jpg",
                }
            ],
        },
    )
    client.post(
        f"/api/v1/clients/{color_client['id']}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "Color",
            "price_cents": 15000,
            "service_at": (now - timedelta(days=10)).isoformat(),
        },
    )
    client.post(
        f"/api/v1/clients/{cut_client['id']}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "Cut",
            "price_cents": 10000,
            "service_at": (now - timedelta(days=20)).isoformat(),
        },
    )
    client.post(
        f"/api/v1/clients/{other_user_client['id']}/formulas",
        headers=_auth("token-user-2"),
        json={
            "service_type": "Color",
            "price_cents": 99900,
            "service_at": now.isoformat(),
        },
    )

    metrics_response = client.get(
        "/api/v1/metrics/overview",
        headers=_auth("token-user-1"),
        params={
            "active_cutoff": (now - timedelta(days=120)).isoformat(),
            "year_start": datetime(now.year, 1, 1, tzinfo=UTC).isoformat(),
            "avg_ticket_cutoff": (now - timedelta(days=180)).isoformat(),
            "photo_cutoff": (now - timedelta(days=30)).isoformat(),
            "new_clients_cutoff": (now - timedelta(days=90)).isoformat(),
        },
    )

    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    assert metrics == {
        "revenue_ytd": 450.0,
        "avg_ticket": 150.0,
        "total_clients": 3,
        "active_clients": 2,
        "inactive_clients": 1,
        "new_clients_90": 3,
        "service_mix_label": "Color",
        "service_mix_percent": 67,
        "color_coverage_percent": 50,
        "photo_coverage_percent": 33,
    }


def test_export_data_returns_zip_for_current_user(client):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Export", "last_name": "Ready", "client_type": "Color"},
    )
    client_id = created_client.json()["id"]

    client.patch(
        f"/api/v1/clients/{client_id}/color-chart",
        headers=_auth("token-user-1"),
        json={"porosity": "Medium"},
    )
    client.post(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "Color",
            "price_cents": 12000,
            "service_at": datetime.now(UTC).isoformat(),
        },
    )

    exported = client.get("/api/v1/exports/data", headers=_auth("token-user-1"))

    assert exported.status_code == 200
    assert exported.headers["content-type"] == "application/zip"
    assert "attachment; filename=myguest_export_" in exported.headers["content-disposition"]

    archive = zipfile.ZipFile(io.BytesIO(exported.content))
    assert sorted(archive.namelist()) == [
        "appointment_logs.csv",
        "clients.csv",
        "color_charts.csv",
        "services.csv",
    ]

    clients_csv = archive.read("clients.csv").decode("utf-8")
    formulas_csv = archive.read("appointment_logs.csv").decode("utf-8")
    charts_csv = archive.read("color_charts.csv").decode("utf-8")

    assert "Export" in clients_csv
    assert "Color" in formulas_csv
    assert "Medium" in charts_csv


def test_account_delete_reports_cleanup_outcome_and_removes_user(client, monkeypatch):
    client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))

    created_client = client.post(
        "/api/v1/clients",
        headers=_auth("token-user-1"),
        json={"first_name": "Delete", "last_name": "Me"},
    )
    client_id = created_client.json()["id"]

    formula = client.post(
        f"/api/v1/clients/{client_id}/formulas",
        headers=_auth("token-user-1"),
        json={
            "service_type": "Color",
            "service_at": datetime.now(UTC).isoformat(),
            "images": [
                {
                    "storage_provider": "firebase",
                    "public_url": "https://cdn.example.com/gallery/delete-me.jpg",
                }
            ],
        },
    )
    assert formula.status_code == 201

    seen: dict[str, object] = {}

    def fake_delete_images(images, default_bucket_name):
        seen["image_count"] = len(images)
        seen["bucket_name"] = default_bucket_name
        return StorageCleanupSummary(deleted=1, failed=1)

    def fake_delete_user(firebase_uid):
        seen["firebase_uid"] = firebase_uid
        return False

    def fake_revoke_tokens(firebase_uid):
        seen["revoked_uid"] = firebase_uid
        client.app.state.fake_token_verifier.REVOKED_UIDS.add(firebase_uid)
        return True

    monkeypatch.setattr(account_endpoint, "delete_firebase_images", fake_delete_images)
    monkeypatch.setattr(account_endpoint, "delete_firebase_user", fake_delete_user)
    monkeypatch.setattr(account_endpoint, "revoke_firebase_tokens", fake_revoke_tokens)

    deleted = client.post(
        "/api/v1/account/delete",
        headers=_auth("token-user-1"),
        json={"email": "one@example.com"},
    )

    assert deleted.status_code == 200
    assert deleted.json() == {
        "deleted": True,
        "images_deleted": 1,
        "images_failed": 1,
        "firebase_user_deleted": False,
    }
    assert seen["image_count"] == 1
    assert seen["firebase_uid"] == "uid-1"
    assert seen["revoked_uid"] == "uid-1"

    resynced = client.post("/api/v1/auth/sync", headers=_auth("token-user-1"))
    assert resynced.status_code == 401
    assert resynced.json()["error"]["code"] == "auth_session_revoked"


def test_extract_storage_target_and_delete_firebase_images_handle_mixed_inputs():
    download_url = (
        "https://firebasestorage.googleapis.com/v0/b/custom-bucket/o/"
        "formula-images%2Fclient-1%2Fafter.jpg?alt=media"
    )
    assert extract_storage_target(download_url, None) == (
        "custom-bucket",
        "formula-images/client-1/after.jpg",
    )

    deleted_paths: list[tuple[str, str]] = []

    class FakeBlob:
        def __init__(self, bucket_name: str, object_path: str):
            self.bucket_name = bucket_name
            self.object_path = object_path

        def delete(self):
            if self.object_path.endswith("fail.jpg"):
                raise RuntimeError("boom")
            deleted_paths.append((self.bucket_name, self.object_path))

    class FakeBucket:
        def __init__(self, name: str):
            self.name = name

        def blob(self, object_path: str):
            return FakeBlob(self.name, object_path)

    class FakeStorage:
        def bucket(self, name: str):
            if name == "missing-bucket":
                raise RuntimeError("missing")
            return FakeBucket(name)

    images = [
        FormulaImage(
            id=1,
            formula_id=10,
            storage_provider="firebase",
            public_url=None,
            object_key="formula-images/client-1/keep.jpg",
            file_name="keep.jpg",
        ),
        FormulaImage(
            id=2,
            formula_id=10,
            storage_provider="firebase",
            public_url=download_url,
            object_key=None,
            file_name="after.jpg",
        ),
        FormulaImage(
            id=3,
            formula_id=10,
            storage_provider="firebase",
            public_url="gs://missing-bucket/formula-images/client-1/fail.jpg",
            object_key=None,
            file_name="fail.jpg",
        ),
        FormulaImage(
            id=4,
            formula_id=10,
            storage_provider="firebase",
            public_url=None,
            object_key=None,
            file_name="broken.jpg",
        ),
        FormulaImage(
            id=5,
            formula_id=10,
            storage_provider="r2",
            public_url=None,
            object_key="formula-images/client-1/skip.jpg",
            file_name="skip.jpg",
        ),
    ]

    summary = delete_firebase_images(
        images,
        default_bucket_name="default-bucket",
        storage_module=FakeStorage(),
    )

    assert summary == StorageCleanupSummary(deleted=2, failed=2)
    assert deleted_paths == [
        ("default-bucket", "formula-images/client-1/keep.jpg"),
        ("custom-bucket", "formula-images/client-1/after.jpg"),
    ]
