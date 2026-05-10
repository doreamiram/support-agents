import hashlib
import hmac


class SignatureVerificationError(Exception):
    """Raised when a webhook signature is absent, malformed, or invalid."""


class SignatureVerifier:
    """Stateless HMAC-SHA256 webhook signature verifier."""

    _PREFIX = "sha256="

    def verify(
        self,
        *,
        tenant_secret: str,
        payload_bytes: bytes,
        signature_header: str,
    ) -> None:
        """
        Verify an inbound webhook signature.

        Expected header format: ``sha256=<hex_digest>``

        Raises ``SignatureVerificationError`` on any failure.  Uses
        ``hmac.compare_digest`` to prevent timing attacks.
        """
        if not signature_header.startswith(self._PREFIX):
            raise SignatureVerificationError(
                f"Signature header must start with {self._PREFIX!r}"
            )

        provided = signature_header[len(self._PREFIX):]
        expected = hmac.new(
            tenant_secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, provided):
            raise SignatureVerificationError("Webhook signature mismatch")

    def compute(self, *, tenant_secret: str, payload_bytes: bytes) -> str:
        """Return the correctly formatted signature for *payload_bytes*."""
        digest = hmac.new(
            tenant_secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()
        return f"{self._PREFIX}{digest}"
