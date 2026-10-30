import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Request

from .auth import CurrentUser, current_user
from .compat import client_version, shape_for_client
from .db import SCHEMA, NotesRepo
from .serializers import note_to_dict
from .storage import Storage


def create_app(conn: sqlite3.Connection | None = None, storage: Storage | None = None) -> FastAPI:
    app = FastAPI()
    conn = conn or sqlite3.connect("notes.db", check_same_thread=False)
    conn.executescript(SCHEMA)
    app.state.conn = conn
    app.state.notes = NotesRepo(conn)
    app.state.storage = storage or Storage()

    @app.get("/notes/{note_id}")
    def get_note(note_id: str, request: Request, user: CurrentUser = Depends(current_user)):
        note = app.state.notes.get_note_for_owner(note_id, user.id)
        if note is None:
            raise HTTPException(status_code=404, detail="note_not_found")
        return shape_for_client(note_to_dict(note), client_version(request))

    @app.get("/sync")
    def sync(since: str, request: Request, user: CurrentUser = Depends(current_user)):
        version = client_version(request)
        notes = app.state.notes.changed_since(user.id, since)
        return {"notes": [shape_for_client(note_to_dict(n), version) for n in notes]}

    return app
