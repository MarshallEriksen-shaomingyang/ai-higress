"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Layout } from "react-resizable-panels";
import { toast } from "sonner";
import { Menu } from "lucide-react";

import { ProjectSelector } from "@/components/chat/project-selector";
import { AssistantList } from "@/components/chat/assistant-list";
import { ConversationList } from "@/components/chat/conversation-list";
import { ErrorAlert } from "@/components/chat/error-alert";
import { useAuth } from "@/components/providers/auth-provider";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";
import type {
  Assistant,
  CreateAssistantRequest,
  CreateConversationRequest,
  UpdateAssistantRequest,
} from "@/lib/api-types";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useChatStore } from "@/lib/stores/chat-store";
import {
  useAssistants,
  useCreateAssistant,
  useDeleteAssistant,
  useUpdateAssistant,
} from "@/lib/swr/use-assistants";
import {
  useConversations,
  useCreateConversation,
  useDeleteConversation,
  useUpdateConversation,
} from "@/lib/swr/use-conversations";
import { ChatNavRail } from "./chat-nav-rail";

const AssistantForm = dynamic(
  () =>
    import("@/components/chat/assistant-form").then((mod) => ({
      default: mod.AssistantForm,
    })),
  { ssr: false }
);

export function ChatLayoutRootClient({
  children,
}: {
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  const { user, isLoading } = useAuth();
  const router = useRouter();

  const {
    selectedProjectId,
    selectedAssistantId,
    selectedConversationId,
    setSelectedAssistant,
    setSelectedConversation,
  } = useChatStore();

  const setLayout = useChatLayoutStore((s) => s.setLayout);
  const activeTab = useChatLayoutStore((s) => s.activeTab);
  const setActiveTab = useChatLayoutStore((s) => s.setActiveTab);

  const defaultLayout = useMemo(() => {
    const storedLayout = useChatLayoutStore.getState().layout;
    if (!storedLayout) return undefined;

    const isValidStoredLayout =
      storedLayout &&
      typeof storedLayout === "object" &&
      "chat-sidebar" in storedLayout &&
      "chat-main" in storedLayout &&
      Object.keys(storedLayout).length === 2;

    return isValidStoredLayout ? storedLayout : undefined;
  }, []);

  const layoutDebounceTimerRef = useRef<number | null>(null);
  const pendingLayoutRef = useRef<Layout | null>(null);

  const handleLayoutChange = useCallback(
    (layout: Layout) => {
      pendingLayoutRef.current = layout;
      if (layoutDebounceTimerRef.current !== null) {
        window.clearTimeout(layoutDebounceTimerRef.current);
      }
      layoutDebounceTimerRef.current = window.setTimeout(() => {
        if (pendingLayoutRef.current) {
          setLayout(pendingLayoutRef.current);
        }
      }, 200);
    },
    [setLayout]
  );

  useEffect(() => {
    return () => {
      if (layoutDebounceTimerRef.current !== null) {
        window.clearTimeout(layoutDebounceTimerRef.current);
      }
      if (pendingLayoutRef.current) {
        setLayout(pendingLayoutRef.current);
      }
    };
  }, [setLayout]);

  const [isAssistantDialogOpen, setIsAssistantDialogOpen] = useState(false);
  const [editingAssistant, setEditingAssistant] = useState<Assistant | null>(
    null
  );
  const [deleteConfirmAssistant, setDeleteConfirmAssistant] = useState<
    string | null
  >(null);
  const [deleteConfirmConversation, setDeleteConfirmConversation] = useState<
    string | null
  >(null);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const hasInitialized = useRef(false);

  const {
    assistants,
    isLoading: isLoadingAssistants,
    error: assistantsError,
    mutate: mutateAssistants,
  } = useAssistants(
    user && selectedProjectId
      ? {
          project_id: selectedProjectId,
          limit: 50,
        }
      : { project_id: "", limit: 0 }
  );

  const {
    conversations,
    isLoading: isLoadingConversations,
    error: conversationsError,
    mutate: mutateConversations,
  } = useConversations(
    user && selectedAssistantId
      ? {
          assistant_id: selectedAssistantId,
          limit: 50,
        }
      : { assistant_id: "", limit: 0 }
  );

  const createAssistant = useCreateAssistant();
  const updateAssistant = useUpdateAssistant();
  const deleteAssistant = useDeleteAssistant();
  const createConversation = useCreateConversation();
  const deleteConversation = useDeleteConversation();
  const updateConversation = useUpdateConversation();

  useEffect(() => {
    if (!isLoading && !user) {
      router.push("/");
    }
  }, [user, isLoading, router]);

  useEffect(() => {
    if (
      !hasInitialized.current &&
      selectedAssistantId &&
      activeTab === "assistants"
    ) {
      setActiveTab("conversations");
      hasInitialized.current = true;
    }
  }, [selectedAssistantId, activeTab, setActiveTab]);

  if (isLoading || !user) {
    return null;
  }

  const handleSelectAssistant = (assistantId: string) => {
    setSelectedAssistant(assistantId);
    setSelectedConversation(null);
    setActiveTab("conversations");
    setIsMobileSidebarOpen(false); // 移动端选择助手后关闭侧边栏
    router.push(`/chat/${assistantId}`);
  };

  const handleCreateAssistant = () => {
    setEditingAssistant(null);
    setIsAssistantDialogOpen(true);
  };

  const handleEditAssistant = (assistant: Assistant) => {
    setEditingAssistant(assistant);
    setIsAssistantDialogOpen(true);
  };

  const handleSaveAssistant = async (
    data: CreateAssistantRequest | UpdateAssistantRequest
  ) => {
    if (!selectedProjectId) {
      toast.error(t("chat.project.not_selected"));
      return;
    }
    try {
      if (editingAssistant) {
        await updateAssistant(
          editingAssistant.assistant_id,
          data as UpdateAssistantRequest
        );
        toast.success(t("chat.assistant.updated"));
      } else {
        const newAssistant = await createAssistant({
          ...(data as CreateAssistantRequest),
          project_id: selectedProjectId,
        });
        toast.success(t("chat.assistant.created"));
        handleSelectAssistant(newAssistant.assistant_id);
      }
      setIsAssistantDialogOpen(false);
      mutateAssistants();
    } catch (error) {
      console.error("Failed to save assistant:", error);
      toast.error(t("chat.errors.invalid_config"));
    }
  };

  const handleDeleteAssistant = async (assistantId: string) => {
    setDeleteConfirmAssistant(assistantId);
  };

  const confirmDeleteAssistant = async () => {
    if (!deleteConfirmAssistant) return;
    try {
      await deleteAssistant(deleteConfirmAssistant);
      toast.success(t("chat.assistant.deleted"));
      if (selectedAssistantId === deleteConfirmAssistant) {
        setSelectedAssistant(null);
        setSelectedConversation(null);
        router.push("/chat");
      }
      mutateAssistants();
    } catch (error) {
      console.error("Failed to delete assistant:", error);
      toast.error(t("chat.errors.invalid_config"));
    } finally {
      setDeleteConfirmAssistant(null);
    }
  };

  const handleSelectConversation = (conversationId: string) => {
    if (!selectedAssistantId) return;
    setSelectedConversation(conversationId);
    setActiveTab("conversations");
    setIsMobileSidebarOpen(false); // 移动端选择会话后关闭侧边栏
    router.push(`/chat/${selectedAssistantId}/${conversationId}`);
  };

  const handleCreateConversation = async () => {
    if (!selectedAssistantId || !selectedProjectId) return;
    try {
      const newConversation = await createConversation({
        assistant_id: selectedAssistantId,
        project_id: selectedProjectId,
      } as CreateConversationRequest);
      toast.success(t("chat.conversation.created"));
      handleSelectConversation(newConversation.conversation_id);
      mutateConversations();
    } catch (error) {
      console.error("Failed to create conversation:", error);
      toast.error(t("chat.errors.invalid_config"));
    }
  };

  const handleArchiveConversation = async (conversationId: string) => {
    try {
      await updateConversation(conversationId, { archived: true });
      toast.success(t("chat.conversation.archived"));
      mutateConversations();
    } catch (error) {
      console.error("Failed to archive conversation:", error);
      toast.error(t("chat.errors.invalid_config"));
    }
  };

  const handleRenameConversation = async (conversationId: string, title: string) => {
    try {
      await updateConversation(conversationId, { title });
      toast.success(t("chat.conversation.renamed"));
      mutateConversations();
    } catch (error) {
      console.error("Failed to rename conversation:", error);
      toast.error(t("chat.conversation.rename_failed"));
    }
  };

  const handleDeleteConversation = async (conversationId: string) => {
    setDeleteConfirmConversation(conversationId);
  };

  const confirmDeleteConversation = async () => {
    if (!deleteConfirmConversation) return;
    try {
      await deleteConversation(deleteConfirmConversation);
      toast.success(t("chat.conversation.deleted"));
      mutateConversations();
    } catch (error) {
      console.error("Failed to delete conversation:", error);
      toast.error(t("chat.errors.invalid_config"));
    } finally {
      setDeleteConfirmConversation(null);
    }
  };

  // 侧边栏内容组件（桌面端和移动端共用）
  const SidebarContent = () => (
    <div className="flex h-full flex-col">
      <div className="border-b p-4">
        <ProjectSelector />
      </div>

      {selectedProjectId ? (
        <Tabs
          value={activeTab}
          onValueChange={(value) =>
            setActiveTab(value as "assistants" | "conversations")
          }
          className="flex flex-1 flex-col min-h-0"
        >
          <div className="border-b px-4 pt-4">
            <TabsList className="w-full">
              <TabsTrigger value="assistants" className="flex-1">
                {t("chat.assistant.title")}
              </TabsTrigger>
              <TabsTrigger
                value="conversations"
                className="flex-1"
                disabled={!selectedAssistantId}
              >
                {t("chat.conversation.title")}
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent
            value="assistants"
            className="flex-1 overflow-y-auto p-4 mt-0 min-h-0"
          >
            {assistantsError ? (
              <ErrorAlert error={assistantsError} />
            ) : (
              <AssistantList
                assistants={assistants}
                isLoading={isLoadingAssistants}
                selectedAssistantId={selectedAssistantId || undefined}
                onSelectAssistant={handleSelectAssistant}
                onCreateAssistant={handleCreateAssistant}
                onEditAssistant={handleEditAssistant}
                onDeleteAssistant={handleDeleteAssistant}
              />
            )}
          </TabsContent>

          <TabsContent
            value="conversations"
            className="flex-1 overflow-y-auto p-4 mt-0 min-h-0"
          >
            {conversationsError ? (
              <ErrorAlert error={conversationsError} />
            ) : (
              <ConversationList
                conversations={conversations}
                isLoading={isLoadingConversations}
                assistantId={selectedAssistantId || undefined}
                selectedConversationId={selectedConversationId || undefined}
                onSelectConversation={handleSelectConversation}
                onCreateConversation={handleCreateConversation}
                onArchiveConversation={handleArchiveConversation}
                onRenameConversation={handleRenameConversation}
                onDeleteConversation={handleDeleteConversation}
              />
            )}
          </TabsContent>
        </Tabs>
      ) : (
        <div className="flex flex-1 items-center justify-center p-6">
          <p className="text-sm text-muted-foreground">
            {t("chat.project.not_selected")}
          </p>
        </div>
      )}
    </div>
  );

  return (
    <>
      <div className="flex h-full w-full overflow-hidden">
        {/* 移动端顶部菜单栏 */}
        <div className="md:hidden fixed top-0 left-0 right-0 z-50 flex items-center gap-2 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 py-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsMobileSidebarOpen(true)}
            className="h-9 w-9"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">
              {selectedProjectId ? t("chat.title") : t("chat.project.not_selected")}
            </div>
          </div>
          <ChatNavRail variant="mobile" />
        </div>

        {/* 移动端侧边栏抽屉 */}
        <Sheet open={isMobileSidebarOpen} onOpenChange={setIsMobileSidebarOpen}>
          <SheetContent side="left" className="w-[85vw] max-w-sm p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>{t("chat.sidebar.title")}</SheetTitle>
            </SheetHeader>
            <SidebarContent />
          </SheetContent>
        </Sheet>

        {/* 桌面端布局 */}
        <ResizablePanelGroup
          id="chat-layout"
          direction="horizontal"
          defaultLayout={defaultLayout}
          onLayoutChange={handleLayoutChange}
          className="h-full w-full"
        >
          <ResizablePanel
            id="chat-sidebar"
            defaultSize="25%"
            minSize="0%"
            maxSize="100%"
            className="hidden md:block"
          >
            <SidebarContent />
          </ResizablePanel>

          <ResizableHandle withHandle className="hidden md:flex" />

          <ResizablePanel id="chat-main" defaultSize="75%" minSize="0%" maxSize="100%">
            <div className="h-full overflow-hidden pt-[52px] md:pt-0">
              {selectedProjectId ? (
                children
              ) : (
                <div className="flex h-full items-center justify-center p-6">
                  <p className="text-muted-foreground">
                    {t("chat.project.not_selected")}
                  </p>
                </div>
              )}
            </div>
          </ResizablePanel>
        </ResizablePanelGroup>
      </div>

      {selectedProjectId && (
        <AssistantForm
          open={isAssistantDialogOpen}
          onOpenChange={setIsAssistantDialogOpen}
          editingAssistant={editingAssistant}
          projectId={selectedProjectId}
          onSubmit={handleSaveAssistant}
        />
      )}

      <AlertDialog
        open={!!deleteConfirmAssistant}
        onOpenChange={() => setDeleteConfirmAssistant(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("chat.assistant.delete")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("chat.assistant.delete_confirm")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("chat.action.cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteAssistant}>
              {t("chat.action.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={!!deleteConfirmConversation}
        onOpenChange={() => setDeleteConfirmConversation(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("chat.conversation.delete")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("chat.conversation.delete_confirm")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("chat.action.cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteConversation}>
              {t("chat.action.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
