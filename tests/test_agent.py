from unittest.mock import MagicMock, patch

import httpx
import openai

from src.agent import _trim_history, respond
from src.order_state import OrderState
from src.tools import CallSession


def _timeout_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.APITimeoutError(request)


def _fake_response(text: str):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=text, tool_calls=None))]
    return response


def test_trim_history_keeps_last_10_turns():
    history = []
    for i in range(15):
        history.append({"role": "user", "content": f"u{i}"})
        history.append({"role": "assistant", "content": f"a{i}"})

    trimmed = _trim_history(history)
    assert len(trimmed) == 20
    assert trimmed[0] == {"role": "user", "content": "u5"}
    assert trimmed[-1] == {"role": "assistant", "content": "a14"}


def test_trim_history_drops_non_user_assistant_messages():
    history = [
        {"role": "user", "content": "u1"},
        {"role": "tool", "content": "some old tool result", "tool_call_id": "x"},
        {"role": "assistant", "content": "a1"},
    ]
    trimmed = _trim_history(history)
    assert trimmed == [{"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}]


@patch("src.agent._get_client")
def test_respond_retries_once_then_succeeds(mock_get_client):
    client = MagicMock()
    client.chat.completions.create.side_effect = [_timeout_error(), _fake_response("هلا والله")]
    mock_get_client.return_value = client

    session = CallSession(order=OrderState())
    reply = respond(session, [], "مرحبا")

    assert reply.text == "هلا والله"
    assert client.chat.completions.create.call_count == 2
    assert session.consecutive_failures == 0


@patch("src.agent._get_client")
def test_respond_timeout_twice_returns_apology(mock_get_client):
    client = MagicMock()
    client.chat.completions.create.side_effect = [_timeout_error(), _timeout_error()]
    mock_get_client.return_value = client

    session = CallSession(order=OrderState())
    reply = respond(session, [], "مرحبا")

    assert "مشكلة" in reply.text
    assert session.transferred is False
    assert session.consecutive_failures == 1


@patch("src.agent._get_client")
def test_respond_two_consecutive_failed_turns_offers_transfer(mock_get_client):
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        _timeout_error(),
        _timeout_error(),
        _timeout_error(),
        _timeout_error(),
    ]
    mock_get_client.return_value = client

    session = CallSession(order=OrderState())
    respond(session, [], "مرحبا")
    reply = respond(session, [], "مرحبا مرة ثانية")

    assert session.transferred is True
    assert session.consecutive_failures == 2
    assert "حول" in reply.text or "موظف" in reply.text


@patch("src.agent._get_client")
def test_respond_order_unchanged_on_repeated_timeout(mock_get_client):
    client = MagicMock()
    client.chat.completions.create.side_effect = [_timeout_error(), _timeout_error()]
    mock_get_client.return_value = client

    session = CallSession(order=OrderState())
    version_before = session.order.version
    respond(session, [], "أبغى أطلب بيتزا")

    assert session.order.version == version_before
    assert session.order.lines == []
