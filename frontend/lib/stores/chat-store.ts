"use client";

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

/**
 * 聊天模块状态管理
 */
interface ChatState {
  // 当前选中的项目（API Key）
  selectedProjectId: string | null;

  // 当前选中的助手和会话
  selectedAssistantId: string | null;
  selectedConversationId: string | null;

  // 评测面板状态
  activeEvalId: string | null;

  // 评测创建是否使用流式（SSE）
  evalStreamingEnabled: boolean;

  // 会话级模型覆盖：conversationId -> logical model（null 表示跟随助手默认）
  conversationModelOverrides: Record<string, string>;

  // 会话级 Bridge Agent 选择（可多选）：conversationId -> agent_ids
  conversationBridgeAgentIds: Record<string, string[]>;

  // 会话级 Bridge 面板聚焦的 req_id：conversationId -> req_id
  conversationBridgeActiveReqIds: Record<string, string>;

  // 会话级 Bridge 工具选择：conversationId -> agent_id -> tool_names[]
  conversationBridgeToolSelections: Record<string, Record<string, string[]>>;

  // 全局默认 Bridge 工具选择：agent_id -> tool_names[]（跨会话复用）
  defaultBridgeToolSelections: Record<string, string[]>;

  // 会话级最近一次发送使用的 model_preset：conversationId -> preset
  conversationModelPresets: Record<string, Record<string, number>>;

  // 会话等待回复中的状态：conversationId -> pending
  conversationPending: Record<string, boolean>;

  // 操作方法
  setSelectedProjectId: (projectId: string | null) => void;
  setSelectedAssistant: (assistantId: string | null) => void;
  setSelectedConversation: (conversationId: string | null) => void;
  setActiveEval: (evalId: string | null) => void;
  setEvalStreamingEnabled: (enabled: boolean) => void;
  setConversationModelOverride: (conversationId: string, logicalModel: string | null) => void;
  clearConversationModelOverrides: () => void;
  setConversationBridgeAgentIds: (conversationId: string, agentIds: string[] | null) => void;
  setConversationBridgeActiveReqId: (conversationId: string, reqId: string | null) => void;
  setConversationBridgeToolSelections: (
    conversationId: string,
    agentId: string,
    toolNames: string[] | null
  ) => void;
  setDefaultBridgeToolSelections: (agentId: string, toolNames: string[] | null) => void;
  setConversationModelPreset: (conversationId: string, preset: Record<string, number> | null) => void;
  setConversationPending: (conversationId: string, pending: boolean) => void;
  
  // 重置状态
  reset: () => void;
}

const initialState = {
  selectedProjectId: null,
  selectedAssistantId: null,
  selectedConversationId: null,
  activeEvalId: null,
  evalStreamingEnabled: false,
  conversationModelOverrides: {} as Record<string, string>,
  conversationBridgeAgentIds: {} as Record<string, string[]>,
  conversationBridgeActiveReqIds: {} as Record<string, string>,
  conversationBridgeToolSelections: {} as Record<string, Record<string, string[]>>,
  defaultBridgeToolSelections: {} as Record<string, string[]>,
  conversationModelPresets: {} as Record<string, Record<string, number>>,
  conversationPending: {} as Record<string, boolean>,
};

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      ...initialState,

      setSelectedProjectId: (projectId) =>
        set({
          selectedProjectId: projectId,
          // 切换项目时清空助手和会话选择
          selectedAssistantId: null,
          selectedConversationId: null,
          conversationModelOverrides: {},
          conversationBridgeAgentIds: {},
          conversationBridgeActiveReqIds: {},
          conversationBridgeToolSelections: {},
          conversationModelPresets: {},
        }),

      setSelectedAssistant: (assistantId) =>
        set({ selectedAssistantId: assistantId }),

      setSelectedConversation: (conversationId) =>
        set({ selectedConversationId: conversationId }),

      setActiveEval: (evalId) =>
        set({ activeEvalId: evalId }),

      setEvalStreamingEnabled: (enabled) =>
        set({ evalStreamingEnabled: enabled }),

      setConversationModelOverride: (conversationId, logicalModel) =>
        set((state) => {
          const next = { ...state.conversationModelOverrides };
          if (!logicalModel) {
            delete next[conversationId];
          } else {
            next[conversationId] = logicalModel;
          }
          return { conversationModelOverrides: next };
        }),

      clearConversationModelOverrides: () => set({ conversationModelOverrides: {} }),

      setConversationBridgeAgentIds: (conversationId, agentIds) =>
        set((state) => {
          const next = { ...state.conversationBridgeAgentIds };
          const normalized = (agentIds || []).map((x) => x.trim()).filter(Boolean);
          if (!normalized.length) {
            delete next[conversationId];
          } else {
            next[conversationId] = normalized;
          }
          return { conversationBridgeAgentIds: next };
        }),

      setConversationBridgeActiveReqId: (conversationId, reqId) =>
        set((state) => {
          const next = { ...state.conversationBridgeActiveReqIds };
          if (!reqId) {
            delete next[conversationId];
          } else {
            next[conversationId] = reqId;
          }
          return { conversationBridgeActiveReqIds: next };
        }),

      setConversationBridgeToolSelections: (conversationId, agentId, toolNames) =>
        set((state) => {
          const next = { ...(state.conversationBridgeToolSelections || {}) };
          const normalizedAgent = String(agentId || "").trim();
          if (!normalizedAgent) {
            return { conversationBridgeToolSelections: next };
          }
          const existing = { ...(next[conversationId] || {}) };
          const normalizedTools = (toolNames || []).map((x) => x.trim()).filter(Boolean);
          if (!normalizedTools.length) {
            delete existing[normalizedAgent];
          } else {
            existing[normalizedAgent] = normalizedTools;
          }
          if (Object.keys(existing).length === 0) {
            delete next[conversationId];
          } else {
            next[conversationId] = existing;
          }
          return { conversationBridgeToolSelections: next };
        }),

      setDefaultBridgeToolSelections: (agentId, toolNames) =>
        set((state) => {
          const next = { ...(state.defaultBridgeToolSelections || {}) };
          const normalizedAgent = String(agentId || "").trim();
          if (!normalizedAgent) return { defaultBridgeToolSelections: next };
          const normalizedTools = (toolNames || []).map((x) => x.trim()).filter(Boolean);
          if (!normalizedTools.length) {
            delete next[normalizedAgent];
          } else {
            next[normalizedAgent] = normalizedTools;
          }
          return { defaultBridgeToolSelections: next };
        }),

      setConversationModelPreset: (conversationId, preset) =>
        set((state) => {
          const next = { ...(state.conversationModelPresets || {}) };
          const normalizedId = String(conversationId || "").trim();
          if (!normalizedId) return { conversationModelPresets: next };
          if (!preset || typeof preset !== "object") {
            delete next[normalizedId];
            return { conversationModelPresets: next };
          }
          const normalized: Record<string, number> = {};
          for (const [k, v] of Object.entries(preset)) {
            const key = String(k || "").trim();
            if (!key) continue;
            if (typeof v !== "number" || Number.isNaN(v)) continue;
            normalized[key] = v;
          }
          if (!Object.keys(normalized).length) {
            delete next[normalizedId];
          } else {
            next[normalizedId] = normalized;
          }
          return { conversationModelPresets: next };
        }),

      setConversationPending: (conversationId, pending) =>
        set((state) => {
          const next = { ...state.conversationPending };
          if (!pending) {
            delete next[conversationId];
          } else {
            next[conversationId] = true;
          }
          return { conversationPending: next };
        }),

      reset: () => set(initialState),
    }),
    {
      name: 'chat-store',
      version: 12,
      migrate: (persistedState: unknown) => {
        // v1 -> v2: add conversationModelOverrides
        // v2 -> v3: add conversationBridgeAgentIds
        // v3 -> v4: add conversationBridgeActiveReqIds
        // v4 -> v5: conversationBridgeAgentIds from string -> string[]
        // v5 -> v6: add evalStreamingEnabled
        // v6 -> v7: add conversationPending
        // v7 -> v8: add conversationBridgeToolSelections
        // v8 -> v9: add defaultBridgeToolSelections
        // v9 -> v10: add conversationModelPresets
        // v11 -> v12: remove chatStreamingEnabled (always streaming in UI)
        if (persistedState && typeof persistedState === 'object') {
          const state = persistedState as Record<string, unknown>;
          const rawAgentIds = state.conversationBridgeAgentIds ?? {};
          const nextAgentIds: Record<string, string[]> = {};
          if (rawAgentIds && typeof rawAgentIds === 'object') {
            for (const [k, v] of Object.entries(rawAgentIds)) {
              if (Array.isArray(v)) {
                nextAgentIds[k] = v.map((x) => String(x)).filter(Boolean);
              } else if (typeof v === 'string' && v.trim()) {
                nextAgentIds[k] = [v.trim()];
              }
            }
          }

          const rawToolSelections = state.conversationBridgeToolSelections ?? {};
          const nextToolSelections: Record<string, Record<string, string[]>> = {};
          if (rawToolSelections && typeof rawToolSelections === 'object') {
            for (const [convId, agents] of Object.entries(rawToolSelections)) {
              if (agents && typeof agents === 'object') {
                const normalizedAgents: Record<string, string[]> = {};
                for (const [aid, tools] of Object.entries(agents as Record<string, unknown>)) {
                  if (Array.isArray(tools)) {
                    const normalizedTools = tools.map((t) => String(t).trim()).filter(Boolean);
                    if (normalizedTools.length) {
                      normalizedAgents[aid] = normalizedTools;
                    }
                  }
                }
                if (Object.keys(normalizedAgents).length) {
                  nextToolSelections[convId] = normalizedAgents;
                }
              }
            }
          }

          const rawDefaultTools = state.defaultBridgeToolSelections ?? {};
          const nextDefaultTools: Record<string, string[]> = {};
          if (rawDefaultTools && typeof rawDefaultTools === 'object') {
            for (const [aid, tools] of Object.entries(rawDefaultTools)) {
              if (Array.isArray(tools)) {
                const normalized = tools.map((t) => String(t).trim()).filter(Boolean);
                if (normalized.length) {
                  nextDefaultTools[aid] = normalized;
                }
              }
            }
          }

          return {
            ...state,
            evalStreamingEnabled: (state.evalStreamingEnabled as boolean | undefined) ?? false,
            conversationModelOverrides: (state.conversationModelOverrides as Record<string, string> | undefined) ?? {},
            conversationBridgeAgentIds: nextAgentIds,
            conversationBridgeActiveReqIds: (state.conversationBridgeActiveReqIds as Record<string, string> | undefined) ?? {},
            conversationPending: (state.conversationPending as Record<string, boolean> | undefined) ?? {},
            conversationBridgeToolSelections: nextToolSelections,
            defaultBridgeToolSelections: nextDefaultTools,
            conversationModelPresets: (state.conversationModelPresets as Record<string, Record<string, number>> | undefined) ?? {},
          };
        }
        return persistedState;
      },
    }
  )
);
