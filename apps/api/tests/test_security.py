import hashlib
import hmac

from app.core.security import verify_facebook_signature


def test_verify_facebook_signature_accepts_valid_digest() -> None:
    body = b'{"object":"page"}'
    secret = "app-secret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_facebook_signature(body, f"sha256={digest}", secret)


def test_verify_facebook_signature_rejects_invalid_digest() -> None:
    assert not verify_facebook_signature(b"payload", "sha256=invalid", "app-secret")
    assert not verify_facebook_signature(b"payload", None, "app-secret")
