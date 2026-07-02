"""POST /register — contract:

* 201 + UserResponse(id, email) on success; the password hash never leaks.
* Emails are case-insensitive and stored lowercase.
* Errors follow {"code", "message"} with a human-readable message.
"""

from tests.conftest import assert_error, make_user

# ---------------------------------------------------------------------------
# success
# ---------------------------------------------------------------------------


async def test_register_success_returns_201_with_user(client):
    ac, db, _ = client
    resp = await ac.post(
        "/register", json={"email": "new@example.com", "password": "password123"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert "id" in body


async def test_register_never_leaks_password_material(client):
    ac, db, _ = client
    resp = await ac.post(
        "/register", json={"email": "new@example.com", "password": "password123"}
    )
    body = resp.json()
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_stores_email_lowercase(client):
    ac, db, _ = client
    resp = await ac.post(
        "/register", json={"email": "MiXeD@Example.COM", "password": "password123"}
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "mixed@example.com"


# ---------------------------------------------------------------------------
# duplicates
# ---------------------------------------------------------------------------


async def test_register_duplicate_email_conflicts(client):
    ac, db, _ = client
    await make_user(db, email="dupe@example.com")
    resp = await ac.post(
        "/register", json={"email": "dupe@example.com", "password": "password123"}
    )
    assert_error(resp, 409, "user_already_exists")


async def test_register_duplicate_email_is_case_insensitive(client):
    ac, db, _ = client
    await make_user(db, email="dupe@example.com")
    resp = await ac.post(
        "/register", json={"email": "DuPe@ExAmPlE.com", "password": "password123"}
    )
    assert_error(resp, 409, "user_already_exists")


# ---------------------------------------------------------------------------
# validation — every 422 must explain the problem in plain language
# ---------------------------------------------------------------------------


async def test_register_short_password_rejected_with_explanation(client):
    ac, db, _ = client
    resp = await ac.post(
        "/register", json={"email": "new@example.com", "password": "short"}
    )
    assert_error(resp, 422, "validation_error")
    message = resp.json()["message"].lower()
    assert "password" in message
    assert "8" in message  # tells the user the minimum length


async def test_register_overlong_password_rejected_with_explanation(client):
    ac, db, _ = client
    resp = await ac.post(
        "/register", json={"email": "new@example.com", "password": "x" * 129}
    )
    assert_error(resp, 422, "validation_error")
    message = resp.json()["message"].lower()
    assert "password" in message
    assert "128" in message  # tells the user the maximum length


async def test_register_invalid_email_rejected_with_explanation(client):
    ac, db, _ = client
    resp = await ac.post(
        "/register", json={"email": "not-an-email", "password": "password123"}
    )
    assert_error(resp, 422, "validation_error")
    assert "email" in resp.json()["message"].lower()


async def test_register_missing_email_names_the_field(client):
    ac, db, _ = client
    resp = await ac.post("/register", json={"password": "password123"})
    assert_error(resp, 422, "validation_error")
    assert "email" in resp.json()["message"].lower()


async def test_register_missing_password_names_the_field(client):
    ac, db, _ = client
    resp = await ac.post("/register", json={"email": "new@example.com"})
    assert_error(resp, 422, "validation_error")
    assert "password" in resp.json()["message"].lower()


async def test_register_empty_body_rejected(client):
    ac, db, _ = client
    resp = await ac.post("/register", json={})
    assert_error(resp, 422, "validation_error")
