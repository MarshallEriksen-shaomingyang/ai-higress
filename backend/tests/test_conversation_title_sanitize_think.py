from app.services.chat_app_service import _sanitize_conversation_title


def test_sanitize_conversation_title_strips_think_blocks() -> None:
    assert _sanitize_conversation_title("<think>abc</think> hello") == "hello"
    assert _sanitize_conversation_title("<think>abc</think>\n\nhello") == "hello"
    assert _sanitize_conversation_title('  <think>abc</think>  “hello”  ') == "hello"


def test_sanitize_conversation_title_drops_unclosed_think_tail() -> None:
    assert _sanitize_conversation_title("<think>abc") == ""

