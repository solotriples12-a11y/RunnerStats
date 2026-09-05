"""Sesión por cookie con una sola contraseña.

Mismo planteamiento que Notyo: no hay usuario, solo una contraseña
compartida. Al acertarla se entrega una cookie con un token HMAC derivado de
esa misma contraseña, así que no hay estado de sesión que guardar.

Falla cerrado: sin `RUNNERSTATS_PASSWORD` configurada no se sirve nada.
"""

import hashlib
import hmac
import os

COOKIE = "runnerstats_session"
DIAS = 30
_MENSAJE = b"runnerstats-session-v1"


def _password() -> str:
    return os.environ.get("RUNNERSTATS_PASSWORD", "")


def configurada() -> bool:
    return bool(_password())


def token() -> str | None:
    """Token opaco derivado de la contraseña. Determinista: cambiar la
    contraseña invalida todas las sesiones."""
    clave = _password()
    if not clave:
        return None
    return hmac.new(clave.encode(), _MENSAJE, hashlib.sha256).hexdigest()


def password_correcta(intento: str) -> bool:
    esperada = _password()
    return bool(esperada) and hmac.compare_digest(intento, esperada)


def sesion_valida(cookie: str | None) -> bool:
    esperado = token()
    return bool(cookie) and bool(esperado) and hmac.compare_digest(cookie, esperado)
