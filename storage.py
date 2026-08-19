"""Работа с зашифрованным файлом хранилища."""
import os
import json
from pathlib import Path
from cryptography.fernet import InvalidToken

from config import VAULT_FILE
from crypto import encrypt, decrypt


class VaultCorruptedError(Exception):
    pass


class VaultAuthError(Exception):
    pass


def vault_exists() -> bool:
    return VAULT_FILE.exists()


def load_vault(password: str) -> dict:
    if not vault_exists():
        return {}
    try:
        raw = decrypt(VAULT_FILE.read_bytes(), password)
        return json.loads(raw.decode("utf-8"))
    except InvalidToken:
        raise VaultAuthError("Неверный мастер-пароль")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise VaultCorruptedError(f"Файл повреждён: {e}")


def save_vault(data: dict, password: str) -> None:
    blob = encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8"), password)
    VAULT_FILE.write_bytes(blob)
    # Только владелец может читать/писать
    try:
        os.chmod(VAULT_FILE, 0o600)
    except OSError:
        pass # Windows не поддерживает chmod


def init_vault(password: str) -> None:
    save_vault({}, password)