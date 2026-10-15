"""
Utilidades de autenticación para YUNPAR ERP.

- Hash de contraseñas con PBKDF2 (solo librería estándar, sin dependencias nuevas).
- Verificación con soporte de migración perezosa: si el valor almacenado todavía es
  texto plano (registros antiguos), la verificación funciona y el login lo re-hashea.
"""

import hashlib
import secrets

_ITERATIONS = 120_000
_PREFIX = "pbkdf2$"


def hash_password(password: str) -> str:
    """Devuelve la contraseña hasheada en formato 'pbkdf2$<salt>$<hex>'."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    )
    return f"{_PREFIX}{salt}${dk.hex()}"


def is_hashed(stored: str) -> bool:
    """Indica si el valor almacenado ya es un hash (vs. texto plano legado)."""
    return bool(stored) and isinstance(stored, str) and stored.startswith(_PREFIX)


def verify_password(password: str, stored: str) -> bool:
    """
    Verifica una contraseña contra el valor almacenado.
    Soporta valores legados en texto plano para poder migrarlos sin fricción.
    """
    if not stored or not isinstance(stored, str):
        return False

    if is_hashed(stored):
        try:
            _, salt, hex_dk = stored.split("$", 2)
            dk = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
            )
            return secrets.compare_digest(dk.hex(), hex_dk)
        except (ValueError, TypeError):
            return False

    # Compatibilidad con contraseñas antiguas guardadas en texto plano.
    return secrets.compare_digest(password, stored)
