from __future__ import annotations

import asyncio
import pytest

from app.services.bridge_tool_runner import BridgeToolResult
from app.services.tool_loop_runner import ToolLoopLimits, ToolLoopRunner, split_text_into_deltas


@pytest.mark.asyncio
async def test_tool_loop_runner_runs_tools_and_returns_final_text():
    calls: list[tuple[str, str, dict]] = []

    async def invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict):
        calls.append((agent_id, tool_name, arguments))
        return BridgeToolResult(
            ok=True,
            exit_code=0,
            canceled=False,
            result_json={"ok": True},
            error=None,
        )

    async def call_model(payload: dict, idempotency_key: str):
        assert payload.get("tool_choice") == "auto"
        return {"choices": [{"message": {"content": "final answer"}}]}

    runner = ToolLoopRunner(invoke_tool=invoke_tool, call_model=call_model)
    result = await runner.run(
        conversation_id="c1",
        run_id="r1",
        base_payload={"messages": [{"role": "user", "content": "hi"}], "tools": [], "tool_choice": "auto"},
        first_response_payload={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{\"q\":\"hi\"}"},
                            }
                        ],
                    }
                }
            ]
        },
        effective_bridge_agent_ids=["agent-1"],
        tool_name_map={},
        idempotency_prefix="chat:r1:tool_loop",
    )

    assert result.did_run is True
    assert result.error_code is None
    assert result.output_text == "final answer"
    assert calls == [("agent-1", "search", {"q": "hi"})]
    assert len(result.tool_invocations) == 1
    assert result.tool_invocations[0]["state"] == "done"


@pytest.mark.asyncio
async def test_tool_loop_runner_forces_non_stream_followup_payload():
    async def invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict):
        return BridgeToolResult(
            ok=True,
            exit_code=0,
            canceled=False,
            result_json={"ok": True},
            error=None,
        )

    async def call_model(payload: dict, idempotency_key: str):
        assert payload.get("stream") is False
        return {"choices": [{"message": {"content": "final answer"}}]}

    runner = ToolLoopRunner(invoke_tool=invoke_tool, call_model=call_model)
    result = await runner.run(
        conversation_id="c1",
        run_id="r1",
        base_payload={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
            "tools": [],
            "tool_choice": "auto",
        },
        first_response_payload={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{\"q\":\"hi\"}"},
                            }
                        ],
                    }
                }
            ]
        },
        effective_bridge_agent_ids=["agent-1"],
        tool_name_map={},
    )

    assert result.did_run is True
    assert result.error_code is None
    assert result.output_text == "final answer"


@pytest.mark.asyncio
async def test_tool_loop_runner_extracts_text_from_content_parts():
    async def invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict):
        return BridgeToolResult(
            ok=True,
            exit_code=0,
            canceled=False,
            result_json={"ok": True},
            error=None,
        )

    async def call_model(payload: dict, idempotency_key: str):
        return {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "hello"},
                            {"type": "text", "text": " world"},
                        ]
                    }
                }
            ]
        }

    runner = ToolLoopRunner(invoke_tool=invoke_tool, call_model=call_model)
    result = await runner.run(
        conversation_id="c1",
        run_id="r1",
        base_payload={"messages": [{"role": "user", "content": "hi"}], "tools": [], "tool_choice": "auto"},
        first_response_payload={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{\"q\":\"hi\"}"},
                            }
                        ],
                    }
                }
            ]
        },
        effective_bridge_agent_ids=["agent-1"],
        tool_name_map={},
    )

    assert result.did_run is True
    assert result.error_code is None
    assert result.output_text == "hello world"


@pytest.mark.asyncio
async def test_tool_loop_runner_timeout_calls_cancel():
    canceled: list[tuple[str, str, str]] = []

    async def invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict):
        return BridgeToolResult(
            ok=False,
            exit_code=0,
            canceled=False,
            result_json=None,
            error={"code": "invoke_timeout", "message": "timeout"},
        )

    async def cancel_tool(req_id: str, agent_id: str, reason: str) -> None:
        canceled.append((req_id, agent_id, reason))

    async def call_model(payload: dict, idempotency_key: str):
        return {"choices": [{"message": {"content": "unused"}}]}

    runner = ToolLoopRunner(invoke_tool=invoke_tool, call_model=call_model, cancel_tool=cancel_tool)
    result = await runner.run(
        conversation_id="c1",
        run_id="r1",
        base_payload={"messages": [{"role": "user", "content": "hi"}], "tools": [], "tool_choice": "auto"},
        first_response_payload={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        },
        effective_bridge_agent_ids=["agent-1"],
        tool_name_map={},
    )

    assert result.did_run is True
    assert len(canceled) == 1
    assert canceled[0][1] == "agent-1"
    assert canceled[0][2] == "invoke_timeout"


@pytest.mark.asyncio
async def test_tool_loop_runner_model_followup_timeout():
    async def invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict):
        return BridgeToolResult(
            ok=True,
            exit_code=0,
            canceled=False,
            result_json={"ok": True},
            error=None,
        )

    async def call_model(payload: dict, idempotency_key: str):
        await asyncio.sleep(1)
        return {"choices": [{"message": {"content": "unused"}}]}

    runner = ToolLoopRunner(
        invoke_tool=invoke_tool,
        call_model=call_model,
        limits=ToolLoopLimits(
            max_rounds=2,
            max_invocations=10,
            max_total_duration_ms=60_000,
            model_call_timeout_ms=10,
        ),
    )
    result = await runner.run(
        conversation_id="c1",
        run_id="r1",
        base_payload={"messages": [{"role": "user", "content": "hi"}], "stream": True, "tools": [], "tool_choice": "auto"},
        first_response_payload={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        },
        effective_bridge_agent_ids=["agent-1"],
        tool_name_map={},
    )

    assert result.did_run is True
    assert result.error_code == "TOOL_LOOP_MODEL_TIMEOUT"


@pytest.mark.asyncio
async def test_tool_loop_runner_stops_on_max_rounds():
    async def invoke_tool(req_id: str, agent_id: str, tool_name: str, arguments: dict):
        return BridgeToolResult(
            ok=True,
            exit_code=0,
            canceled=False,
            result_json={"ok": True},
            error=None,
        )

    async def call_model(payload: dict, idempotency_key: str):
        return {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_next",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        }

    runner = ToolLoopRunner(
        invoke_tool=invoke_tool,
        call_model=call_model,
        limits=ToolLoopLimits(max_rounds=1, max_invocations=10, max_total_duration_ms=60_000),
    )
    result = await runner.run(
        conversation_id="c1",
        run_id="r1",
        base_payload={"messages": [{"role": "user", "content": "hi"}], "tools": [], "tool_choice": "auto"},
        first_response_payload={
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "search", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        },
        effective_bridge_agent_ids=["agent-1"],
        tool_name_map={},
    )

    assert result.error_code == "TOOL_LOOP_MAX_ROUNDS"


def test_split_text_into_deltas_caps_chunk_count_and_roundtrips():
    text = "a" * 10_000
    chunks = split_text_into_deltas(text)
    assert chunks
    assert "".join(chunks) == text
    assert len(chunks) <= 240
