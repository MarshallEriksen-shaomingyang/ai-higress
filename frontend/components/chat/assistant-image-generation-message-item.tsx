"use client";

import { formatDistanceToNow } from "date-fns";
import { zhCN, enUS } from "date-fns/locale";
import { Bot } from "lucide-react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import { ImageGenerationItem } from "@/components/chat/image-generation-item";
import type { Message } from "@/lib/api-types";
import type { ImageGenerationTask } from "@/lib/chat/composer-tasks";

export function AssistantImageGenerationMessageItem({
  message,
}: {
  message: Message;
}) {
  const { t, language } = useI18n();
  const img = message.image_generation;
  if (!img) return null;

  const createdAtMs = new Date(message.created_at).getTime();
  const formattedTime = formatDistanceToNow(new Date(message.created_at), {
    addSuffix: true,
    locale: language === "zh" ? zhCN : enUS,
  });

  const task: ImageGenerationTask = {
    id: message.message_id,
    conversationId: message.conversation_id,
    kind: "image_generation",
    status:
      img.status === "failed"
        ? "failed"
        : img.status === "succeeded"
          ? "success"
          : "pending",
    prompt: img.prompt,
    params: img.params,
    createdAt: Number.isFinite(createdAtMs) ? createdAtMs : Date.now(),
    ...(img.status === "failed" ? { error: img.error } : {}),
    ...(img.status === "succeeded"
      ? {
          result: {
            created:
              typeof img.created === "number"
                ? img.created
                : Math.floor((Number.isFinite(createdAtMs) ? createdAtMs : Date.now()) / 1000),
            data: (img.images || []).map((it) => ({
              url: it.url,
              b64_json: it.b64_json,
              revised_prompt: it.revised_prompt ?? undefined,
            })),
          },
        }
      : {}),
  };

  return (
    <div className={cn("flex gap-3 group justify-start")}>
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

      <div className={cn("flex flex-col gap-2 max-w-[80%]")}>
        <div className="min-w-0">
          <ImageGenerationItem task={task} />
        </div>
        <div className="flex items-center gap-2 px-1">
          <span className="text-xs text-muted-foreground">{formattedTime}</span>
        </div>
      </div>
    </div>
  );
}
