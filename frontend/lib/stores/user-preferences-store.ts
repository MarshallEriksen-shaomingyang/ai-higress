"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * 用户偏好设置类型
 */
export interface UserPreferences {
  /** 发送消息的快捷键模式 */
  sendShortcut: "enter" | "ctrl-enter";
  /** 用户最近选择的聊天模型（按项目存储） */
  preferredChatModelByProject: Record<string, string>;
  /** 用户最近选择的文生图模型（按项目存储） */
  preferredImageModelByProject: Record<string, string>;
}

/**
 * 用户偏好设置 Store 状态
 */
interface UserPreferencesState {
  preferences: UserPreferences;
  updatePreferences: (updates: Partial<UserPreferences>) => void;
  setPreferredChatModel: (projectId: string | null | undefined, model: string | null) => void;
  setPreferredImageModel: (projectId: string | null | undefined, model: string | null) => void;
  resetPreferences: () => void;
}

/**
 * 默认用户偏好设置
 */
const DEFAULT_PREFERENCES: UserPreferences = {
  sendShortcut: "ctrl-enter",
  preferredChatModelByProject: {},
  preferredImageModelByProject: {},
};

/**
 * 用户偏好设置 Zustand Store
 * 使用 persist 中间件自动持久化到 localStorage
 */
export const useUserPreferencesStore = create<UserPreferencesState>()(
  persist(
    (set) => ({
      preferences: DEFAULT_PREFERENCES,
      
      updatePreferences: (updates) =>
        set((state) => ({
          preferences: { ...state.preferences, ...updates },
        })),

      setPreferredChatModel: (projectId, model) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.preferredChatModelByProject };
          if (!model) {
            delete next[key];
          } else {
            next[key] = model;
          }
          return {
            preferences: { ...state.preferences, preferredChatModelByProject: next },
          };
        }),

      setPreferredImageModel: (projectId, model) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.preferredImageModelByProject };
          if (!model) {
            delete next[key];
          } else {
            next[key] = model;
          }
          return {
            preferences: { ...state.preferences, preferredImageModelByProject: next },
          };
        }),
      
      resetPreferences: () =>
        set({ preferences: DEFAULT_PREFERENCES }),
    }),
    {
      name: "user-preferences", // localStorage key
      storage: createJSONStorage(() => localStorage),
      version: 2,
      migrate: (persistedState: unknown, version: number) => {
        if (!persistedState || typeof persistedState !== "object") {
          return { preferences: DEFAULT_PREFERENCES };
        }

        const state = persistedState as Record<string, any>;
        const prefs = (state.preferences || {}) as Partial<UserPreferences>;

        // 兼容旧版本（仅有 sendShortcut）
        const next: UserPreferences = {
          sendShortcut: prefs.sendShortcut === "enter" || prefs.sendShortcut === "ctrl-enter"
            ? prefs.sendShortcut
            : DEFAULT_PREFERENCES.sendShortcut,
          preferredChatModelByProject: prefs.preferredChatModelByProject ?? {},
          preferredImageModelByProject: prefs.preferredImageModelByProject ?? {},
        };

        // 如果版本号未变化，也直接返回合并后的结构
        if (version >= 2) {
          return { preferences: next };
        }
        return { preferences: next };
      },
    }
  )
);
