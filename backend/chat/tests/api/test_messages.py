"""GET /messages/{conversation_id}?limit=&offset=

Returns messages of a conversation ordered by `created_at` ascending
(oldest first), paginated via `limit`/`offset` (default limit 50, max 100).
Requires a valid access token belonging to a participant of the
conversation.
"""

from tests.conftest import (
    assert_error,
    auth_headers,
    make_conversation,
    make_message,
    make_token,
)


async def test_returns_messages_in_ascending_order(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    first = await make_message(
        db_session, conversation_id=conversation.id, sender_id="user-a", content="hi"
    )
    second = await make_message(
        db_session, conversation_id=conversation.id, sender_id="user-b", content="hey"
    )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [m["id"] for m in body] == [first.id, second.id]


async def test_response_shape_has_all_fields(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    message = await make_message(
        db_session, conversation_id=conversation.id, sender_id="user-a", content="hi"
    )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    body = resp.json()[0]
    assert body == {
        "id": message.id,
        "conversation_id": conversation.id,
        "sender_id": "user-a",
        "content": "hi",
        "created_at": body["created_at"],
    }
    assert isinstance(body["created_at"], str)


async def test_default_limit_is_50(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    for i in range(55):
        await make_message(
            db_session,
            conversation_id=conversation.id,
            sender_id="user-a",
            content=f"msg-{i}",
        )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    assert len(resp.json()) == 50


async def test_custom_limit(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    for i in range(5):
        await make_message(
            db_session,
            conversation_id=conversation.id,
            sender_id="user-a",
            content=f"msg-{i}",
        )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}?limit=2", headers=auth_headers(token)
    )

    assert len(resp.json()) == 2


async def test_offset_skips_older_messages(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    messages = [
        await make_message(
            db_session,
            conversation_id=conversation.id,
            sender_id="user-a",
            content=f"msg-{i}",
        )
        for i in range(3)
    ]
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}?offset=1", headers=auth_headers(token)
    )

    body = resp.json()
    assert [m["id"] for m in body] == [messages[1].id, messages[2].id]


async def test_limit_and_offset_combined(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    messages = [
        await make_message(
            db_session,
            conversation_id=conversation.id,
            sender_id="user-a",
            content=f"msg-{i}",
        )
        for i in range(5)
    ]
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}?limit=2&offset=2", headers=auth_headers(token)
    )

    body = resp.json()
    assert [m["id"] for m in body] == [messages[2].id, messages[3].id]


async def test_limit_above_max_does_not_error(client, db_session):
    # NOTE: clamping to MAX_PAGE_SIZE (100) with real volume is exercised at
    # the unit/test_service.py level — here we only assert the endpoint
    # accepts an oversized limit instead of rejecting it.
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    await make_message(
        db_session, conversation_id=conversation.id, sender_id="user-a", content="hi"
    )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}?limit=1000", headers=auth_headers(token)
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_limit_zero_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}?limit=0", headers=auth_headers(token)
    )

    assert resp.status_code == 422


async def test_negative_limit_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}?limit=-1", headers=auth_headers(token)
    )

    assert resp.status_code == 422


async def test_negative_offset_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}?offset=-1", headers=auth_headers(token)
    )

    assert resp.status_code == 422


async def test_empty_conversation_returns_empty_list(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a")

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    assert resp.status_code == 200
    assert resp.json() == []


async def test_nonexistent_conversation_returns_404(client, db_session):
    token = make_token(sub="user-a")

    resp = await client.get("/messages/999999", headers=auth_headers(token))

    assert_error(resp, 404, "conversation_not_found")


async def test_non_participant_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-c")

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    assert_error(resp, 404, "conversation_not_found")


async def test_invalid_conversation_id_format_rejected(client, db_session):
    token = make_token(sub="user-a")

    resp = await client.get("/messages/not-an-id", headers=auth_headers(token))

    assert resp.status_code == 422


async def test_missing_token_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )

    resp = await client.get(f"/messages/{conversation.id}")

    assert_error(resp, 401, "not_authenticated")


async def test_wrong_auth_scheme_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )

    resp = await client.get(
        f"/messages/{conversation.id}", headers={"Authorization": "Basic abc123"}
    )

    assert_error(resp, 401, "not_authenticated")


async def test_garbage_token_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers("not-a-real-jwt")
    )

    assert_error(resp, 401, "token_invalid")


async def test_expired_token_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a", expires_in=-60)

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    assert_error(resp, 401, "token_expired")


async def test_wrong_signature_token_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a", secret="wrong-secret")

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    assert_error(resp, 401, "token_invalid")


async def test_refresh_token_used_as_access_rejected(client, db_session):
    conversation = await make_conversation(
        db_session, user_a_id="user-a", user_b_id="user-b"
    )
    token = make_token(sub="user-a", token_type="refresh")

    resp = await client.get(
        f"/messages/{conversation.id}", headers=auth_headers(token)
    )

    assert_error(resp, 401, "token_invalid")
