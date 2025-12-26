"use client";

import { formatDistanceToNow } from "date-fns";
import { zhCN, enUS } from "date-fns/locale";
import { User, Bot } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { MessageBubble } from "./message-bubble";
import { ImageGenerationItem } from "./image-generation-item";
import { useI18n } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";
import type { ImageGenTask } from "@/lib/stores/image-generation-store";
import type { UserInfo } from "@/lib/api-types";

interface ImageGenerationMessageItemProps {
  role: "user" | "assistant";
  task: ImageGenTask;
  user?: UserInfo | null;
}

export function ImageGenerationMessageItem({ role, task, user }: ImageGenerationMessageItemProps) {
  const { t, language } = useI18n();
  const isUser = role === "user";
  const isAssistant = role === "assistant";

  // Formatted time
  const formattedTime = formatDistanceToNow(new Date(task.createdAt), {
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
      {/* Assistant Avatar */}
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

      {/* Content */}
      <div className={cn("flex flex-col gap-2 max-w-[80%]", isUser && "items-end")}>
        {isUser ? (
          <MessageBubble role="user">
            <div className="whitespace-pre-wrap break-words">{task.prompt}</div>
          </MessageBubble>
        ) : (
          <div className="min-w-0">
             {/* We don't use MessageBubble for assistant image card to avoid double padding/border 
                 or we can use it if we want consistent background. 
                 Let's try direct ImageGenerationItem first. */}
             <ImageGenerationItem task={task} />
          </div>
        )}

        {/* Time */}
        <div className="flex items-center gap-2 px-1">
          <span className="text-xs text-muted-foreground">
            {formattedTime}
          </span>
        </div>
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex-shrink-0 mt-1">
          <Avatar aria-label={user?.display_name || t("chat.message.user")} className="size-10">
            {user?.avatar ? (
              <AvatarImage src={user.avatar} alt={user.display_name || t("chat.message.user")} />
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
