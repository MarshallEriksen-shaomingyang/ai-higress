from __future__ import annotations

from app.services.chat_app_service import _ToolTagStreamFilter


def test_tool_tag_stream_filter_pass_through_when_no_markers():
    f = _ToolTagStreamFilter(holdback_chars=0)
    assert f.feed("hello") == "hello"
    assert f.feed(" world") == " world"
    assert f.flush() == ""
    assert f.detected is False


def test_tool_tag_stream_filter_detects_and_suppresses_markers():
    f = _ToolTagStreamFilter(holdback_chars=0)
    assert f.feed("prefix ") == "prefix "
    # Marker出现后开始抑制（避免把标签工件透传到前端）。
    assert f.feed("FUNC_TRIGGER_x_END <function_calls><function_call>") == ""
    assert f.detected is True
    assert f.feed("rest") == ""
    assert f.flush() == ""


def test_tool_tag_stream_filter_holdback_buffers_tail():
    f = _ToolTagStreamFilter(holdback_chars=4)
    assert f.feed("abcd") == ""
    assert f.feed("efgh") == "abcd"
    assert f.flush() == "efgh"

