"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

/**
 * 选定的参考音频信息
 */
export interface SelectedVoiceAudio {
  audio_id: string;
  object_key: string;
  url: string;
  filename?: string;
  format: "wav" | "mp3";
}

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
  /** 用户偏好的语音模型（TTS，按项目存储） */
  preferredTtsModelByProject: Record<string, string>;
  /** 用户偏好的语音音色（TTS voice，按项目存储） */
  preferredTtsVoiceByProject: Record<
    string,
    "alloy" | "echo" | "fable" | "onyx" | "nova" | "shimmer"
  >;
  /** 用户偏好的语音返回格式（TTS，按项目存储） */
  preferredTtsFormatByProject: Record<
    string,
    "mp3" | "opus" | "aac" | "wav" | "pcm" | "ogg" | "flac" | "aiff"
  >;
  /** 用户偏好的语速（TTS speed，按项目存储） */
  preferredTtsSpeedByProject: Record<string, number>;
  /** 语音输出模式是否开启（按项目存储） */
  speechModeEnabledByProject: Record<string, boolean>;
  /** 选定的参考语音音频（按项目存储，用于语音克隆） */
  selectedVoiceAudioByProject: Record<string, SelectedVoiceAudio>;
}

/**
 * 用户偏好设置 Store 状态
 */
interface UserPreferencesState {
  preferences: UserPreferences;
  updatePreferences: (updates: Partial<UserPreferences>) => void;
  setPreferredChatModel: (projectId: string | null | undefined, model: string | null) => void;
  setPreferredImageModel: (projectId: string | null | undefined, model: string | null) => void;
  setPreferredTtsModel: (projectId: string | null | undefined, model: string | null) => void;
  setPreferredTtsVoice: (
    projectId: string | null | undefined,
    voice: UserPreferences["preferredTtsVoiceByProject"][string] | null
  ) => void;
  setPreferredTtsFormat: (
    projectId: string | null | undefined,
    format: UserPreferences["preferredTtsFormatByProject"][string] | null
  ) => void;
  setPreferredTtsSpeed: (projectId: string | null | undefined, speed: number | null) => void;
  setSpeechModeEnabled: (projectId: string | null | undefined, enabled: boolean) => void;
  setSelectedVoiceAudio: (projectId: string | null | undefined, audio: SelectedVoiceAudio | null) => void;
  resetPreferences: () => void;
}

/**
 * 默认用户偏好设置
 */
const DEFAULT_PREFERENCES: UserPreferences = {
  sendShortcut: "ctrl-enter",
  preferredChatModelByProject: {},
  preferredImageModelByProject: {},
  preferredTtsModelByProject: {},
  preferredTtsVoiceByProject: {},
  preferredTtsFormatByProject: {},
  preferredTtsSpeedByProject: {},
  speechModeEnabledByProject: {},
  selectedVoiceAudioByProject: {},
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

      setPreferredTtsModel: (projectId, model) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.preferredTtsModelByProject };
          if (!model) {
            delete next[key];
          } else {
            next[key] = model;
          }
          return {
            preferences: { ...state.preferences, preferredTtsModelByProject: next },
          };
        }),

      setPreferredTtsVoice: (projectId, voice) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.preferredTtsVoiceByProject };
          if (!voice) {
            delete next[key];
          } else {
            next[key] = voice;
          }
          return {
            preferences: { ...state.preferences, preferredTtsVoiceByProject: next },
          };
        }),

      setPreferredTtsFormat: (projectId, format) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.preferredTtsFormatByProject };
          if (!format) {
            delete next[key];
          } else {
            next[key] = format;
          }
          return {
            preferences: { ...state.preferences, preferredTtsFormatByProject: next },
          };
        }),

      setPreferredTtsSpeed: (projectId, speed) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.preferredTtsSpeedByProject };
          if (speed === null || speed === undefined) {
            delete next[key];
          } else {
            next[key] = speed;
          }
          return {
            preferences: { ...state.preferences, preferredTtsSpeedByProject: next },
          };
        }),

      setSpeechModeEnabled: (projectId, enabled) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.speechModeEnabledByProject };
          if (!enabled) {
            delete next[key];
          } else {
            next[key] = enabled;
          }
          return {
            preferences: { ...state.preferences, speechModeEnabledByProject: next },
          };
        }),

      setSelectedVoiceAudio: (projectId, audio) =>
        set((state) => {
          const key = (projectId || "").trim();
          if (!key) return state;
          const next = { ...state.preferences.selectedVoiceAudioByProject };
          if (!audio) {
            delete next[key];
          } else {
            next[key] = audio;
          }
          return {
            preferences: { ...state.preferences, selectedVoiceAudioByProject: next },
          };
        }),

      resetPreferences: () =>
        set({ preferences: DEFAULT_PREFERENCES }),
    }),
    {
      name: "user-preferences", // localStorage key
      storage: createJSONStorage(() => localStorage),
      version: 6,
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
          preferredTtsModelByProject: prefs.preferredTtsModelByProject ?? {},
          preferredTtsVoiceByProject: (prefs as any).preferredTtsVoiceByProject ?? {},
          preferredTtsFormatByProject: (prefs as any).preferredTtsFormatByProject ?? {},
          preferredTtsSpeedByProject: (prefs as any).preferredTtsSpeedByProject ?? {},
          speechModeEnabledByProject: (prefs as any).speechModeEnabledByProject ?? {},
          selectedVoiceAudioByProject: (prefs as any).selectedVoiceAudioByProject ?? {},
        };

        // 如果版本号未变化，也直接返回合并后的结构
        if (version >= 6) {
          return { preferences: next };
        }
        return { preferences: next };
      },
    }
  )
);
