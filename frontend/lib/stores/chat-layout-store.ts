"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Layout } from "react-resizable-panels";

interface ChatLayoutState {
  layout: Layout | null;
  chatVerticalLayout: Layout | null;
  activeTab: "assistants" | "conversations";
  isImmersive: boolean;
  setLayout: (layout: Layout) => void;
  setChatVerticalLayout: (layout: Layout) => void;
  setActiveTab: (tab: "assistants" | "conversations") => void;
  setIsImmersive: (isImmersive: boolean) => void;
  resetLayout: () => void;
}

export const useChatLayoutStore = create<ChatLayoutState>()(
  persist(
    (set) => ({
      layout: null,
      chatVerticalLayout: null,
      activeTab: "assistants",
      isImmersive: false,
      setLayout: (layout) => set({ layout }),
      setChatVerticalLayout: (layout) => set({ chatVerticalLayout: layout }),
      setActiveTab: (tab) => set({ activeTab: tab }),
      setIsImmersive: (isImmersive) => set({ isImmersive }),
      resetLayout: () => set({ layout: null, chatVerticalLayout: null, activeTab: "assistants", isImmersive: false }),
    }),
    {
      name: "chat-layout",
      version: 3,
    }
  )
);

