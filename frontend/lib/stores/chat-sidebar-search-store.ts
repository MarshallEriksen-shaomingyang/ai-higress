"use client";

import { create } from "zustand";

interface ChatSidebarSearchState {
  assistantQuery: string;
  conversationQuery: string;

  setAssistantQuery: (query: string) => void;
  setConversationQuery: (query: string) => void;
  clearAssistantQuery: () => void;
  clearConversationQuery: () => void;
  reset: () => void;
}

const initialState = {
  assistantQuery: "",
  conversationQuery: "",
};

export const useChatSidebarSearchStore = create<ChatSidebarSearchState>((set) => ({
  ...initialState,

  setAssistantQuery: (query) => set({ assistantQuery: query }),
  setConversationQuery: (query) => set({ conversationQuery: query }),
  clearAssistantQuery: () => set({ assistantQuery: "" }),
  clearConversationQuery: () => set({ conversationQuery: "" }),
  reset: () => set(initialState),
}));

