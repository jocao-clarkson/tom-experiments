from conftest import FakeResponse


def _seed(repo, status="authorized"):
    repo.insert_order({
        "id": "ord_1", "customer_id": "cus_1", "charge_id": "ch_1",
        "captured_cents": 0, "currency": "USD", "status": status,
    })


def test_capture_updates_amount(client, repo, fake_session):
    _seed(repo)
    fake_session.queue(FakeResponse(200, {"amount_captured": 4200}))
    resp = client.post("/orders/ord_1/capture")
    assert resp.status_code == 200
    assert resp.get_json()["captured_cents"] == 4200


def test_capture_retries_on_503(client, repo, fake_session):
    _seed(repo)
    fake_session.queue(FakeResponse(503))
    fake_session.queue(FakeResponse(200, {"amount_captured": 100}))
    resp = client.post("/orders/ord_1/capture")
    assert resp.status_code == 200
    assert len(fake_session.calls) == 2


def test_capture_wrong_state_is_conflict(client, repo):
    _seed(repo, status="captured")
    resp = client.post("/orders/ord_1/capture")
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "invalid_state"


def test_unknown_order_is_404(client):
    resp = client.get("/orders/nope")
    assert resp.status_code == 404
