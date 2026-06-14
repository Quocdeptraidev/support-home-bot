import hashlib
import hmac


def verify_facebook_signature(
    raw_body: bytes,
    signature_header: str | None,
    app_secret: str,
) -> bool:
    if not signature_header or not app_secret:
        return False

    algorithm, separator, provided_digest = signature_header.partition("=")
    if separator != "=" or algorithm != "sha256" or not provided_digest:
        return False

    expected_digest = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(provided_digest, expected_digest)
