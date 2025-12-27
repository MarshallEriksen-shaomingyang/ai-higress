from __future__ import annotations

import json

from app.services.bridge_tool_runner import extract_openai_tool_calls, tool_call_to_args


def test_extract_openai_tool_calls_fallback_from_tagged_text_xmlish_args():
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "我将立即使用工具查询。\n"
                        "FUNC_TRIGGER_abc_123_END <function_calls>\n"
                        "<function_call>\n"
                        "<tool>tavily_remote__tavily_search</tool>\n"
                        "<args>\n"
                        "<query>Elon Musk latest news December 2025</query>\n"
                        "<max_results>10</max_results>\n"
                        "<search_depth>advanced</search_depth>\n"
                        "<include_raw_content>true</include_raw_content>\n"
                        "<topic>news</topic>\n"
                        "</args>\n"
                        "</function_call>\n"
                        "</function_calls>\n"
                    ),
                }
            }
        ]
    }

    tool_calls = extract_openai_tool_calls(payload)
    assert len(tool_calls) == 1

    name, args, _ = tool_call_to_args(tool_calls[0])
    assert name == "tavily_remote__tavily_search"
    assert args == {
        "query": "Elon Musk latest news December 2025",
        "max_results": 10,
        "search_depth": "advanced",
        "include_raw_content": True,
        "topic": "news",
    }


def test_extract_openai_tool_calls_fallback_from_tagged_text_json_args():
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "<function_calls>"
                        "<function_call>"
                        "<tool>search</tool>"
                        "<args>{\"q\":\"hi\",\"n\":2}</args>"
                        "</function_call>"
                        "</function_calls>"
                    ),
                }
            }
        ]
    }

    tool_calls = extract_openai_tool_calls(payload)
    assert len(tool_calls) == 1
    name, args, _ = tool_call_to_args(tool_calls[0])
    assert name == "search"
    assert args == {"q": "hi", "n": 2}


def test_extract_openai_tool_calls_does_not_parse_without_markers():
    payload = {"choices": [{"message": {"role": "assistant", "content": "no tools here"}}]}
    assert extract_openai_tool_calls(payload) == []


def test_tool_call_to_args_handles_generated_arguments_json():
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "<function_calls>"
                        "<function_call>"
                        "<tool>search</tool>"
                        "<args><q>hi</q><n>2</n></args>"
                        "</function_call>"
                        "</function_calls>"
                    ),
                }
            }
        ]
    }
    tc = extract_openai_tool_calls(payload)[0]
    # Ensure arguments are JSON string (OpenAI-compatible) and parsable downstream.
    raw_args = tc["function"]["arguments"]
    assert isinstance(raw_args, str)
    assert json.loads(raw_args) == {"q": "hi", "n": 2}

