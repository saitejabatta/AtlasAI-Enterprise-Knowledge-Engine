import base64
import hashlib
import os
from pathlib import Path
from storage_paths import DATA_DIR

from cryptography.fernet import Fernet


BASE_DIR = DATA_DIR
LOCAL_SECRET_PATH = BASE_DIR / ".atlas_secret"


def get_secret_material():
    configured_secret = os.getenv(
        "ATLAS_SECRET_KEY"
    )

    if configured_secret:
        return configured_secret.encode(
            "utf-8"
        )

    if not LOCAL_SECRET_PATH.exists():
        LOCAL_SECRET_PATH.write_text(
            Fernet.generate_key().decode("utf-8"),
            encoding="utf-8"
        )

    return LOCAL_SECRET_PATH.read_text(
        encoding="utf-8"
    ).strip().encode("utf-8")


def get_fernet():
    secret_material = get_secret_material()

    try:
        return Fernet(secret_material)
    except Exception:
        digest = hashlib.sha256(
            secret_material
        ).digest()
        key = base64.urlsafe_b64encode(
            digest
        )

        return Fernet(key)


def encrypt_secret(value):
    return get_fernet().encrypt(
        value.encode("utf-8")
    ).decode("utf-8")


def decrypt_secret(value):
    return get_fernet().decrypt(
        value.encode("utf-8")
    ).decode("utf-8")
