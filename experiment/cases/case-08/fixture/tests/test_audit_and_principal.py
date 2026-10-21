import pytest
from fastapi import HTTPException

from authsvc.cache import TTLMemo
from authsvc.crypto import hash_secret, random_base62, verify_secret
from authsvc.principal import Principal
from authsvc.redact import mask_bearer, scrub


def test_scrub_drops_sensitive_fields_recursively():
    data = {"name": "ci", "client_secret": "x", "nested": {"refresh_token": "y", "keep": 1}}
    assert scrub(data) == {"name": "ci", "nested": {"keep": 1}}


def test_mask_bearer_replaces_jwt_signature():
    assert mask_bearer("Bearer aaa.bbb.ccc") == "Bearer aaa.bbb.<redacted>"


def test_hash_roundtrip():
    h = hash_secret("correct horse")
    assert verify_secret(h, "correct horse")
    assert not verify_secret(h, "wrong")
    assert not verify_secret("not-a-hash", "anything")


def test_random_base62_alphabet():
    value = random_base62(32)
    assert len(value) == 32 and value.isalnum()


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


def test_memo_expires_and_evicts():
    now = [0.0]
    memo = TTLMemo(ttl=10, clock=lambda: now[0])
    loads = []
    load = lambda: loads.append(1) or len(loads)
    assert memo.get_or_load("a", load) == 1
    now[0] = 5
    assert memo.get_or_load("a", load) == 1
    now[0] = 11
    assert memo.get_or_load("a", load) == 2
    memo.evict("a")
    assert memo.get_or_load("a", load) == 3
