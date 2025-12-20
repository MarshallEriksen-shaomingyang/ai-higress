"use client";

import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { Layout } from "react-resizable-panels";
import { toast } from "sonner";

import { useAuth } from "@/components/providers/auth-provider";
import { MessageInput } from "@/components/chat/message-input";
import { MessageList } from "@/components/chat/message-list";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useI18n } from "@/lib/i18n-context";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useChatStore } from "@/lib/stores/chat-store";
import { useConversationFromList } from "@/lib/swr/use-conversations";
import { useCreateEval } from "@/lib/swr/use-evals";
import { ConversationHeader } from "./conversation-header";

const EvalPanel = dynamic(
  () =>
    import("@/components/chat/eval-panel").then((mod) => ({
      default: mod.EvalPanel,
    })),
  {
    loading: () => (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    ),
    ssr: false,
  }
);

export function ConversationPageClient({
  assistantId,
  conversationId,
}: {
  assistantId: string;
  conversationId: string;
}) {
  const { t } = useI18n();
  const { user } = useAuth();

  const conversation = useConversationFromList(conversationId, assistantId);
  const {
    selectedProjectId,
    activeEvalId,
    setActiveEval,
    conversationModelOverrides,
  } = useChatStore();
  const setChatVerticalLayout = useChatLayoutStore((s) => s.setChatVerticalLayout);
  const createEval = useCreateEval();

  const defaultVerticalLayout = useMemo(() => {
    const storedVerticalLayout = useChatLayoutStore.getState().chatVerticalLayout;
    if (!storedVerticalLayout) return undefined;

    const isValid =
      storedVerticalLayout &&
      typeof storedVerticalLayout === "object" &&
      "message-list" in storedVerticalLayout &&
      "message-input" in storedVerticalLayout &&
      Object.keys(storedVerticalLayout).length === 2;

    return isValid ? storedVerticalLayout : undefined;
  }, []);

  const verticalLayoutDebounceTimerRef = useRef<number | null>(null);
  const pendingVerticalLayoutRef = useRef<Layout | null>(null);

  const handleVerticalLayoutChange = useCallback(
    (layout: Layout) => {
      pendingVerticalLayoutRef.current = layout;
      if (verticalLayoutDebounceTimerRef.current !== null) {
        window.clearTimeout(verticalLayoutDebounceTimerRef.current);
      }
      verticalLayoutDebounceTimerRef.current = window.setTimeout(() => {
        if (pendingVerticalLayoutRef.current) {
          setChatVerticalLayout(pendingVerticalLayoutRef.current);
        }
      }, 200);
    },
    [setChatVerticalLayout]
  );

  useEffect(() => {
    return () => {
      if (verticalLayoutDebounceTimerRef.current !== null) {
        window.clearTimeout(verticalLayoutDebounceTimerRef.current);
      }
      if (pendingVerticalLayoutRef.current) {
        setChatVerticalLayout(pendingVerticalLayoutRef.current);
      }
    };
  }, [setChatVerticalLayout]);

  const handleTriggerEval = async (messageId: string, baselineRunId: string) => {
    if (!user || !selectedProjectId) return;

    try {
      const result = await createEval({
        project_id: selectedProjectId,
        assistant_id: assistantId,
        conversation_id: conversationId,
        message_id: messageId,
        baseline_run_id: baselineRunId,
      });

      setActiveEval(result.eval_id);
      toast.success(t("chat.eval.trigger_success"));
    } catch (error) {
      console.error("Failed to trigger eval:", error);
      toast.error(t("chat.eval.trigger_failed"));
    }
  };

  const handleCloseEval = () => {
    setActiveEval(null);
  };

  if (!conversation) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">
            {t("chat.errors.conversation_not_found")}
          </div>
        </div>
      </div>
    );
  }

  const isArchived = conversation.archived;
  const overrideLogicalModel = conversationModelOverrides[conversationId] ?? null;

  return (
    <div className="flex flex-col h-full">
      <ConversationHeader
        assistantId={assistantId}
        conversationId={conversationId}
        title={conversation.title}
      />

      {isArchived && (
        <div className="bg-muted/50 border-b px-4 py-2 text-sm text-muted-foreground text-center">
          {t("chat.conversation.archived_notice")}
        </div>
      )}

      <div className="flex-1 overflow-hidden">
        <ResizablePanelGroup
          id="chat-vertical-layout"
          direction="vertical"
          defaultLayout={defaultVerticalLayout}
          onLayoutChange={handleVerticalLayoutChange}
        >
          <ResizablePanel
            id="message-list"
            defaultSize="70"
            minSize="50"
            maxSize="85"
          >
            <div className="h-full overflow-hidden">
              <MessageList
                conversationId={conversationId}
                onTriggerEval={handleTriggerEval}
              />
            </div>
          </ResizablePanel>

          <ResizableHandle withHandle />

          <ResizablePanel
            id="message-input"
            defaultSize="30"
            minSize="15"
            maxSize="50"
          >
            <div className="h-full bg-background">
              <MessageInput
                conversationId={conversationId}
                assistantId={assistantId}
                overrideLogicalModel={overrideLogicalModel}
                disabled={isArchived}
                layout="fill"
                className="h-full border-t-0"
              />
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      {activeEvalId && (
        <div className="fixed inset-y-0 right-0 w-96 border-l bg-background shadow-lg z-50 overflow-y-auto">
          <EvalPanel evalId={activeEvalId} onClose={handleCloseEval} />
        </div>
      )}
    </div>
  );
}
