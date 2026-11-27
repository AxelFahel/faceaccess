"""Cryptographic helpers.

* AES-256-GCM authenticated encryption with a key ring (key id stored alongside
  the ciphertext) for biometric templates and other sensitive values.
* Associated data binds a ciphertext to its owner record, so swapping
  templates between rows makes decryption fail.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

NONCE_SIZE = 12


class DecryptionError(Exception):
    pass


@dataclass(frozen=True)
class EncryptedBlob:
    key_id: str
    nonce: bytes
    ciphertext: bytes


class KeyRing:
    def __init__(self, keys: dict[str, bytes], active_key_id: str):
        if active_key_id not in keys:
            raise ValueError("active key id missing from key ring")
        self._keys = dict(keys)
        self.active_key_id = active_key_id

    def encrypt(self, plaintext: bytes, aad: bytes) -> EncryptedBlob:
        nonce = os.urandom(NONCE_SIZE)
        ct = AESGCM(self._keys[self.active_key_id]).encrypt(nonce, plaintext, aad)
        return EncryptedBlob(self.active_key_id, nonce, ct)

    def decrypt(self, blob: EncryptedBlob, aad: bytes) -> bytes:
        key = self._keys.get(blob.key_id)
        if key is None:
            raise DecryptionError(f"unknown key id {blob.key_id}")
        try:
            return AESGCM(key).decrypt(blob.nonce, blob.ciphertext, aad)
        except Exception as exc:  # InvalidTag
            raise DecryptionError("authentication failed") from exc

    def has_key(self, key_id: str) -> bool:
        return key_id in self._keys


def biometric_key_ring() -> KeyRing:
    s = get_settings()
    return KeyRing(s.biometric_key_ring(), s.biometric_active_key_id)


def data_key_ring() -> KeyRing:
    return KeyRing({"d1": get_settings().data_key()}, "d1")


# --- Templates ----------------------------------------------------------

def template_aad(enrollment_id: str, employee_id: str, engine_version: str) -> bytes:
    return f"faceaccess:template:v1:{enrollment_id}:{employee_id}:{engine_version}".encode()


def serialize_template(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype="<f4").ravel().tobytes()


def deserialize_template(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype="<f4").copy()


# --- Misc ---------------------------------------------------------------

def encrypt_str(value: str, aad: str) -> bytes:
    """Encrypt a short string; returns key_id|nonce|ct packed bytes."""
    blob = data_key_ring().encrypt(value.encode(), aad.encode())
    kid = blob.key_id.encode()
    return bytes([len(kid)]) + kid + blob.nonce + blob.ciphertext


def decrypt_str(packed: bytes, aad: str) -> str:
    klen = packed[0]
    kid = packed[1 : 1 + klen].decode()
    nonce = packed[1 + klen : 1 + klen + NONCE_SIZE]
    ct = packed[1 + klen + NONCE_SIZE :]
    return data_key_ring().decrypt(EncryptedBlob(kid, nonce, ct), aad.encode()).decode()


def sha256_hex(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def hmac_sha256_hex(key: str, message: str) -> str:
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def random_numeric_code(digits: int = 8) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(digits))
