import threading
from concurrent.futures import ThreadPoolExecutor

from app.db.session import SessionLocal
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus


def _create_incident(client, location="Test Location", severity="HIGH"):
    response = client.post(
        "/incidents",
        json={"location": location, "type": "flood", "severity": severity},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_resource(client, resource_type="ambulance", location="Depot"):
    response = client.post("/resources", json={"type": resource_type, "location": location})
    assert response.status_code == 201
    return response.json()["id"]


def test_create_assignment_updates_incident_and_resource(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": [resource_id],
            "decision_source": "ai",
            "approved_by": "dispatcher_1",
            "reason": "Medical emergency",
        },
    )
    assert response.status_code == 201
    assignments = response.json()
    assert len(assignments) == 1
    assert assignments[0]["status"] == "ASSIGNED"
    assert assignments[0]["resource_id"] == resource_id
    assert assignments[0]["incident_id"] == incident_id

    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["status"] == "ASSIGNED"
    assert len(incident["current_assignments"]) == 1

    resource = client.get(f"/resources/{resource_id}").json()
    assert resource["status"] == "DISPATCHED"


def test_create_assignment_with_ai_recommendation_logs_it(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": [resource_id],
            "decision_source": "ai",
            "ai_recommendation": {
                "incident_id": incident_id,
                "priority_score": 94,
                "recommended_resources": [resource_id],
                "reason": "Medical emergency involving a vulnerable person",
            },
        },
    )
    assert response.status_code == 201


def test_cannot_assign_already_dispatched_resource(client):
    incident_a = _create_incident(client, "Location A")
    incident_b = _create_incident(client, "Location B")
    resource_id = _create_resource(client)

    first = client.post(
        "/assignments",
        json={"incident_id": incident_a, "resource_ids": [resource_id], "decision_source": "ai"},
    )
    assert first.status_code == 201

    second = client.post(
        "/assignments",
        json={"incident_id": incident_b, "resource_ids": [resource_id], "decision_source": "ai"},
    )
    assert second.status_code == 409


def test_create_assignment_unknown_incident_returns_404(client):
    resource_id = _create_resource(client)
    response = client.post(
        "/assignments",
        json={
            "incident_id": "INC-does-not-exist",
            "resource_ids": [resource_id],
            "decision_source": "ai",
        },
    )
    assert response.status_code == 404


def test_create_assignment_unknown_resource_returns_404(client):
    incident_id = _create_incident(client)
    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": ["AMB-does-not-exist"],
            "decision_source": "ai",
        },
    )
    assert response.status_code == 404


def test_create_assignment_is_all_or_nothing(client):
    incident_id = _create_incident(client)
    available_resource = _create_resource(client)
    already_taken_resource = _create_resource(client)

    other_incident = _create_incident(client, "Elsewhere")
    client.post(
        "/assignments",
        json={
            "incident_id": other_incident,
            "resource_ids": [already_taken_resource],
            "decision_source": "ai",
        },
    )

    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": [available_resource, already_taken_resource],
            "decision_source": "ai",
        },
    )
    assert response.status_code == 409

    # The available resource must NOT have been dispatched by the failed
    # all-or-nothing attempt.
    resource = client.get(f"/resources/{available_resource}").json()
    assert resource["status"] == "AVAILABLE"


def test_assignment_lifecycle_activate_then_complete_frees_resource(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)

    assignment_id = client.post(
        "/assignments",
        json={"incident_id": incident_id, "resource_ids": [resource_id], "decision_source": "ai"},
    ).json()[0]["id"]

    activate = client.post(f"/assignments/{assignment_id}/status", json={"status": "ACTIVE"})
    assert activate.status_code == 200
    assert activate.json()["status"] == "ACTIVE"
    assert client.get(f"/resources/{resource_id}").json()["status"] == "ACTIVE"

    complete = client.post(f"/assignments/{assignment_id}/status", json={"status": "COMPLETED"})
    assert complete.status_code == 200
    assert complete.json()["status"] == "COMPLETED"
    assert complete.json()["completed_at"] is not None
    assert client.get(f"/resources/{resource_id}").json()["status"] == "AVAILABLE"


def test_cancel_assignment_frees_resource(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = client.post(
        "/assignments",
        json={"incident_id": incident_id, "resource_ids": [resource_id], "decision_source": "ai"},
    ).json()[0]["id"]

    cancel = client.post(
        f"/assignments/{assignment_id}/status",
        json={"status": "CANCELLED", "reason": "false alarm"},
    )
    assert cancel.status_code == 200
    assert client.get(f"/resources/{resource_id}").json()["status"] == "AVAILABLE"


def test_invalid_assignment_transition_is_rejected(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = client.post(
        "/assignments",
        json={"incident_id": incident_id, "resource_ids": [resource_id], "decision_source": "ai"},
    ).json()[0]["id"]

    # ASSIGNED -> COMPLETED is not a direct transition (must go through ACTIVE).
    response = client.post(f"/assignments/{assignment_id}/status", json={"status": "COMPLETED"})
    assert response.status_code == 409


def test_superseded_is_rejected_via_status_endpoint(client):
    incident_id = _create_incident(client)
    resource_id = _create_resource(client)
    assignment_id = client.post(
        "/assignments",
        json={"incident_id": incident_id, "resource_ids": [resource_id], "decision_source": "ai"},
    ).json()[0]["id"]

    response = client.post(f"/assignments/{assignment_id}/status", json={"status": "SUPERSEDED"})
    assert response.status_code == 422


def test_concurrent_assignment_of_same_resource_is_serialized_not_double_booked(client):
    """Two requests race to assign the same AVAILABLE resource to two
    different incidents. Real PostgreSQL row locking (SELECT ... FOR UPDATE)
    must serialize them so exactly one succeeds; the partial unique index is
    the backstop if it didn't."""
    incident_a = _create_incident(client, "Location A")
    incident_b = _create_incident(client, "Location B")
    resource_id = _create_resource(client)

    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def attempt(name: str, incident_id: str) -> None:
        barrier.wait()
        results[name] = client.post(
            "/assignments",
            json={
                "incident_id": incident_id,
                "resource_ids": [resource_id],
                "decision_source": "ai",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt, "a", incident_a),
            executor.submit(attempt, "b", incident_b),
        ]
        for future in futures:
            future.result()

    status_codes = sorted(r.status_code for r in results.values())
    assert status_codes == [201, 409]

    resource = client.get(f"/resources/{resource_id}").json()
    assert resource["status"] == "DISPATCHED"

    with SessionLocal() as db:
        live_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.resource_id == resource_id,
                Assignment.status.in_((AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)),
            )
            .all()
        )
    assert len(live_assignments) == 1
