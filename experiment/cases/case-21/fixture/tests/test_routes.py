import requests

from tests.conftest import FakeResponse


def test_get_item(client):
    resp = client.get("/items/A-1")
    assert resp.status_code == 200
    assert resp.get_json()["on_hand"] == 5


def test_unknown_item_is_404(client):
    resp = client.get("/items/NOPE")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"


def test_adjust_rejects_unknown_fields(client):
    resp = client.post("/items/A-1/adjust", json={"delta": 1, "extra": True})
    assert resp.status_code == 400


def test_adjust_cannot_go_negative(client):
    resp = client.post("/items/A-1/adjust", json={"delta": -6})
    assert resp.status_code == 400


def test_supplier_price_retries_on_timeout(client, fake_session):
    fake_session.queue(requests.Timeout("slow"))
    fake_session.queue(FakeResponse(200, {"price_cents": 1299}))
    resp = client.get("/items/A-1/supplier-price")
    assert resp.status_code == 200
    assert len(fake_session.calls) == 2
