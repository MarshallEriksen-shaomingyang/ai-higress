import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ImageGenerationRequest, ImageGenerationResponse } from '@/lib/api-types';

export interface ImageGenTask {
  id: string; // client-side ID
  conversationId: string;
  status: 'pending' | 'success' | 'failed';
  prompt: string;
  params: ImageGenerationRequest;
  result?: ImageGenerationResponse;
  error?: string;
  createdAt: number;
}

interface ImageGenState {
  tasks: ImageGenTask[];
  
  addTask: (task: ImageGenTask) => void;
  updateTask: (id: string, updates: Partial<ImageGenTask>) => void;
  getTasksByConversation: (conversationId: string) => ImageGenTask[];
  removeTask: (id: string) => void;
  
  // Clean up old tasks? Maybe not needed for MVP
}

export const useImageGenStore = create<ImageGenState>()(
  persist(
    (set, get) => ({
      tasks: [],

      addTask: (task) =>
        set((state) => ({
          tasks: [...state.tasks, task],
        })),

      updateTask: (id, updates) =>
        set((state) => ({
          tasks: state.tasks.map((t) =>
            t.id === id ? { ...t, ...updates } : t
          ),
        })),

      getTasksByConversation: (conversationId) => {
        return get().tasks.filter((t) => t.conversationId === conversationId);
      },

      removeTask: (id) =>
        set((state) => ({
          tasks: state.tasks.filter((t) => t.id !== id),
        })),
    }),
    {
      name: 'image-gen-store',
      version: 1,
    }
  )
);
