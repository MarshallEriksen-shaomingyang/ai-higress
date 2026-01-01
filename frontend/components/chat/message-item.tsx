"use client";

import { formatDistanceToNow, format } from "date-fns";
import { zhCN, enUS } from "date-fns/locale";
import {
  User,
  Bot,
  Eye,
  Sparkles,
  Plus,
  Layers,
  RotateCw,
  Trash2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n-context";
import type { Message, RunSummary } from "@/lib/api-types";
import type { ComparisonVariant } from "@/lib/stores/chat-comparison-store";
import { useUserPreferencesStore } from "@/lib/stores/user-preferences-store";
import { cn } from "@/lib/utils";
import { MessageContent } from "./message-content";
import { MessageBubble } from "./message-bubble";
import { ToolInvocationBubbles } from "./tool-invocation-bubbles";
import { MessageTtsControl } from "./message-tts-control";

export interface MessageItemProps {
  message: Message;
  runs?: RunSummary[]; // 改为 runs 数组
  runSourceMessageId?: string; // runs 所属的 user message_id（用于创建 eval）
  projectId?: string | null;
  defaultTtsModel?: string | null;
  userAvatarUrl?: string | null;
  userDisplayName?: string | null;
  onViewDetails?: (runId: string) => void;
  onTriggerEval?: (messageId: string, runId: string) => void; // 添加 messageId 参数
  showEvalButton?: boolean;
  comparisonVariants?: ComparisonVariant[];
  onAddComparison?: (assistantMessageId: string, sourceUserMessageId: string) => void;
  isLatestAssistant?: boolean;
  enableTypewriter?: boolean;
  typewriterKey?: string;
  onRegenerate?: (assistantMessageId: string, sourceUserMessageId?: string) => void;
  onDeleteMessage?: () => void;
  disableActions?: boolean;
  isRegenerating?: boolean;
  isDeletingMessage?: boolean;
  errorMessage?: string | null;
}

export function MessageItem({
  message,
  runs = [], // 默认为空数组
  runSourceMessageId,
  projectId = null,
  defaultTtsModel = null,
  userAvatarUrl,
  userDisplayName,
  onViewDetails,
  onTriggerEval,
  showEvalButton = true,
  comparisonVariants = [],
  onAddComparison,
  isLatestAssistant = false,
  enableTypewriter = false,
  typewriterKey,
  onRegenerate,
  onDeleteMessage,
  disableActions = false,
  isRegenerating = false,
  isDeletingMessage = false,
  errorMessage = null,
}: MessageItemProps) {
  const { t, language } = useI18n();
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const configuredTtsModel = useUserPreferencesStore((s) => {
    const key = (projectId || "").trim();
    if (!key) return null;
    return s.preferences.preferredTtsModelByProject?.[key] ?? null;
  });
  const shouldShowTtsControl =
    isAssistant && !!(configuredTtsModel && String(configuredTtsModel).trim());
  
  // 获取第一个 run（通常是 baseline run）
  const primaryRun = runs.length > 0 ? runs[0] : undefined;
  const [activeTab, setActiveTab] = useState<string>("baseline");
  const effectiveTypewriterKey =
    typewriterKey ?? `${message.conversation_id}:${message.created_at}`;
  const primaryStatus = primaryRun?.status;
  const createdMs = new Date(message.created_at).getTime();
  const isAssistantPendingResponse =
    isAssistant &&
    primaryStatus === "running" &&
    (message.content ?? "").trim().length === 0;
  const toolInvocations = primaryRun?.tool_invocations ?? [];
  const isRecent = Number.isFinite(createdMs)
    ? Date.now() - createdMs < 90_000
    : false;
  const shouldTypewriter =
    enableTypewriter &&
    isAssistant &&
    isLatestAssistant &&
    (primaryStatus === "running" || primaryStatus === "queued" || isRecent);
  // 仅在明确的 run 状态为 queued/running 时展示“运行中”标记；
  // 对于“最近消息”的 typewriter 兜底，不应误导为仍在运行。
  const isActivelyGenerating =
    isAssistant &&
    (primaryStatus === "running" ||
      primaryStatus === "queued" ||
      (!primaryStatus && isRecent && (message.content ?? "").trim().length === 0));

  const tabItems = useMemo(() => {
    if (!isAssistant) return [];
    const items: Array<{
      key: string;
      label: string;
      status?: "queued" | "running" | "succeeded" | "failed" | "canceled";
      content?: string;
      errorMessage?: string;
    }> = [];

    const baselineLabel = primaryRun?.requested_logical_model || "Baseline";
    items.push({
      key: "baseline",
      label: baselineLabel,
      status: primaryRun?.status,
      content: message.content,
    });

    for (const v of comparisonVariants) {
      items.push({
        key: v.id,
        label: v.model,
        status: v.status,
        content: v.content,
        errorMessage: v.error_message,
      });
    }

    return items;
  }, [comparisonVariants, isAssistant, message.content, primaryRun?.requested_logical_model, primaryRun?.status]);

  // 格式化时间
  const formattedTime = formatDistanceToNow(new Date(message.created_at), {
    addSuffix: true,
    locale: language === "zh" ? zhCN : enUS,
  });

  return (
    <div
      className={cn(
        "flex gap-3 group",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {/* 助手头像（在气泡外） */}
      {isAssistant && (
        <div className="flex-shrink-0 mt-1">
          <Avatar aria-label={t("chat.message.assistant")} className="size-12 ring-2 ring-white/50 shadow-lg">
            <AvatarImage
              src="/images/robot.png"
              alt={t("chat.message.assistant")}
              className="object-cover"
            />
            <AvatarFallback className="text-primary bg-primary/10">
              <Bot className="size-6" />
            </AvatarFallback>
          </Avatar>
        </div>
      )}

      {/* 消息内容 */}
      <div
        className={cn(
          "flex flex-col gap-2 max-w-[min(800px,85%)] md:max-w-[min(800px,75%)]",
          isUser && "items-end"
        )}
      >
        {/* 消息卡片 */}
        <MessageBubble role={message.role}>
          <div className="flex-1 min-w-0">
            {isAssistantPendingResponse ? (
              <div className="flex items-center gap-2.5">
                <div className="flex items-center gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="size-2 rounded-full bg-primary/60 animate-bounce"
                      style={{
                        animationDelay: `${i * 150}ms`,
                        animationDuration: '600ms',
                      }}
                    />
                  ))}
                </div>
                <span className="text-sm font-medium text-muted-foreground">
                  {t("chat.message.ai_typing")}
                </span>
              </div>
            ) : isAssistant && comparisonVariants.length > 0 ? (
              <Tabs value={activeTab} onValueChange={setActiveTab} className="gap-3">
                <TabsList className="h-8 px-1">
                  {tabItems.map((item) => (
                    <TabsTrigger
                      key={item.key}
                      value={item.key}
                      className="text-xs px-2 py-1"
                    >
                      {item.label}
                    </TabsTrigger>
                  ))}
                </TabsList>

                {tabItems.map((item) => (
                  <TabsContent key={item.key} value={item.key} className="mt-0">
                    {item.status === "running" ? (
                      <div className="text-sm text-muted-foreground">
                        {t("chat.message.add_comparison_generating")}
                      </div>
                    ) : item.status === "canceled" ? (
                      <div className="text-sm text-muted-foreground">
                        {t("chat.run.status_canceled")}
                      </div>
                    ) : item.status === "failed" ? (
                      <div className="text-sm text-destructive">
                        {item.errorMessage || t("chat.message.add_comparison_failed")}
                      </div>
                    ) : (
                      <MessageContent
                        content={item.content || ""}
                        role="assistant"
                        enableTypewriter={item.key === "baseline" && shouldTypewriter}
                        typewriterKey={effectiveTypewriterKey}
                      />
                    )}
                  </TabsContent>
                ))}
              </Tabs>
            ) : (
                <>
                  {isAssistant &&
                  isRegenerating &&
                  (message.content ?? "").trim().length === 0 ? (
                    <div className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="size-4 animate-spin" />
                      {t("chat.message.loading")}
                    </div>
                  ) : (
                    <MessageContent
                      content={message.content}
                      role={message.role}
                      enableTypewriter={shouldTypewriter}
                      typewriterKey={effectiveTypewriterKey}
                    />
                  )}
                </>
              )}
              {isAssistant && errorMessage ? (
                <Alert variant="destructive" className="mt-3">
                  <AlertCircle className="size-4" />
                  <AlertDescription className="flex items-center justify-between gap-2">
                    <span className="text-xs flex-1">{errorMessage}</span>
                    {onRegenerate && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onRegenerate(message.message_id, runSourceMessageId)}
                        className="h-7 px-2 text-xs"
                        disabled={disableActions || isRegenerating}
                      >
                        <RotateCw className="size-3 mr-1" />
                        {t("chat.action.retry")}
                      </Button>
                    )}
                  </AlertDescription>
                </Alert>
              ) : null}
              {isAssistant && primaryRun ? (
                <ToolInvocationBubbles
                  runId={primaryRun.run_id}
                  runStatus={primaryRun.status}
                  seedInvocations={toolInvocations}
                />
              ) : null}
          </div>
        </MessageBubble>

        {/* 时间和操作按钮 */}
        <div className="flex items-center gap-2 px-1">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="text-xs text-muted-foreground cursor-help">
                  {formattedTime}
                </span>
              </TooltipTrigger>
              <TooltipContent>
                <p className="text-xs">
                  {format(new Date(message.created_at), "yyyy-MM-dd HH:mm:ss")}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          {isActivelyGenerating ? (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" />
              {t("chat.run.status_running")}
            </span>
          ) : null}

          {/* 助手消息的操作按钮 */}
          {isAssistant && (
            <div className="flex items-center gap-1 opacity-60 md:group-hover:opacity-100 transition-opacity duration-200">
              {shouldShowTtsControl ? (
                <MessageTtsControl
                  messageId={message.message_id}
                  projectId={projectId}
                  fallbackModel={runs?.[0]?.requested_logical_model ?? defaultTtsModel}
                  disabled={
                    disableActions ||
                    isActivelyGenerating ||
                    isRegenerating ||
                    !(message.content ?? "").trim()
                  }
                />
              ) : null}
              {/* 重新生成 */}
              {onRegenerate && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  disabled={disableActions || isRegenerating}
                  onClick={() => onRegenerate(message.message_id, runSourceMessageId)}
                  title={t("chat.message.regenerate")}
                  aria-label={t("chat.message.regenerate")}
                >
                  {isRegenerating ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RotateCw className="size-3.5" />
                  )}
                </Button>
              )}
              {/* 删除消息 */}
              {onDeleteMessage && (
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="text-destructive hover:text-destructive hover:bg-destructive/10"
                  disabled={disableActions || isDeletingMessage}
                  onClick={onDeleteMessage}
                  title={t("chat.message.delete")}
                  aria-label={t("chat.message.delete")}
                >
                  {isDeletingMessage ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="size-3.5" />
                  )}
                </Button>
              )}

              {/* 以下操作依赖基线 run */}
              {primaryRun && (
                <>
                  {/* 查看详情按钮 */}
                  {onViewDetails && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => onViewDetails(primaryRun.run_id)}
                      title={t("chat.message.view_details")}
                    >
                      <Eye className="size-3.5" />
                    </Button>
                  )}

                  {/* 多 run 展示：弹出列表（baseline 之外的 runs） */}
                  {onViewDetails && runs.length > 1 ? (
                    <Popover>
                      <PopoverTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          title={t("chat.run.more_runs")}
                          aria-label={t("chat.run.more_runs")}
                        >
                          <Layers className="size-3.5" />
                        </Button>
                      </PopoverTrigger>
                      <PopoverContent className="w-72 p-2">
                        <div className="px-2 py-1 text-xs text-muted-foreground">
                          {t("chat.run.more_runs")}
                        </div>
                        <div className="space-y-1">
                          {runs.map((r) => (
                            <Button
                              key={r.run_id}
                              variant="ghost"
                              size="sm"
                              className="w-full justify-between"
                              onClick={() => onViewDetails(r.run_id)}
                            >
                              <span className="truncate">
                                {r.requested_logical_model}
                              </span>
                              <span className="ml-3 text-xs text-muted-foreground">
                                {t(`chat.run.status_${r.status}`)}
                              </span>
                            </Button>
                          ))}
                        </div>
                      </PopoverContent>
                    </Popover>
                  ) : null}

                  {/* 添加对比按钮 */}
                  {onAddComparison &&
                    runSourceMessageId &&
                    primaryRun.status === "succeeded" && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onAddComparison(message.message_id, runSourceMessageId)}
                        title={t("chat.message.add_comparison")}
                        aria-label={t("chat.message.add_comparison")}
                      >
                        <Plus className="size-3.5" />
                      </Button>
                    )}

                  {/* 推荐评测按钮 */}
                  {showEvalButton && onTriggerEval && primaryRun.status === "succeeded" && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() =>
                        onTriggerEval(runSourceMessageId ?? message.message_id, primaryRun.run_id)
                      }
                      title={t("chat.message.trigger_eval")}
                    >
                      <Sparkles className="size-3.5" />
                    </Button>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="flex-shrink-0 mt-1">
          <Avatar aria-label={userDisplayName || t("chat.message.user")} className="size-10">
            {userAvatarUrl ? (
              <AvatarImage src={userAvatarUrl} alt={userDisplayName || t("chat.message.user")} />
            ) : null}
            <AvatarFallback className="text-muted-foreground">
              <User className="size-5" />
            </AvatarFallback>
          </Avatar>
        </div>
      )}
    </div>
  );
}
