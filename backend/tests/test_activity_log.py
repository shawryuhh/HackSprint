def test_incident_creation_is_logged_automatically(client):
    incident_id = client.post(
        "/incidents",
        json={"location": "Test Location", "type": "flood", "severity": "HIGH"},
    ).json()["id"]

    logs = client.get("/activity-log", params={"incident_id": incident_id}).json()
    assert len(logs) == 1
    assert logs[0]["action"] == "incident_received"
    assert logs[0]["incident_id"] == incident_id


def test_create_manual_activity_log_entry(client):
    response = client.post(
        "/activity-log",
        json={
            "source": "ai",
            "action": "duplicate_merged",
            "reason": "Two WhatsApp reports described the same event",
            "metadata": {"merged_report_ids": ["wa-1", "wa-2"]},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["action"] == "duplicate_merged"
    assert body["metadata"] == {"merged_report_ids": ["wa-1", "wa-2"]}

    fetched = client.get(f"/activity-log/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_manual_activity_log_rejects_unknown_incident_reference(client):
    response = client.post(
        "/activity-log",
        json={
            "source": "ai",
            "action": "duplicate_merged",
            "incident_id": "INC-does-not-exist",
        },
    )
    assert response.status_code == 422


def test_activity_log_has_no_mutation_endpoints(client):
    log_id = client.post(
        "/activity-log", json={"source": "ai", "action": "duplicate_merged"}
    ).json()["id"]

    assert client.patch(f"/activity-log/{log_id}", json={"action": "changed"}).status_code == 405
    assert client.put(f"/activity-log/{log_id}", json={"action": "changed"}).status_code == 405
    assert client.delete(f"/activity-log/{log_id}").status_code == 405


def test_activity_log_filters_by_source_and_action(client):
    client.post("/activity-log", json={"source": "ai", "action": "duplicate_merged"})
    client.post("/activity-log", json={"source": "n8n", "action": "road_blocked"})

    filtered = client.get(
        "/activity-log", params={"source": "n8n", "action": "road_blocked"}
    ).json()
    assert len(filtered) == 1
    assert filtered[0]["source"] == "n8n"


def test_get_unknown_activity_log_entry_returns_404(client):
    response = client.get("/activity-log/999999")
    assert response.status_code == 404
