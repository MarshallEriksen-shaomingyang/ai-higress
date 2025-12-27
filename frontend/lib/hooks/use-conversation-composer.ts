"use client";

import { useCallback, useEffect, useMemo } from "react";

import type { ComposerMode } from "@/lib/chat/composer-modes";
import {
  getConversationComposerState,
  useChatComposerStore,
} from "@/lib/stores/chat-composer-store";

export function useConversationComposer(conversationId: string) {
  const snapshot = useChatComposerStore(
    useCallback(
      (s) => getConversationComposerState(s, conversationId),
      [conversationId]
    )
  );
  const ensureConversation = useChatComposerStore((s) => s.ensureConversation);
  const setActiveMode = useChatComposerStore((s) => s.setActiveMode);
  const setImageState = useChatComposerStore((s) => s.setImageState);

  useEffect(() => {
    ensureConversation(conversationId);
  }, [conversationId, ensureConversation]);

  const setMode = useCallback(
    (mode: ComposerMode) => setActiveMode(conversationId, mode),
    [conversationId, setActiveMode]
  );

  const setImageParams = useCallback(
    (
      updates: {
        model?: string;
        size?: string;
        n?: number;
        enableGoogleSearch?: boolean;
        sendResponseFormat?: boolean;
      }
    ) =>
      setImageState(conversationId, updates),
    [conversationId, setImageState]
  );

  return useMemo(
    () => ({
      mode: snapshot.activeMode,
      image: snapshot.image,
      setMode,
      setImageParams,
    }),
    [snapshot.activeMode, snapshot.image, setImageParams, setMode]
  );
}
