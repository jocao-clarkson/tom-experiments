import pytest
from fastapi import HTTPException

from authsvc.audit import scrub
from authsvc.principal import Principal
from authsvc.security.hashing import hash_secret, verify_secret


def test_scrub_drops_sensitive_keys_recursively():
    data = {"name": "ci", "secret": "x", "nested": {"token": "y", "keep": 1}}
    assert scrub(data) == {"name": "ci", "nested": {"keep": 1}}


def test_hash_roundtrip():
    h = hash_secret("correct horse")
    assert verify_secret(h, "correct horse")
    assert not verify_secret(h, "wrong")
    assert not verify_secret("not-a-hash", "anything")


def test_require_scope():
    p = Principal(subject="sa_1", org_id="o1", kind="service_account", scopes=frozenset({"invoices:read"}))
    p.require_scope("invoices:read")
    with pytest.raises(HTTPException) as exc:
        p.require_scope("invoices:write")
    assert exc.value.status_code == 403


def test_only_org_admin_users_pass_admin_check():
    admin = Principal(subject="u1", org_id="o1", kind="user", role="admin")
    admin.require_org_admin("o1")
    with pytest.raises(HTTPException):
        admin.require_org_admin("o2")
    sa = Principal(subject="sa_1", org_id="o1", kind="service_account", role="admin")
    with pytest.raises(HTTPException):
        sa.require_org_admin("o1")
