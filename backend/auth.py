import hashlib
import hmac
import os

COOKIE_NAME = "lawcubator_session"
_ITERATIONS = 200_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256:{_ITERATIONS}:{salt.hex()}:{digest.hex()}"


def _stored_hash() -> str:
    return os.environ.get("APP_PASSWORD_HASH", "").strip()


def auth_required() -> bool:
    # No hash configured (e.g. local dev) means no login screen.
    return bool(_stored_hash())


def verify_password(password: str) -> bool:
    stored = _stored_hash()
    try:
        _, iterations, salt_hex, digest_hex = stored.split(":")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def session_token() -> str:
    # Derived from the stored hash, so it survives restarts/updates and is
    # invalidated automatically when the password is changed.
    return hmac.new(_stored_hash().encode(), b"lawcubator-session", hashlib.sha256).hexdigest()


def is_authenticated(cookie_value: str | None) -> bool:
    return bool(cookie_value) and hmac.compare_digest(cookie_value, session_token())
