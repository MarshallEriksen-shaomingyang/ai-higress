"use client";

import type { SendMessageRequest, RegenerateMessageRequest } from "@/lib/api-types";

type ToolSelectionsByAgent = Record<string, string[]>;

export type BridgeState = {
  conversationBridgeAgentIds?: string[] | null;
  conversationBridgeToolSelections?: ToolSelectionsByAgent | null;
  defaultBridgeToolSelections?: ToolSelectionsByAgent | null;
};

const normalizeIdList = (ids: string[] | undefined | null) =>
  (ids || []).map((x) => String(x || "").trim()).filter(Boolean);

const normalizeToolNames = (names: string[] | undefined | null) =>
  (names || []).map((x) => String(x || "").trim()).filter(Boolean);

/**
 * 根据默认与会话选择构造 bridge 字段（不做白名单过滤）。
 */
export function buildBridgeFields(state: BridgeState): Pick<
  SendMessageRequest,
  "bridge_agent_ids" | "bridge_tool_selections"
> {
  const conversationAgentIds = normalizeIdList(state.conversationBridgeAgentIds ?? undefined);

  const merged: ToolSelectionsByAgent = { ...(state.defaultBridgeToolSelections || {}) };
  for (const [aid, tools] of Object.entries(state.conversationBridgeToolSelections || {})) {
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

/**
 * 基于已加载的 Bridge Agent 列表过滤/清空 bridge 字段。
 */
export function sanitizeBridgeFields<
  T extends Partial<
    Pick<SendMessageRequest, "bridge_agent_id" | "bridge_agent_ids" | "bridge_tool_selections">
  >
>(raw: T, availableBridgeAgentIds: Set<string> | null | undefined): T {
  if (!availableBridgeAgentIds || !availableBridgeAgentIds.size) {
    const {
      bridge_agent_id: _omitSingle,
      bridge_agent_ids: _omitList,
      bridge_tool_selections: _omitTools,
      ...rest
    } = raw as T & Record<string, unknown>;
    return rest as T;
  }

  const filterId = (value: unknown): string | null => {
    const v = typeof value === "string" ? value.trim() : "";
    return v && availableBridgeAgentIds.has(v) ? v : null;
  };

  const filteredAgentIds = Array.isArray(raw.bridge_agent_ids)
    ? raw.bridge_agent_ids
        .map((id) => filterId(id))
        .filter((id): id is string => !!id)
    : [];

  const singleAgentId = filterId(raw.bridge_agent_id);

  const filteredToolSelections = Array.isArray(raw.bridge_tool_selections)
    ? raw.bridge_tool_selections
        .map((sel) => {
          const agentId = filterId((sel as any)?.agent_id);
          if (!agentId) return null;
          const names = Array.isArray((sel as any)?.tool_names)
            ? (sel as any).tool_names
                .map((n: unknown) => (typeof n === "string" ? n.trim() : ""))
                .filter(Boolean)
            : [];
          if (!names.length) return null;
          return { agent_id: agentId, tool_names: names };
        })
        .filter((x): x is { agent_id: string; tool_names: string[] } => !!x)
    : [];

  const next: T = {
    ...raw,
    bridge_agent_id: singleAgentId ?? undefined,
    bridge_agent_ids: filteredAgentIds.length ? filteredAgentIds : undefined,
    bridge_tool_selections: filteredToolSelections.length ? filteredToolSelections : undefined,
  };

  if (!next.bridge_agent_id && !next.bridge_agent_ids && !next.bridge_tool_selections) {
    delete (next as any).bridge_agent_id;
    delete (next as any).bridge_agent_ids;
    delete (next as any).bridge_tool_selections;
  }

  return next;
}

export function buildChatPayload(opts: {
  content: string;
  inputAudio?: SendMessageRequest["input_audio"] | null;
  modelPreset?: Record<string, any> | null;
  overrideLogicalModel?: string | null;
  bridgeState?: BridgeState | null;
  availableBridgeAgentIds?: Set<string> | null;
}): SendMessageRequest {
  const bridgeFields = buildBridgeFields(opts.bridgeState || {});
  const sanitizedBridge = sanitizeBridgeFields(bridgeFields, opts.availableBridgeAgentIds);

  const payload: SendMessageRequest = {
    content: opts.content,
    input_audio: opts.inputAudio ?? undefined,
    model_preset: opts.modelPreset ?? undefined,
    override_logical_model: opts.overrideLogicalModel ?? undefined,
    ...sanitizedBridge,
  };
  return payload;
}

export function buildRegeneratePayload(opts: {
  modelPreset?: Record<string, any> | null;
  overrideLogicalModel?: string | null;
  bridgeState?: BridgeState | null;
  availableBridgeAgentIds?: Set<string> | null;
}): RegenerateMessageRequest {
  const bridgeFields = buildBridgeFields(opts.bridgeState || {});
  const sanitizedBridge = sanitizeBridgeFields(bridgeFields, opts.availableBridgeAgentIds);

  return {
    model_preset: opts.modelPreset ?? undefined,
    override_logical_model: opts.overrideLogicalModel ?? undefined,
    ...sanitizedBridge,
  };
}

export function buildComparisonPayload(opts: {
  content: string;
  modelPreset?: Record<string, any> | null;
  overrideLogicalModel: string;
  bridgeState?: BridgeState | null;
  availableBridgeAgentIds?: Set<string> | null;
}): SendMessageRequest {
  return buildChatPayload({
    content: opts.content,
    modelPreset: opts.modelPreset,
    overrideLogicalModel: opts.overrideLogicalModel,
    bridgeState: opts.bridgeState,
    availableBridgeAgentIds: opts.availableBridgeAgentIds,
  });
}
