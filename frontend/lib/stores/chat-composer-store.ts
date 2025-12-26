"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ComposerMode } from "@/lib/chat/composer-modes";

export interface ImageComposerState {
  model: string;
  size: string;
  n: number;
}

export interface ConversationComposerState {
  activeMode: ComposerMode;
  image: ImageComposerState;
}

interface ChatComposerState {
  byConversationId: Record<string, ConversationComposerState>;

  ensureConversation: (conversationId: string) => void;
  setActiveMode: (conversationId: string, mode: ComposerMode) => void;
  setImageState: (
    conversationId: string,
    updates: Partial<ImageComposerState>
  ) => void;
  resetConversation: (conversationId: string) => void;
}

const defaultConversationState = (): ConversationComposerState => ({
  activeMode: "chat",
  image: {
    model: "",
    size: "1024x1024",
    n: 1,
  },
});

const fallbackConversationState: ConversationComposerState = (() => {
  const state = defaultConversationState();
  if (process.env.NODE_ENV !== "production") {
    Object.freeze(state.image);
    Object.freeze(state);
  }
  return state;
})();

export const useChatComposerStore = create<ChatComposerState>()(
  persist(
    (set) => ({
      byConversationId: {},

      ensureConversation: (conversationId) =>
        set((state) => {
          const key = String(conversationId || "").trim();
          if (!key) return state;
          if (state.byConversationId[key]) return state;
          return {
            ...state,
            byConversationId: {
              ...state.byConversationId,
              [key]: defaultConversationState(),
            },
          };
        }),

      setActiveMode: (conversationId, mode) =>
        set((state) => {
          const key = String(conversationId || "").trim();
          if (!key) return state;
          const prev = state.byConversationId[key] ?? defaultConversationState();
          if (prev.activeMode === mode) return state;
          return {
            ...state,
            byConversationId: {
              ...state.byConversationId,
              [key]: { ...prev, activeMode: mode },
            },
          };
        }),

      setImageState: (conversationId, updates) =>
        set((state) => {
          const key = String(conversationId || "").trim();
          if (!key) return state;
          const prev = state.byConversationId[key] ?? defaultConversationState();
          const nextImage = { ...prev.image, ...updates };
          if (
            nextImage.model === prev.image.model &&
            nextImage.size === prev.image.size &&
            nextImage.n === prev.image.n
          ) {
            return state;
          }
          return {
            ...state,
            byConversationId: {
              ...state.byConversationId,
              [key]: {
                ...prev,
                image: nextImage,
              },
            },
          };
        }),

      resetConversation: (conversationId) =>
        set((state) => {
          const key = String(conversationId || "").trim();
          if (!key) return state;
          const next = { ...state.byConversationId };
          delete next[key];
          return { ...state, byConversationId: next };
        }),
    }),
    {
      name: "chat-composer-store",
      version: 1,
      migrate: (persistedState: unknown) => {
        if (!persistedState || typeof persistedState !== "object") {
          return { byConversationId: {} };
        }
        const state = persistedState as Record<string, unknown>;
        const raw = state.byConversationId;
        if (!raw || typeof raw !== "object") {
          return { byConversationId: {} };
        }

        const byConversationId: Record<string, ConversationComposerState> = {};
        for (const [conversationId, value] of Object.entries(
          raw as Record<string, unknown>
        )) {
          if (!value || typeof value !== "object") continue;
          const record = value as Record<string, unknown>;
          const mode = record.activeMode;
          const image = record.image;
          const normalized: ConversationComposerState = defaultConversationState();
          if (mode === "chat" || mode === "image") {
            normalized.activeMode = mode;
          }
          if (image && typeof image === "object") {
            const img = image as Record<string, unknown>;
            if (typeof img.model === "string") normalized.image.model = img.model;
            if (typeof img.size === "string") normalized.image.size = img.size;
            if (typeof img.n === "number" && Number.isFinite(img.n)) {
              normalized.image.n = img.n;
            }
          }
          byConversationId[conversationId] = normalized;
        }
        return { byConversationId };
      },
    }
  )
);

export function getConversationComposerState(
  state: Pick<ChatComposerState, "byConversationId">,
  conversationId: string
) {
  const key = String(conversationId || "").trim();
  return key
    ? state.byConversationId[key] ?? fallbackConversationState
    : fallbackConversationState;
}
