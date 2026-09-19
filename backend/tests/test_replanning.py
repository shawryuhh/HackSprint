import threading
from concurrent.futures import ThreadPoolExecutor


def _create_incident(client, location="Krishna Apartments, Block C", severity="CRITICAL"):
    return client.post(
        "/incidents",
        json={"location": location, "type": "flood", "severity": severity},
    ).json()["id"]


def _create_resource(client, resource_type="ambulance", location="Depot"):
    return client.post("/resources", json={"type": resource_type, "location": location}).json()[
        "id"
    ]


def _assign(client, incident_id, resource_id):
    response = client.post(
        "/assignments",
        json={
            "incident_id": incident_id,
            "resource_ids": [resource_id],
            "decision_source": "ai",
            "approved_by": "dispatcher_1",
        },
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def test_canonical_replan_scenario(client):
    """INC-1042 style: AMB-02 assigned, hits a road block, replanned to AMB-05."""
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client, location="Sector 12 Depot")
    amb_05 = _create_resource(client, location="Sector 9 Depot")
    old_assignment_id = _assign(client, incident_id, amb_02)

    response = client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": [amb_05],
            "reason": "road_blocked",
            "decision_source": "ai",
            "approved_by": "dispatcher_1",
        },
    )
    assert response.status_code == 201
    body = response.json()

    assert body["superseded_assignment"]["id"] == old_assignment_id
    assert body["superseded_assignment"]["status"] == "SUPERSEDED"
    assert len(body["new_assignments"]) == 1
    new_assignment = body["new_assignments"][0]
    assert new_assignment["resource_id"] == amb_05
    assert new_assignment["status"] == "ASSIGNED"

    # AMB-02 released, AMB-05 dispatched.
    assert client.get(f"/resources/{amb_02}").json()["status"] == "AVAILABLE"
    assert client.get(f"/resources/{amb_05}").json()["status"] == "DISPATCHED"

    # Incident remains correctly assigned.
    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["status"] == "ASSIGNED"
    live_resource_ids = {a["resource_id"] for a in incident["current_assignments"]}
    assert live_resource_ids == {amb_05}

    # Old assignment preserved (never deleted), just superseded.
    old = client.get(f"/assignments/{old_assignment_id}").json()
    assert old["status"] == "SUPERSEDED"


def test_replan_replacement_resource_unavailable(client):
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    amb_05 = _create_resource(client)
    other_incident = _create_incident(client, "Elsewhere")
    _assign(client, other_incident, amb_05)  # AMB-05 already busy elsewhere
    _assign(client, incident_id, amb_02)

    response = client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": [amb_05],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 409

    # Nothing changed: old assignment still live, AMB-02 still dispatched.
    assert client.get(f"/resources/{amb_02}").json()["status"] == "DISPATCHED"
    incident = client.get(f"/incidents/{incident_id}").json()
    assert len(incident["current_assignments"]) == 1
    assert incident["current_assignments"][0]["status"] == "ASSIGNED"


def test_replan_old_assignment_already_completed_is_rejected(client):
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    amb_05 = _create_resource(client)
    assignment_id = _assign(client, incident_id, amb_02)

    client.post(f"/assignments/{assignment_id}/status", json={"status": "ACTIVE"})
    client.post(f"/assignments/{assignment_id}/status", json={"status": "COMPLETED"})

    response = client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": [amb_05],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 409


def test_replan_old_assignment_already_cancelled_is_rejected(client):
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    amb_05 = _create_resource(client)
    assignment_id = _assign(client, incident_id, amb_02)
    client.post(f"/assignments/{assignment_id}/status", json={"status": "CANCELLED"})

    response = client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": [amb_05],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 409


def test_replan_invalid_incident_returns_404(client):
    amb_02 = _create_resource(client)
    amb_05 = _create_resource(client)
    response = client.post(
        "/replanning",
        json={
            "incident_id": "INC-does-not-exist",
            "old_resource_id": amb_02,
            "new_resource_ids": [amb_05],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 404


def test_replan_invalid_replacement_resource_returns_404(client):
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    _assign(client, incident_id, amb_02)

    response = client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": ["AMB-does-not-exist"],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 404


def test_replan_no_live_assignment_for_old_resource_returns_404(client):
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    amb_05 = _create_resource(client)
    # Never assigned to this incident at all.

    response = client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": [amb_05],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 404


def test_replan_is_all_or_nothing_when_one_of_several_replacements_unavailable(client):
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    rescue_05 = _create_resource(client, resource_type="rescue_unit")
    already_busy = _create_resource(client)
    other_incident = _create_incident(client, "Elsewhere")
    _assign(client, other_incident, already_busy)
    _assign(client, incident_id, amb_02)

    response = client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": [rescue_05, already_busy],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )
    assert response.status_code == 409

    # Nothing partially applied: AMB-02 still dispatched, RESCUE-05 not touched.
    assert client.get(f"/resources/{amb_02}").json()["status"] == "DISPATCHED"
    assert client.get(f"/resources/{rescue_05}").json()["status"] == "AVAILABLE"
    assignments_for_incident = client.get(
        "/assignments", params={"incident_id": incident_id}
    ).json()
    assert len(assignments_for_incident) == 1
    assert assignments_for_incident[0]["status"] == "ASSIGNED"


def test_concurrent_replanning_of_same_assignment_is_serialized(client):
    """Two replan requests race to replace the same old assignment with
    different resources. Only one may win; the loser must not have partially
    applied any change."""
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    amb_05 = _create_resource(client)
    amb_07 = _create_resource(client)
    _assign(client, incident_id, amb_02)

    barrier = threading.Barrier(2)
    results: dict[str, object] = {}

    def attempt(name: str, new_resource_id: str) -> None:
        barrier.wait()
        results[name] = client.post(
            "/replanning",
            json={
                "incident_id": incident_id,
                "old_resource_id": amb_02,
                "new_resource_ids": [new_resource_id],
                "reason": "road_blocked",
                "decision_source": "ai",
            },
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt, "a", amb_05),
            executor.submit(attempt, "b", amb_07),
        ]
        for future in futures:
            future.result()

    status_codes = sorted(r.status_code for r in results.values())
    assert status_codes == [201, 409]

    incident = client.get(f"/incidents/{incident_id}").json()
    assert len(incident["current_assignments"]) == 1

    assert client.get(f"/resources/{amb_02}").json()["status"] == "AVAILABLE"
    winner_resource_status = {
        client.get(f"/resources/{amb_05}").json()["status"],
        client.get(f"/resources/{amb_07}").json()["status"],
    }
    assert winner_resource_status == {"AVAILABLE", "DISPATCHED"}


def test_replan_preserves_complete_audit_history(client):
    incident_id = _create_incident(client)
    amb_02 = _create_resource(client)
    amb_05 = _create_resource(client)
    old_assignment_id = _assign(client, incident_id, amb_02)

    client.post(
        "/replanning",
        json={
            "incident_id": incident_id,
            "old_resource_id": amb_02,
            "new_resource_ids": [amb_05],
            "reason": "road_blocked",
            "decision_source": "ai",
        },
    )

    logs = client.get("/activity-log", params={"incident_id": incident_id}).json()
    actions = [log["action"] for log in logs]
    assert "incident_received" in actions
    assert "assignment_created" in actions
    assert "assignment_superseded" in actions

    superseded_log = next(log for log in logs if log["action"] == "assignment_superseded")
    assert superseded_log["assignment_id"] == old_assignment_id
    assert superseded_log["metadata"]["replaced_by_resources"] == [amb_05]

    all_assignments = client.get(
        "/assignments", params={"incident_id": incident_id}
    ).json()
    assert len(all_assignments) == 2
    statuses = {a["status"] for a in all_assignments}
    assert statuses == {"SUPERSEDED", "ASSIGNED"}
