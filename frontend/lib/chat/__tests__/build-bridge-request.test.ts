import { buildBridgeRequestFields } from "@/lib/chat/build-bridge-request";

describe("buildBridgeRequestFields", () => {
  it("returns empty when no selections", () => {
    expect(buildBridgeRequestFields({})).toEqual({});
  });

  it("prefers tool selections over plain agent ids", () => {
    const res = buildBridgeRequestFields({
      conversationBridgeAgentIds: ["agent-1"],
      defaultBridgeToolSelections: { "agent-1": ["search"] },
    });
    expect(res.bridge_agent_ids).toEqual(["agent-1"]);
    expect(res.bridge_tool_selections).toEqual([{ agent_id: "agent-1", tool_names: ["search"] }]);
  });

  it("merges default and conversation tool selections (conversation overrides when non-empty)", () => {
    const res = buildBridgeRequestFields({
      defaultBridgeToolSelections: { "agent-1": ["a", "b"] },
      conversationBridgeToolSelections: { "agent-1": ["c"] },
    });
    expect(res.bridge_tool_selections).toEqual([{ agent_id: "agent-1", tool_names: ["c"] }]);
  });

  it("falls back to agent ids only when no tool selections exist", () => {
    const res = buildBridgeRequestFields({
      conversationBridgeAgentIds: ["agent-1", "agent-2"],
    });
    expect(res).toEqual({ bridge_agent_ids: ["agent-1", "agent-2"] });
  });
});

