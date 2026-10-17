from pipeline.transform import normalize


def test_missing_fields_are_quarantined_with_reason():
    clean, held = normalize([{"event_id": "e1", "event_type": "Click"}])
    assert clean == []
    assert held[0]["reason"].startswith("missing_fields:")


def test_duplicates_are_dropped_and_currency_uppercased():
    ev = {"event_id": "e1", "event_type": "Order", "occurred_at": "2026-10-01T10:00:00Z",
          "user_id": 7, "amount": "9.99", "currency": "eur"}
    clean, held = normalize([ev, dict(ev)])
    assert len(clean) == 1 and held == []
    assert clean[0]["currency"] == "EUR"
