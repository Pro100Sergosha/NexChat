from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import jwt

from app.core.auth.exceptions import TokenExpired, TokenInvalid
from app.core.auth.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    PasswordHasher,
    TokenService,
)
from app.core.config import settings

# ---------------------------------------------------------------------------
# PasswordHasher
# ---------------------------------------------------------------------------


class TestPasswordHasher:
    def setup_method(self):
        self.hasher = PasswordHasher()

    def test_hash_is_not_plaintext(self):
        hashed = self.hasher.hash("password123")
        assert hashed != "password123"

    def test_hash_is_deterministic_verify(self):
        hashed = self.hasher.hash("password123")
        assert self.hasher.verify("password123", hashed) is True

    def test_wrong_password_fails(self):
        hashed = self.hasher.hash("password123")
        assert self.hasher.verify("wrong-password", hashed) is False

    def test_salt_makes_hashes_unique(self):
        assert self.hasher.hash("same") != self.hasher.hash("same")

    def test_password_over_72_bytes_truncated(self):
        # bcrypt caps at 72 bytes; the 73rd+ char must not change verification
        base = "a" * 72
        hashed = self.hasher.hash(base)
        assert self.hasher.verify(base + "extra-tail", hashed) is True

    def test_empty_password_roundtrips(self):
        hashed = self.hasher.hash("")
        assert self.hasher.verify("", hashed) is True
        assert self.hasher.verify("not-empty", hashed) is False

    @pytest.mark.parametrize(
        "corrupt",
        [
            "",  # empty column
            "not-a-bcrypt-hash",  # plaintext leaked into the column
            "$2b$12$truncated",  # cut off mid-hash
            "5f4dcc3b5aa765d61d8327deb882cf99",  # md5 from a legacy system
        ],
    )
    def test_corrupt_stored_hash_returns_false(self, corrupt):
        """A corrupt DB value must fail verification quietly (401 for the
        user), never crash the request with a 500."""
        assert self.hasher.verify("password123", corrupt) is False


# ---------------------------------------------------------------------------
# TokenService
# ---------------------------------------------------------------------------


class TestTokenService:
    def setup_method(self):
        self.tokens = TokenService(settings)

    def _decode_raw(self, token: str) -> dict:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.jwt_algorithm])

    def test_access_token_has_access_type(self):
        claims = self._decode_raw(self.tokens.create_access("user-1"))
        assert claims["type"] == ACCESS_TOKEN_TYPE
        assert claims["sub"] == "user-1"

    def test_refresh_token_has_refresh_type(self):
        claims = self._decode_raw(self.tokens.create_refresh("user-1"))
        assert claims["type"] == REFRESH_TOKEN_TYPE

    def test_tokens_have_unique_jti(self):
        a = self._decode_raw(self.tokens.create_access("user-1"))
        b = self._decode_raw(self.tokens.create_access("user-1"))
        assert a["jti"] != b["jti"]

    def test_expiry_is_in_the_future(self):
        now = datetime.now(UTC).timestamp()
        access = self._decode_raw(self.tokens.create_access("user-1"))
        refresh = self._decode_raw(self.tokens.create_refresh("user-1"))
        assert access["exp"] > now
        assert refresh["exp"] > now

    def test_refresh_lives_longer_than_access(self):
        access = self._decode_raw(self.tokens.create_access("user-1"))
        refresh = self._decode_raw(self.tokens.create_refresh("user-1"))
        assert refresh["exp"] > access["exp"]

    def test_decode_roundtrip(self):
        token = self.tokens.create_access("user-42")
        claims = self.tokens.decode(token)
        assert claims["sub"] == "user-42"
        assert claims["type"] == ACCESS_TOKEN_TYPE

    def test_decode_malformed_raises_invalid(self):
        with pytest.raises(TokenInvalid):
            self.tokens.decode("not-a-jwt")

    def test_decode_wrong_signature_raises_invalid(self):
        forged = jwt.encode({"sub": "x"}, "different-secret", algorithm=settings.jwt_algorithm)
        with pytest.raises(TokenInvalid):
            self.tokens.decode(forged)

    def test_decode_expired_raises_expired(self):
        now = datetime.now(UTC)
        expired = jwt.encode(
            {
                "sub": "user-1",
                "jti": uuid4().hex,
                "type": ACCESS_TOKEN_TYPE,
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(TokenExpired):
            self.tokens.decode(expired)

    def test_decode_token_without_type_returns_claims(self):
        """decode() only parses/verifies — type enforcement lives in the service."""
        now = datetime.now(UTC)
        typeless = jwt.encode(
            {"sub": "user-1", "jti": uuid4().hex, "iat": now, "exp": now + timedelta(minutes=5)},
            settings.JWT_SECRET_KEY,
            algorithm=settings.jwt_algorithm,
        )
        claims = self.tokens.decode(typeless)
        assert claims["sub"] == "user-1"
        assert "type" not in claims
