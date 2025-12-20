"use client";

import { formatDistanceToNow } from "date-fns";
import { zhCN, enUS } from "date-fns/locale";
import { User, Bot, Eye, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useI18n } from "@/lib/i18n-context";
import type { Message, RunSummary } from "@/lib/api-types";
import { cn } from "@/lib/utils";
import { MessageContent } from "./message-content";
import { AdaptiveCard } from "@/components/cards/adaptive-card";

export interface MessageItemProps {
  message: Message;
  runs?: RunSummary[]; // 改为 runs 数组
  runSourceMessageId?: string; // runs 所属的 user message_id（用于创建 eval）
  userAvatarUrl?: string | null;
  userDisplayName?: string | null;
  onViewDetails?: (runId: string) => void;
  onTriggerEval?: (messageId: string, runId: string) => void; // 添加 messageId 参数
  showEvalButton?: boolean;
}

export function MessageItem({
  message,
  runs = [], // 默认为空数组
  runSourceMessageId,
  userAvatarUrl,
  userDisplayName,
  onViewDetails,
  onTriggerEval,
  showEvalButton = true,
}: MessageItemProps) {
  const { t, language } = useI18n();
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  
  // 获取第一个 run（通常是 baseline run）
  const primaryRun = runs.length > 0 ? runs[0] : undefined;

  // 格式化时间
  const formattedTime = formatDistanceToNow(new Date(message.created_at), {
    addSuffix: true,
    locale: language === "zh" ? zhCN : enUS,
  });

  // 获取状态显示
  const getStatusBadge = (run: RunSummary) => {
    const statusConfig = {
      queued: {
        label: t("chat.run.status_queued"),
        className: "bg-muted text-muted-foreground",
      },
      running: {
        label: t("chat.run.status_running"),
        className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
      },
      succeeded: {
        label: t("chat.run.status_succeeded"),
        className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      },
      failed: {
        label: t("chat.run.status_failed"),
        className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      },
    };

    const config = statusConfig[run.status];
    if (!config) return null;

    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
          config.className
        )}
      >
        {config.label}
      </span>
    );
  };

  return (
    <div
      className={cn(
        "flex gap-3 group",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {/* 助手头像 */}
      {isAssistant && (
        <div className="flex-shrink-0 mt-1">
          <div className="flex size-8 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Bot className="size-4" />
          </div>
        </div>
      )}

      {/* 消息内容 */}
      <div className={cn("flex flex-col gap-2 max-w-[80%]", isUser && "items-end")}>
        {/* 消息卡片 */}
        <AdaptiveCard
          showDecor={false}
          variant="plain"
          hoverScale={false}
          className={cn(
            "py-0 gap-0 shadow-sm",
            isUser ? "bg-primary text-primary-foreground border-0" : "bg-card"
          )}
        >
          <CardContent className="py-3 px-4">
            <MessageContent content={message.content} role={message.role} />

            {/* Run 摘要信息 */}
            {isAssistant && (
              <>
                {runs.length === 0 ? (
                  <div className="mt-3 pt-3 border-t border-border/50 text-xs text-muted-foreground">
                    {t("chat.message.no_response")}
                  </div>
                ) : (
                  <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
                    {runs.map((run, index) => (
                      <div key={run.run_id} className="flex items-center gap-2 text-xs text-muted-foreground">
                        {runs.length > 1 && (
                          <span className="font-medium text-muted-foreground/70">
                            #{index + 1}
                          </span>
                        )}
                        <span className="font-medium">{run.requested_logical_model}</span>
                        {getStatusBadge(run)}
                        {run.latency && (
                          <span>
                            {run.latency}ms
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </AdaptiveCard>

        {/* 时间和操作按钮 */}
        <div className="flex items-center gap-2 px-1">
          <span className="text-xs text-muted-foreground">
            {formattedTime}
          </span>

          {/* 助手消息的操作按钮 */}
          {isAssistant && primaryRun && (
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
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
            </div>
          )}
        </div>
      </div>

      {/* 用户头像 */}
      {isUser && (
        <div className="flex-shrink-0 mt-1">
          <Avatar aria-label={userDisplayName || t("chat.message.user")}>
            {userAvatarUrl ? (
              <AvatarImage src={userAvatarUrl} alt={userDisplayName || t("chat.message.user")} />
            ) : null}
            <AvatarFallback className="text-muted-foreground">
              <User className="size-4" />
            </AvatarFallback>
          </Avatar>
        </div>
      )}
    </div>
  );
}
