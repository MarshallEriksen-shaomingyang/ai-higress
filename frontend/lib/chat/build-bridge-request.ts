"use client";

import type { SendMessageRequest } from "@/lib/api-types";

type ToolSelectionsByAgent = Record<string, string[]>;

const normalizeIdList = (ids: string[] | undefined | null) =>
  (ids || []).map((x) => String(x || "").trim()).filter(Boolean);

const normalizeToolNames = (names: string[] | undefined | null) =>
  (names || []).map((x) => String(x || "").trim()).filter(Boolean);

/**
 * 统一构造 bridge 字段，避免多个发送/对比/重试入口各写一套逻辑导致遗漏。
 *
 * 规则：
 * - 若配置了工具子集（default + conversation 覆盖），则生成 `bridge_agent_ids` + `bridge_tool_selections`。
 * - 否则若只选择了 agent（conversationBridgeAgentIds），则仅携带 `bridge_agent_ids`（表示注入该 agent 的全部工具）。
 */
export function buildBridgeRequestFields(opts: {
  conversationBridgeAgentIds?: string[] | null;
  conversationBridgeToolSelections?: ToolSelectionsByAgent | null;
  defaultBridgeToolSelections?: ToolSelectionsByAgent | null;
}): Pick<SendMessageRequest, "bridge_agent_ids" | "bridge_tool_selections"> {
  const conversationAgentIds = normalizeIdList(opts.conversationBridgeAgentIds ?? undefined);

  const merged: ToolSelectionsByAgent = { ...(opts.defaultBridgeToolSelections || {}) };
  for (const [aid, tools] of Object.entries(opts.conversationBridgeToolSelections || {})) {
    const normAid = String(aid || "").trim();
    if (!normAid) continue;
    const normTools = normalizeToolNames(tools);
    if (normTools.length) {
      merged[normAid] = normTools;
    }
  }

  const effectiveAgentIds = Object.entries(merged)
    .filter(([aid, tools]) => String(aid || "").trim() && Array.isArray(tools) && tools.length)
    .map(([aid]) => String(aid).trim());

  if (effectiveAgentIds.length) {
    return {
      bridge_agent_ids: effectiveAgentIds,
      bridge_tool_selections: effectiveAgentIds.map((agentId) => ({
        agent_id: agentId,
        tool_names: normalizeToolNames(merged[agentId]),
      })),
    };
  }

  if (conversationAgentIds.length) {
    return { bridge_agent_ids: conversationAgentIds };
  }

  return {};
}

