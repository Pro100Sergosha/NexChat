"""TokenVerifier.decode — chat only verifies JWTs issued by auth, it never
issues them. Type/sub-presence enforcement lives one layer up in
infra/web/dependables.py (see tests/web/test_dependables.py); decode() here
only proves the signature is valid and the token isn't expired.

# TODO: chat does not check auth's Redis blacklist (signature+expiry only,
# per ARCHITECTURE.md) — a revoked token stays valid here until natural
# expiry. Accepted trade-off, not a bug.
"""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.chat.exceptions import TokenExpired, TokenInvalid
from app.core.chat.security import TokenVerifier
from app.core.config import settings


def _b64url(data: dict) -> str:
    raw = json.dumps(data).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class TestTokenVerifier:
    def setup_method(self):
        self.verifier = TokenVerifier(settings)

    def _sign(
        self, claims: dict, *, secret: str | None = None, algorithm: str | None = None
    ) -> str:
        return jwt.encode(
            claims,
            secret if secret is not None else settings.JWT_SECRET_KEY,
            algorithm=algorithm or settings.jwt_algorithm,
        )

    def _valid_claims(self, **overrides) -> dict:
        now = datetime.now(UTC)
        claims = {
            "sub": "user-1",
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=15),
        }
        claims.update(overrides)
        return claims

    def test_decode_roundtrip_returns_sub(self):
        token = self._sign(self._valid_claims(sub="user-42"))
        claims = self.verifier.decode(token)
        assert claims["sub"] == "user-42"

    def test_decode_malformed_raises_invalid(self):
        with pytest.raises(TokenInvalid):
            self.verifier.decode("not-a-jwt")

    def test_decode_empty_string_raises_invalid(self):
        with pytest.raises(TokenInvalid):
            self.verifier.decode("")

    def test_decode_wrong_signature_raises_invalid(self):
        forged = self._sign(self._valid_claims(), secret="different-secret")
        with pytest.raises(TokenInvalid):
            self.verifier.decode(forged)

    def test_decode_expired_raises_expired(self):
        now = datetime.now(UTC)
        expired = self._sign(
            self._valid_claims(
                iat=now - timedelta(hours=2), exp=now - timedelta(hours=1)
            )
        )
        with pytest.raises(TokenExpired):
            self.verifier.decode(expired)

    def test_decode_missing_exp_raises_invalid(self):
        claims = self._valid_claims()
        del claims["exp"]
        token = self._sign(claims)
        with pytest.raises(TokenInvalid):
            self.verifier.decode(token)

    def test_decode_token_without_type_returns_claims(self):
        """decode() only parses/verifies — type enforcement lives one layer up."""
        claims = self._valid_claims()
        del claims["type"]
        token = self._sign(claims)
        result = self.verifier.decode(token)
        assert result["sub"] == "user-1"
        assert "type" not in result

    def test_decode_token_without_sub_returns_claims(self):
        """decode() doesn't enforce sub presence — dependables.py does."""
        claims = self._valid_claims()
        del claims["sub"]
        token = self._sign(claims)
        result = self.verifier.decode(token)
        assert "sub" not in result

    def test_decode_rejects_none_algorithm(self):
        header = _b64url({"alg": "none", "typ": "JWT"})
        payload = _b64url(self._valid_claims())
        forged = f"{header}.{payload}."
        with pytest.raises(TokenInvalid):
            self.verifier.decode(forged)

    def test_decode_rejects_unexpected_algorithm(self):
        # signed with a different (still valid-looking) algorithm than the
        # service is configured to accept
        token = self._sign(self._valid_claims(), algorithm="HS512")
        with pytest.raises(TokenInvalid):
            self.verifier.decode(token)

    def test_decode_wrong_type_claim_still_parses(self):
        """A refresh token decodes fine at this layer — it's rejected later
        by dependables.py, not here."""
        token = self._sign(self._valid_claims(type="refresh"))
        claims = self.verifier.decode(token)
        assert claims["type"] == "refresh"
