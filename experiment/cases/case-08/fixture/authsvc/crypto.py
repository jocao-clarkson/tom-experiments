"""Credential helpers: random tokens, and hashing for every secret we store.

Stored secrets (passwords, recovery codes, ...) go through hash_secret and
verify_secret so that the scheme and its parameters are tuned in one place.
"""
import hashlib
import hmac
import os
import secrets
import string

from .settings import hash_params

_BASE62 = string.ascii_letters + string.digits


def random_base62(length: int) -> str:
    return "".join(secrets.choice(_BASE62) for _ in range(length))


def recovery_code() -> str:
    """Ten-character code shown once to the user, grouped for readability."""
    raw = random_base62(10).lower()
    return f"{raw[:5]}-{raw[5:]}"


def hash_secret(secret: str) -> str:
    p = hash_params()
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(p.algorithm, secret.encode(), salt, p.iterations)
    return f"pbkdf2_{p.algorithm}${p.iterations}${salt.hex()}${digest.hex()}"


def verify_secret(stored_hash: str, candidate: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = stored_hash.split("$")
        algorithm = scheme.removeprefix("pbkdf2_")
        digest = hashlib.pbkdf2_hmac(algorithm, candidate.encode(), bytes.fromhex(salt_hex), int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def needs_rehash(stored_hash: str) -> bool:
    p = hash_params()
    return not stored_hash.startswith(f"pbkdf2_{p.algorithm}${p.iterations}$")
