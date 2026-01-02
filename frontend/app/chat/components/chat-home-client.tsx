"use client";

import { useMemo, useState, useCallback, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import type { Layout } from "react-resizable-panels";

import { useChatStore } from "@/lib/stores/chat-store";
import { useAssistants } from "@/lib/swr/use-assistants";
import { useConversations } from "@/lib/swr/use-conversations";
import { SlateChatInput } from "@/components/chat/slate-chat-input";
import { useQuickStartChat } from "@/lib/hooks/use-quick-start-chat";
import type { ComposerMode } from "@/components/chat/chat-input/chat-toolbar";
import type { ImageGenParams } from "@/components/chat/slate-chat-input";
import { ChatWelcomeContent } from "@/components/chat/chat-welcome-content";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";

export function ChatHomeClient({ assistantId }: { assistantId?: string | null } = {}) {
  const router = useRouter();
  const { selectedProjectId, selectedAssistantId, setSelectedConversation } = useChatStore();
  const setChatVerticalLayout = useChatLayoutStore((s) => s.setChatVerticalLayout);
  const hasAutoNavigated = useRef(false);

  const needsAutoAssistant = !assistantId && !selectedAssistantId;
  const { assistants } = useAssistants(
    needsAutoAssistant && selectedProjectId
      ? { project_id: selectedProjectId, limit: 50 }
      : { project_id: "", limit: 0 }
  );

  // 确定目标助手ID
  const targetAssistantId = useMemo(() => {
    return assistantId ?? selectedAssistantId ?? assistants[0]?.assistant_id ?? null;
  }, [assistantId, selectedAssistantId, assistants]);

  // 获取会话列表用于自动导航
  const { conversations, isLoading: isLoadingConversations } = useConversations(
    targetAssistantId
      ? { assistant_id: targetAssistantId, limit: 50 }
      : { assistant_id: "", limit: 0 }
  );

  // 自动导航到第一个会话：当用户在欢迎页面且有会话可选时
  useEffect(() => {
    // 防止重复导航
    if (hasAutoNavigated.current) return;

    // 条件：有目标助手、会话列表已加载完成、有会话可选
    if (
      targetAssistantId &&
      !isLoadingConversations &&
      conversations.length > 0
    ) {
      const firstConversation = conversations[0];
      if (firstConversation) {
        hasAutoNavigated.current = true;
        setSelectedConversation(firstConversation.conversation_id);
        router.push(`/chat/${targetAssistantId}/${firstConversation.conversation_id}`);
      }
    }
  }, [
    targetAssistantId,
    isLoadingConversations,
    conversations,
    setSelectedConversation,
    router,
  ]);

  const { handleSend, isSubmitting, canSubmit } = useQuickStartChat({
    assistantId: targetAssistantId,
  });

  // 模式切换状态
  const [mode, setMode] = useState<ComposerMode>("chat");
  const [imageGenParams, setImageGenParams] = useState<ImageGenParams>({
    model: "",
    size: "1024x1024",
    n: 1,
    quality: "auto",
    enableGoogleSearch: false,
  });

  const defaultVerticalLayout = useMemo(() => {
    const storedVerticalLayout = useChatLayoutStore.getState().chatVerticalLayout;
    if (!storedVerticalLayout) return undefined;

    const isValid =
      typeof storedVerticalLayout === "object" &&
      storedVerticalLayout !== null &&
      "message-list" in storedVerticalLayout &&
      "message-input" in storedVerticalLayout &&
      Object.keys(storedVerticalLayout).length === 2;

    return isValid ? storedVerticalLayout : undefined;
  }, []);

  const handleVerticalLayoutChange = useCallback(
    (layout: Layout) => {
      setChatVerticalLayout(layout);
    },
    [setChatVerticalLayout]
  );

  return (
    <div className="flex h-full flex-col">
      <ResizablePanelGroup
        id="chat-home-vertical-layout"
        direction="vertical"
        defaultLayout={defaultVerticalLayout}
        onLayoutChange={handleVerticalLayoutChange}
      >
        <ResizablePanel
          id="message-list"
          defaultSize="70%"
          minSize="0%"
          maxSize="100%"
        >
          <div className="h-full overflow-y-auto">
            <ChatWelcomeContent />
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle aria-orientation="horizontal" />

        <ResizablePanel
          id="message-input"
          defaultSize="30%"
          minSize="0%"
          maxSize="100%"
        >
          <div className="h-full flex flex-col">
            <div className="flex-1 min-h-0 flex flex-col justify-end p-4 pb-6">
              <div className="mx-auto w-full max-w-3xl flex flex-col gap-3 min-h-0">
                <div className="flex-1 min-h-0">
                  <SlateChatInput
                    conversationId="welcome"
                    assistantId={targetAssistantId ?? undefined}
                    projectId={selectedProjectId}
                    disabled={!canSubmit || isSubmitting}
                    mode={mode}
                    onModeChange={setMode}
                    imageGenParams={imageGenParams}
                    onImageGenParamsChange={setImageGenParams}
                    onSend={handleSend}
                    hideModeSwitcher={false}
                    className="border-0 h-full"
                  />
                </div>
              </div>
            </div>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
