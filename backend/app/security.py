import hashlib
import hmac
import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.settings import Settings


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(digest.hex(), expected)
    except (ValueError, TypeError):
        return False


def hash_device_token(token: str) -> str:
    # Tokens são aleatórios de alta entropia; apenas o hash fica no banco.
    return hashlib.sha256(token.encode()).hexdigest()


def session_serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        settings.session_secret.get_secret_value(), salt="movement-operator"
    )


def password_fingerprint(password_hash: str) -> str:
    # Trocar a senha altera a impressão e invalida as sessões emitidas antes.
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def issue_session(
    settings: Settings,
    *,
    username: str,
    user_id: str | None,
    password_hash: str,
    session_version: int = 0,
) -> str:
    return session_serializer(settings).dumps(
        {
            "sub": username,
            "uid": user_id,
            "pv": password_fingerprint(password_hash),
            "sv": session_version,
        }
    )


def read_session(token: str, settings: Settings) -> dict | None:
    try:
        payload = session_serializer(settings).loads(token, max_age=settings.session_ttl_seconds)
    except (BadSignature, SignatureExpired):
        return None
    return payload if isinstance(payload, dict) and isinstance(payload.get("sub"), str) else None
