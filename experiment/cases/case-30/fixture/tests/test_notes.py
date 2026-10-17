def test_owner_can_read_note(client, note):
    r = client.get(f"/notes/{note['id']}", headers={"X-User-ID": "u1", "X-App-Version": "4.2.0"})
    assert r.status_code == 200
    assert r.json()["title"] == "Groceries"


def test_other_user_gets_404(client, note):
    r = client.get(f"/notes/{note['id']}", headers={"X-User-ID": "u2"})
    assert r.status_code == 404


def test_old_clients_do_not_get_gated_keys(app, client, note):
    app.state.conn.execute("UPDATE notes SET reminders = ? WHERE id = ?", ('[{"at": "09:00"}]', note["id"]))
    old = client.get(f"/notes/{note['id']}", headers={"X-User-ID": "u1", "X-App-Version": "3.5.9"})
    new = client.get(f"/notes/{note['id']}", headers={"X-User-ID": "u1", "X-App-Version": "3.6.0"})
    assert "reminders" not in old.json()
    assert new.json()["reminders"] == [{"at": "09:00"}]


def test_sync_returns_changed_notes(client, note):
    r = client.get("/sync", params={"since": "1970-01-01"}, headers={"X-User-ID": "u1"})
    assert [n["id"] for n in r.json()["notes"]] == [note["id"]]
