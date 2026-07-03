"""GET /conversations

Returns the list of conversations the current user (from JWT `sub`) is a
participant in, ordered by most recent activity first (last message time,
falling back to conversation creation time when empty). Requires a valid
access token.

# TODO: no POST /conversations — conversation is created implicitly on the
# first WS message with a recipient_id. If a "start empty conversation"
# flow is ever needed, add the explicit endpoint here.
"""

from tests.conftest import (
    assert_error,
    auth_headers,
    make_conversation,
    make_message,
    make_token,
)


async def test_returns_conversations_for_current_user(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a")

    resp = await client.get("/conversations", headers=auth_headers(token))

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == conversation.id
    assert body[0]["other_user_id"] == "user-b"


async def test_returns_conversation_when_user_is_participant_b(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-b")

    resp = await client.get("/conversations", headers=auth_headers(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["id"] == conversation.id
    assert body[0]["other_user_id"] == "user-a"


async def test_empty_list_when_no_conversations(client, db_session):
    token = make_token(sub="user-a")

    resp = await client.get("/conversations", headers=auth_headers(token))

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body == []


async def test_does_not_return_other_users_conversations(client, db_session):
    await make_conversation(db_session, user_a_id="user-a", user_b_id="user-b")
    token = make_token(sub="user-c")

    resp = await client.get("/conversations", headers=auth_headers(token))

    assert resp.status_code == 200
    assert resp.json() == []


async def test_response_shape_has_all_fields(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a")

    resp = await client.get("/conversations", headers=auth_headers(token))

    body = resp.json()[0]
    assert body == {
        "id": conversation.id,
        "other_user_id": "user-b",
        "created_at": body["created_at"],
        "last_message_at": body["last_message_at"],
    }
    assert isinstance(body["created_at"], str)


async def test_ordered_by_most_recent_activity(client, db_session):
    older = await make_conversation(db_session, user_a_id="user-a", user_b_id="user-b")
    newer = await make_conversation(db_session, user_a_id="user-a", user_b_id="user-c")
    # bump `older`'s activity above `newer`'s by sending a message after it was created
    await make_message(
        db_session, conversation_id=older.id, sender_id="user-a", content="hi"
    )
    token = make_token(sub="user-a")

    resp = await client.get("/conversations", headers=auth_headers(token))

    body = resp.json()
    assert [c["id"] for c in body] == [older.id, newer.id]


async def test_missing_token_rejected(client, db_session):
    resp = await client.get("/conversations")

    assert_error(resp, 401, "not_authenticated")


async def test_wrong_auth_scheme_rejected(client, db_session):
    resp = await client.get("/conversations", headers={"Authorization": "Basic abc123"})

    assert_error(resp, 401, "not_authenticated")


async def test_garbage_token_rejected(client, db_session):
    resp = await client.get("/conversations", headers=auth_headers("not-a-real-jwt"))

    assert_error(resp, 401, "token_invalid")


async def test_expired_token_rejected(client, db_session):
    token = make_token(sub="user-a", expires_in=-60)

    resp = await client.get("/conversations", headers=auth_headers(token))

    assert_error(resp, 401, "token_expired")


async def test_wrong_signature_token_rejected(client, db_session):
    token = make_token(sub="user-a", secret="wrong-secret")

    resp = await client.get("/conversations", headers=auth_headers(token))

    assert_error(resp, 401, "token_invalid")


async def test_refresh_token_used_as_access_rejected(client, db_session):
    token = make_token(sub="user-a", token_type="refresh")

    resp = await client.get("/conversations", headers=auth_headers(token))

    assert_error(resp, 401, "token_invalid")
