"""Hashing for every secret we store (passwords, recovery codes).

All stored secrets go through hash_secret/verify_secret so that parameters
can be tuned in one place.
"""
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from ..settings import argon2_params


@lru_cache
def _hasher() -> PasswordHasher:
    p = argon2_params()
    return PasswordHasher(time_cost=p.time_cost, memory_cost=p.memory_kib, parallelism=p.parallelism)


def hash_secret(secret: str) -> str:
    return _hasher().hash(secret)


def verify_secret(stored_hash: str, candidate: str) -> bool:
    try:
        return _hasher().verify(stored_hash, candidate)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher().check_needs_rehash(stored_hash)
