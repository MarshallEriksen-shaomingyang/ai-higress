"use client";

import dynamic from "next/dynamic";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { AssistantList } from "@/components/chat/assistant-list";
import { ConversationList } from "@/components/chat/conversation-list";
import { ProjectSelector } from "@/components/chat/project-selector";
import { ErrorAlert } from "@/components/chat/error-alert";
import { useChatStore } from "@/lib/stores/chat-store";
import { useChatLayoutStore } from "@/lib/stores/chat-layout-store";
import { useAuth } from "@/components/providers/auth-provider";
import { useRouter } from "next/navigation";
import React, { useEffect, useState, useMemo, useRef } from "react";
import {
  useAssistants,
  useCreateAssistant,
  useUpdateAssistant,
  useDeleteAssistant,
} from "@/lib/swr/use-assistants";
import { useConversations, useCreateConversation, useDeleteConversation } from "@/lib/swr/use-conversations";
import { useLogicalModels } from "@/lib/swr/use-logical-models";
import { toast } from "sonner";
import { useI18n } from "@/lib/i18n-context";
import type { Assistant, CreateAssistantRequest, UpdateAssistantRequest, CreateConversationRequest } from "@/lib/api-types";
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

// 动态导入助手表单（仅在打开对话框时加载）
const AssistantForm = dynamic(
  () => import("@/components/chat/assistant-form").then((mod) => ({ default: mod.AssistantForm })),
  { ssr: false }
);

/**
 * 聊天模块布局
 * 
 * 包含：
 * - 左侧边栏：助手列表 + 会话列表（可调整宽度）
 * - 主内容区：聊天页面或提示页面
 */
export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const { selectedProjectId, selectedAssistantId, setSelectedAssistant, setSelectedConversation } = useChatStore();
  const storedLayout = useChatLayoutStore((s) => s.layout);
  const setLayout = useChatLayoutStore((s) => s.setLayout);
  const activeTab = useChatLayoutStore((s) => s.activeTab);
  const setActiveTab = useChatLayoutStore((s) => s.setActiveTab);

  // 验证并准备默认布局
  const defaultLayout = useMemo(() => {
    if (!storedLayout) return undefined;
    
    const isValidStoredLayout =
      storedLayout &&
      typeof storedLayout === 'object' &&
      "chat-sidebar" in storedLayout &&
      "chat-main" in storedLayout &&
      Object.keys(storedLayout).length === 2;
    
    return isValidStoredLayout ? storedLayout : undefined;
  }, [storedLayout]);

  // 对话框状态
  const [isAssistantDialogOpen, setIsAssistantDialogOpen] = useState(false);
  const [editingAssistant, setEditingAssistant] = useState<Assistant | null>(null);
  const [deleteConfirmAssistant, setDeleteConfirmAssistant] = useState<string | null>(null);
  const [deleteConfirmConversation, setDeleteConfirmConversation] = useState<string | null>(null);

  // 标记是否已完成初始加载
  const hasInitialized = useRef(false);

  // 获取助手列表（仅当已登录且选中项目时）
  const { assistants, isLoading: isLoadingAssistants, error: assistantsError, mutate: mutateAssistants } = useAssistants(
    user && selectedProjectId
      ? {
          project_id: selectedProjectId,
          limit: 50,
        }
      : { project_id: '', limit: 0 }
  );

  // 获取会话列表（仅当已登录且选中助手时）
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
      : { assistant_id: '', limit: 0 }
  );

  // 获取可用逻辑模型列表（用于助手默认模型下拉）
  const { models: logicalModels } = useLogicalModels();

  const availableAssistantModels = useMemo(() => {
    const modelSet = new Set<string>(["auto"]);

    for (const model of logicalModels) {
      if (!model.enabled) continue;
      if (!model.capabilities?.includes("chat")) continue;
      modelSet.add(model.logical_id);
    }

    // 编辑时确保当前值可选（即便该模型暂时不可用/被禁用）
    if (editingAssistant?.default_logical_model) {
      modelSet.add(editingAssistant.default_logical_model);
    }

    return ["auto", ...Array.from(modelSet).filter((m) => m !== "auto").sort()];
  }, [logicalModels, editingAssistant?.default_logical_model]);

  // Mutation hooks
  const createAssistant = useCreateAssistant();
  const updateAssistant = useUpdateAssistant();
  const deleteAssistant = useDeleteAssistant();
  const createConversation = useCreateConversation();
  const deleteConversation = useDeleteConversation();

  // 未登录时重定向到首页
  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/');
    }
  }, [user, isLoading, router]);

  // 页面初始加载时，如果已选中助手，自动切换到会话 Tab（仅执行一次）
  useEffect(() => {
    if (!hasInitialized.current && selectedAssistantId && activeTab === "assistants") {
      setActiveTab("conversations");
      hasInitialized.current = true;
    }
  }, [selectedAssistantId, activeTab, setActiveTab]);

  // 加载中或未登录时不渲染
  if (isLoading || !user) {
    return null;
  }

  // 助手操作
  const handleSelectAssistant = (assistantId: string) => {
    setSelectedAssistant(assistantId);
    setSelectedConversation(null);
    setActiveTab("conversations"); // 自动切换到会话 Tab
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

  const handleSaveAssistant = async (data: CreateAssistantRequest | UpdateAssistantRequest) => {
    if (!selectedProjectId) {
      toast.error(t('chat.project.not_selected'));
      return;
    }
    try {
      if (editingAssistant) {
        await updateAssistant(editingAssistant.assistant_id, data as UpdateAssistantRequest);
        toast.success(t('chat.assistant.updated'));
      } else {
        const newAssistant = await createAssistant({ ...data, project_id: selectedProjectId } as CreateAssistantRequest);
        toast.success(t('chat.assistant.created'));
        handleSelectAssistant(newAssistant.assistant_id);
      }
      setIsAssistantDialogOpen(false);
      mutateAssistants();
    } catch (error) {
      console.error('Failed to save assistant:', error);
      toast.error(t('chat.errors.invalid_config'));
    }
  };

  const handleDeleteAssistant = async (assistantId: string) => {
    setDeleteConfirmAssistant(assistantId);
  };

  const confirmDeleteAssistant = async () => {
    if (!deleteConfirmAssistant) return;
    try {
      await deleteAssistant(deleteConfirmAssistant);
      toast.success(t('chat.assistant.deleted'));
      if (selectedAssistantId === deleteConfirmAssistant) {
        setSelectedAssistant(null);
        setSelectedConversation(null);
        router.push('/chat');
      }
      mutateAssistants();
    } catch (error) {
      console.error('Failed to delete assistant:', error);
      toast.error(t('chat.errors.invalid_config'));
    } finally {
      setDeleteConfirmAssistant(null);
    }
  };

  // 会话操作
  const handleSelectConversation = (conversationId: string) => {
    if (!selectedAssistantId) return;
    setSelectedConversation(conversationId);
    setActiveTab("conversations"); // 确保在会话 Tab
    router.push(`/chat/${selectedAssistantId}/${conversationId}`);
  };

  const handleCreateConversation = async () => {
    if (!selectedAssistantId || !selectedProjectId) return;
    try {
      const newConversation = await createConversation({
        assistant_id: selectedAssistantId,
        project_id: selectedProjectId,
      } as CreateConversationRequest);
      toast.success(t('chat.conversation.created'));
      handleSelectConversation(newConversation.conversation_id);
      mutateConversations();
    } catch (error) {
      console.error('Failed to create conversation:', error);
      toast.error(t('chat.errors.invalid_config'));
    }
  };

  const handleDeleteConversation = async (conversationId: string) => {
    setDeleteConfirmConversation(conversationId);
  };

  const confirmDeleteConversation = async () => {
    if (!deleteConfirmConversation) return;
    try {
      await deleteConversation(deleteConfirmConversation);
      toast.success(t('chat.conversation.deleted'));
      mutateConversations();
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      toast.error(t('chat.errors.invalid_config'));
    } finally {
      setDeleteConfirmConversation(null);
    }
  };

  return (
    <>
      <div className="flex h-screen flex-col bg-background overflow-hidden w-full">
        {/* 项目选择器 */}
        <div className="border-b p-4">
          <ProjectSelector />
        </div>

        {/* 主内容区 */}
        {selectedProjectId ? (
          <div className="flex-1 overflow-hidden">
            <ResizablePanelGroup
              id="chat-layout"
              direction="horizontal"
              defaultLayout={defaultLayout}
              onLayoutChange={setLayout}
            >
              {/* 左侧边栏：助手和会话 Tab 切换 */}
              <ResizablePanel id="chat-sidebar" defaultSize="25%" minSize="20%" maxSize="50%">
                <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as "assistants" | "conversations")} className="flex flex-col h-full border-r">
                  <div className="border-b px-4 pt-4">
                    <TabsList className="w-full">
                      <TabsTrigger value="assistants" className="flex-1">
                        {t('chat.assistant.title')}
                      </TabsTrigger>
                      <TabsTrigger value="conversations" className="flex-1" disabled={!selectedAssistantId}>
                        {t('chat.conversation.title')}
                      </TabsTrigger>
                    </TabsList>
                  </div>
                  
                  <TabsContent value="assistants" className="flex-1 overflow-y-auto p-4 mt-0">
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
                  
                  <TabsContent value="conversations" className="flex-1 overflow-y-auto p-4 mt-0">
                    {conversationsError ? (
                      <ErrorAlert error={conversationsError} />
                    ) : (
                      <ConversationList
                        conversations={conversations}
                        isLoading={isLoadingConversations}
                        onSelectConversation={handleSelectConversation}
                        onCreateConversation={handleCreateConversation}
                        onDeleteConversation={handleDeleteConversation}
                      />
                    )}
                  </TabsContent>
                </Tabs>
              </ResizablePanel>

              {/* 调整宽度的手柄 */}
              <ResizableHandle withHandle />

              {/* 主内容区 */}
              <ResizablePanel id="chat-main" defaultSize="75%">
                <div className="h-full overflow-hidden">
                  {children}
                </div>
              </ResizablePanel>
            </ResizablePanelGroup>
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center">
            <p className="text-muted-foreground">{t('chat.project.not_selected')}</p>
          </div>
        )}
      </div>

      {/* 助手创建/编辑对话框 */}
      {selectedProjectId && (
        <AssistantForm
          open={isAssistantDialogOpen}
          onOpenChange={setIsAssistantDialogOpen}
          editingAssistant={editingAssistant}
          projectId={selectedProjectId}
          onSubmit={handleSaveAssistant}
          availableModels={availableAssistantModels}
        />
      )}

      {/* 删除助手确认对话框 */}
      <AlertDialog open={!!deleteConfirmAssistant} onOpenChange={() => setDeleteConfirmAssistant(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('chat.assistant.delete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('chat.assistant.delete_confirm')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('chat.action.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteAssistant}>
              {t('chat.action.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 删除会话确认对话框 */}
      <AlertDialog open={!!deleteConfirmConversation} onOpenChange={() => setDeleteConfirmConversation(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('chat.conversation.delete')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('chat.conversation.delete_confirm')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('chat.action.cancel')}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteConversation}>
              {t('chat.action.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
