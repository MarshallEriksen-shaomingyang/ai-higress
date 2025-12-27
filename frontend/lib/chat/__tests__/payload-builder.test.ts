import { describe, it, expect } from "vitest";
import {
  buildBridgeFields,
  sanitizeBridgeFields,
  buildChatPayload,
  buildRegeneratePayload,
} from "../payload-builder";

describe("payload-builder", () => {
  it("merges default and conversation bridge tool selections", () => {
    const res = buildBridgeFields({
      conversationBridgeAgentIds: ["agent-1"],
      conversationBridgeToolSelections: { "agent-1": ["search"] },
      defaultBridgeToolSelections: { "agent-2": ["crawl"] },
    });

    expect(res.bridge_agent_ids).toEqual(["agent-1", "agent-2"]);
    expect(res.bridge_tool_selections).toEqual([
      { agent_id: "agent-1", tool_names: ["search"] },
      { agent_id: "agent-2", tool_names: ["crawl"] },
    ]);
  });

  it("sanitizes bridge fields when no available agents", () => {
    const cleaned = sanitizeBridgeFields(
      {
        bridge_agent_ids: ["agent-1"],
        bridge_tool_selections: [{ agent_id: "agent-1", tool_names: ["search"] }],
      },
      null
    );

    expect(cleaned.bridge_agent_ids).toBeUndefined();
    expect(cleaned.bridge_tool_selections).toBeUndefined();
  });

  it("sanitizes bridge fields by available agent whitelist", () => {
    const cleaned = sanitizeBridgeFields(
      {
        bridge_agent_ids: ["agent-1", "agent-2"],
        bridge_tool_selections: [
          { agent_id: "agent-1", tool_names: ["search"] },
          { agent_id: "agent-2", tool_names: ["crawl"] },
        ],
      },
      new Set(["agent-1"])
    );

    expect(cleaned.bridge_agent_ids).toEqual(["agent-1"]);
    expect(cleaned.bridge_tool_selections).toEqual([
      { agent_id: "agent-1", tool_names: ["search"] },
    ]);
  });

  it("builds chat payload with sanitized bridge fields", () => {
    const payload = buildChatPayload({
      content: "hello",
      modelPreset: { temperature: 0.7 },
      overrideLogicalModel: "test-model",
      bridgeState: {
        conversationBridgeAgentIds: ["agent-1"],
        conversationBridgeToolSelections: { "agent-1": ["search"] },
      },
      availableBridgeAgentIds: new Set(["agent-1"]),
    });

    expect(payload.content).toBe("hello");
    expect(payload.model_preset).toEqual({ temperature: 0.7 });
    expect(payload.override_logical_model).toBe("test-model");
    expect(payload.bridge_agent_ids).toEqual(["agent-1"]);
    expect(payload.bridge_tool_selections).toEqual([
      { agent_id: "agent-1", tool_names: ["search"] },
    ]);
  });

  it("builds regenerate payload with sanitized bridge fields", () => {
    const payload = buildRegeneratePayload({
      modelPreset: { temperature: 0.5 },
      overrideLogicalModel: "model",
      bridgeState: {
        conversationBridgeAgentIds: ["agent-1", "agent-2"],
        conversationBridgeToolSelections: { "agent-2": ["crawl"] },
      },
      availableBridgeAgentIds: new Set(["agent-2"]),
    });

    expect(payload.model_preset).toEqual({ temperature: 0.5 });
    expect(payload.override_logical_model).toBe("model");
    expect(payload.bridge_agent_ids).toEqual(["agent-2"]);
    expect(payload.bridge_tool_selections).toEqual([
      { agent_id: "agent-2", tool_names: ["crawl"] },
    ]);
  });
});
