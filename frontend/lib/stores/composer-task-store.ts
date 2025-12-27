"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ComposerTask } from "@/lib/chat/composer-tasks";

interface ComposerTaskState {
  tasks: ComposerTask[];

  addTask: (task: ComposerTask) => void;
  updateTask: (id: string, updates: Partial<ComposerTask>) => void;
  getTasksByConversation: (conversationId: string) => ComposerTask[];
  removeTask: (id: string) => void;
}

export const useComposerTaskStore = create<ComposerTaskState>()(
  persist(
    (set, get) => ({
      tasks: [],

      addTask: (task) =>
        set((state) => ({
          tasks: [...state.tasks, task],
        })),

      updateTask: (id, updates) =>
        set((state) => ({
          tasks: state.tasks.map((t) => (t.id === id ? ({ ...t, ...updates } as ComposerTask) : t)),
        })),

      getTasksByConversation: (conversationId) => {
        const key = String(conversationId || "").trim();
        if (!key) return [];
        return get().tasks.filter((t) => t.conversationId === key);
      },

      removeTask: (id) =>
        set((state) => ({
          tasks: state.tasks.filter((t) => t.id !== id),
        })),
    }),
    {
      name: "composer-task-store",
      version: 2,
      migrate: () => ({ tasks: [] }),
    }
  )
);
