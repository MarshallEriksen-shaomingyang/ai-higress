"use client";

import { useState, useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Send, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";
import { useSendMessage } from "@/lib/swr/use-messages";
import type { Message } from "@/lib/api-types";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/lib/stores/chat-store";

const EMPTY_STRING_ARRAY: string[] = [];

// 表单验证 schema
const messageSchema = z.object({
  content: z.string().min(1, "chat.message.input_placeholder"),
});

type MessageFormData = z.infer<typeof messageSchema>;

export interface MessageInputProps {
  conversationId: string;
  assistantId?: string;
  overrideLogicalModel?: string | null;
  disabled?: boolean;
  onMessageSent?: (message: Message) => void;
  className?: string;
  layout?: "auto" | "fill";
}

export function MessageInput({
  conversationId,
  assistantId,
  overrideLogicalModel,
  disabled = false,
  onMessageSent,
  className,
  layout = "auto",
}: MessageInputProps) {
  const { t } = useI18n();
  const [isSending, setIsSending] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const sendMessage = useSendMessage(conversationId, assistantId, overrideLogicalModel);
  const bridgeAgentIds =
    useChatStore((s) => s.conversationBridgeAgentIds[conversationId]) ??
    EMPTY_STRING_ARRAY;

  // 表单管理
  const {
    register,
    handleSubmit,
    reset,
    watch,
    formState: { errors },
  } = useForm<MessageFormData>({
    resolver: zodResolver(messageSchema),
    defaultValues: {
      content: "",
    },
  });

  const content = watch("content");
  const isFillLayout = layout === "fill";

  const contentField = register("content", {
    onChange: () => {
      if (isFillLayout) return;

      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
      }
    },
  });

  // 发送消息
  const onSubmit = async (data: MessageFormData) => {
    // 阻止在归档会话中发送消息
    if (disabled) {
      return;
    }

    if (isSending) return;

    setIsSending(true);

    try {
      const response = await sendMessage({
        content: data.content.trim(),
        bridge_agent_ids: bridgeAgentIds.length ? bridgeAgentIds : undefined,
      });

      // 清空输入框
      reset();

      // 重置 textarea 高度
      if (!isFillLayout && textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }

      if (onMessageSent && response.message_id) {
        // 注意：这里我们只有 message_id，实际的 message 对象会通过 SWR 自动更新
      }
    } catch (error: any) {
      console.error("Failed to send message:", error);
      // 错误信息会作为聊天气泡展示，避免使用 toast
    } finally {
      setIsSending(false);
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl/Cmd + Enter 发送消息
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit(onSubmit)();
    }
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className={cn(
        "flex items-end gap-2 p-4 border-t bg-background",
        isFillLayout && "h-full",
        className
      )}
      role="form"
      aria-label={t("chat.message.input_form")}
    >
      {/* 输入框 */}
      <div className={cn("flex-1 relative", isFillLayout && "h-full")}>
        <textarea
          {...contentField}
          ref={(e) => {
            contentField.ref(e);
            textareaRef.current = e;
          }}
          placeholder={disabled ? t("chat.conversation.archived_notice") : t("chat.message.input_placeholder")}
          disabled={disabled || isSending}
          onKeyDown={handleKeyDown}
          rows={1}
          aria-label={t("chat.message.input_label")}
          aria-describedby={disabled ? "archived-notice" : undefined}
          aria-invalid={!!errors.content}
          className={cn(
            "w-full resize-none rounded-md border bg-background px-3 py-2 text-sm",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
            isFillLayout ? "h-full max-h-none overflow-y-auto" : "max-h-32 overflow-y-auto",
            errors.content && "border-destructive"
          )}
        />
      </div>

      {/* 发送按钮 */}
      <Button
        type="submit"
        size="icon"
        disabled={disabled || isSending || !content.trim()}
        aria-label={isSending ? t("chat.message.sending") : t("chat.message.send")}
        title={t("chat.message.send_hint")}
        className={cn(isFillLayout && "self-end")}
      >
        {isSending ? (
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        ) : (
          <Send className="size-4" aria-hidden="true" />
        )}
        <span className="sr-only">
          {isSending ? t("chat.message.sending") : t("chat.message.send")}
        </span>
      </Button>
    </form>
  );
}
