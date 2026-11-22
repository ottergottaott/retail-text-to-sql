import pytest
from fastapi.testclient import TestClient
from retail.api import create_app
from retail.config import Settings


@pytest.fixture
def client(tmp_path):
    config = Settings(database_url=f"sqlite:///{tmp_path}/app.db", log_path=str(tmp_path / "events.jsonl"),
        adapter_secret="adapter-only", webui_users_json='{"webui-alice":"alice"}')
    return TestClient(create_app(config))


def test_auth_and_webui_trust_boundary(client):
    assert client.post("/chat", json={"message": "hello"}).status_code == 403
    assert client.get("/reports", headers={"Authorization": "Bearer adapter-only", "X-Webui-User": "bob"}).status_code == 403
    result = client.get("/preferences", headers={"Authorization": "Bearer adapter-only", "X-Webui-User": "webui-alice"})
    assert result.status_code == 200
    # An ordinary token cannot select another principal through a forwarded header.
    client.put("/preferences", headers={"Authorization": "Bearer alice-local-token", "X-Webui-User": "bob"},
        json={"format": "bullets", "depth": "concise"})
    assert client.get("/preferences", headers={"Authorization": "Bearer alice-local-token"}).json()["format"] == "bullets"
    assert client.get("/preferences", headers={"Authorization": "Bearer bob-local-token"}).json()["format"] == "tables"


def test_stream_final_and_progress_and_report_lifetime(client):
    headers = {"Authorization": "Bearer alice-local-token"}
    response = client.post("/chat/stream", headers=headers, json={"message": "monthly revenue"})
    assert response.status_code == 200
    assert "event: progress" in response.text and "event: result" in response.text
    import json
    result = json.loads(response.text.split("event: result\ndata: ")[1].strip())
    assert result["evidence"][0]["mode"] == "fixture"
    saved = client.post("/chat", headers=headers, json={"message": "save report", "conversation_id": result["conversation_id"]}).json()
    rid = saved["management"]["report_id"]
    assert client.get(f"/reports/{rid}", headers=headers).status_code == 200
    assert client.get(f"/reports/{rid}", headers={"Authorization": "Bearer bob-local-token"}).status_code == 403
    # A fresh chat can retrieve independent persisted reports.
    listed = client.post("/chat", headers=headers, json={"message": "list reports"}).json()
    assert rid in listed["answer"]


def test_webui_conversation_mapping_survives_adapter_calls(client):
    alice = {"Authorization": "Bearer adapter-only", "X-Webui-User": "webui-alice"}
    first = client.post("/chat", headers=alice, json={"message": "schema", "external_chat_id": "chat-1"}).json()
    second = client.post("/chat", headers=alice, json={"message": "schema", "external_chat_id": "chat-1"}).json()
    assert first["conversation_id"] == second["conversation_id"]
    other = client.post("/chat", headers={"Authorization": "Bearer bob-local-token"},
        json={"message": "schema", "external_chat_id": "chat-1"}).json()
    assert first["conversation_id"] != other["conversation_id"]


def test_report_html_is_opt_in_and_preserves_owner_and_scope_checks(client):
    alice = {"Authorization": "Bearer alice-local-token"}
    bob = {"Authorization": "Bearer bob-local-token"}
    ordinary = client.post("/chat", headers=alice, json={"message": "monthly revenue"}).json()
    assert "report_view" not in ordinary
    draft = client.post("/chat", headers=alice, json={"message": "monthly revenue", "include_report_view": True}).json()
    assert "100.0" in draft["report_view"]["html"]
    assert draft["report_view"]["report_id"] is None
    saved = client.post("/chat", headers=alice, json={"message": "save report", "conversation_id": draft["conversation_id"], "include_report_view": True}).json()
    rid = saved["management"]["report_id"]
    assert saved["report_view"]["report_id"] == rid
    html = client.get(f"/reports/{rid}/html", headers=alice)
    assert html.status_code == 200 and html.headers["content-type"].startswith("text/html")
    assert "default-src 'none'" in html.headers["content-security-policy"]
    assert html.headers["cache-control"] == "no-store" and "100.0" in html.text
    for headers in ({}, bob):
        assert client.get(f"/reports/{rid}/html", headers=headers).status_code == 403
    opened = client.post("/chat", headers=alice, json={"message": "open report " + rid, "include_report_view": True}).json()
    assert "100.0" in opened["report_view"]["html"]
    denied = client.post("/chat", headers=bob, json={"message": "open report " + rid, "include_report_view": True}).json()
    assert "report_view" not in denied
    # Even the owner cannot render a report after losing part of its scope.
    client.app.state.store.get("report", "alice", rid)
    client.app.state.agent.config.entitlements_json = '{"alice":[1],"bob":[2,3]}'
    assert client.get(f"/reports/{rid}/html", headers=alice).status_code == 403


def test_non_analysis_responses_do_not_become_html_reports(client):
    for message in ("schema", "list reports", "show customer email", "hello"):
        result = client.post("/chat", headers={"Authorization": "Bearer alice-local-token"},
            json={"message": message, "include_report_view": True}).json()
        assert "report_view" not in result


def test_report_presentation_failure_does_not_hide_a_committed_save(client, monkeypatch):
    import retail.api as api
    def broken(*args, **kwargs):
        raise ValueError("template unavailable")
    monkeypatch.setattr(api, "render_report", broken)
    headers = {"Authorization": "Bearer alice-local-token"}
    result = client.post("/chat", headers=headers,
        json={"message": "Create and save a monthly revenue report", "include_report_view": True}).json()
    assert result["outcome"] == "succeeded" and "report_view" not in result
    assert client.get("/reports/" + result["management"]["report_id"], headers=headers).status_code == 200


def test_confirmed_deletion_removes_html_endpoint_access(client):
    headers = {"Authorization": "Bearer alice-local-token"}
    saved = client.post("/chat", headers=headers,
        json={"message": "Create and save a monthly revenue report"}).json()
    rid, cid = saved["management"]["report_id"], saved["conversation_id"]
    assert client.get(f"/reports/{rid}/html", headers=headers).status_code == 200
    proposal = client.post("/reports/deletion-proposals", headers=headers,
        json={"conversation_id": cid, "report_ids": [rid]}).json()
    confirmed = client.post(f'/reports/deletion-proposals/{proposal["proposal_id"]}/confirmation', headers=headers,
        json={"conversation_id": cid, "confirm": True})
    assert confirmed.status_code == 200 and confirmed.json()["deleted"] == 1
    assert client.get(f"/reports/{rid}/html", headers=headers).status_code == 403
