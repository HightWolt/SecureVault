"""Криптографические примитивы."""
import base64
import secrets
from argon2.low_level import hash_secret_raw, Type
from cryptography.fernet import Fernet
from config import (
    SALT_SIZE, ARGON2_TIME_COST, ARGON2_MEM_COST, 
    ARGON2_PARALLELISM, KEY_LENGTH
)


def derive_key(password: str, salt: bytes) -> bytes:
    """Argon2id -> 32-байтный ключ."""
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=ARGON2_TIME_COST,
        memory_cost=ARGON2_MEM_COST,
        parallelism=ARGON2_PARALLELISM,
        hash_len=KEY_LENGTH,
        type=Type.ID,
    )


def encrypt(data: bytes, password: str) -> bytes:
    """Шифрует данные. Возвращает: salt + ciphertext."""
    salt = secrets.token_bytes(SALT_SIZE)
    key = base64.urlsafe_b64encode(derive_key(password, salt))
    return salt + Fernet(key).encrypt(data)


def decrypt(blob: bytes, password: str) -> bytes:
    """Расшифровывает. Бросает InvalidToken при неверном пароле."""
    salt, ciphertext = blob[:SALT_SIZE], blob[SALT_SIZE:]
    key = base64.urlsafe_b64encode(derive_key(password, salt))
    return Fernet(key).decrypt(ciphertext)