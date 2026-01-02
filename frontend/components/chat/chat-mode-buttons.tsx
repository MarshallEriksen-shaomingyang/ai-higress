"use client";

import { Image as ImageIcon, MessageSquare, Volume2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import {
  composerModeLabelKeys,
  composerModes,
  type ComposerMode,
} from "@/lib/chat/composer-modes";

export function ChatModeButtons({
  mode,
  onModeChange,
  disabled = false,
  className,
}: {
  mode: ComposerMode;
  onModeChange: (mode: ComposerMode) => void;
  disabled?: boolean;
  className?: string;
}) {
  const { t } = useI18n();
  const icons: Record<ComposerMode, typeof MessageSquare> = {
    chat: MessageSquare,
    image: ImageIcon,
    speech: Volume2,
  };

  return (
    <div className={cn("flex items-center justify-center gap-2", className)}>
      {composerModes.map((m) => {
        const Icon = icons[m];
        return (
          <Button
            key={m}
            type="button"
            variant={mode === m ? "default" : "outline"}
            size="sm"
            disabled={disabled}
            onClick={() => onModeChange(m)}
            className={cn("rounded-full transition-all h-8", mode === m && "shadow-md")}
          >
            <Icon className="h-3.5 w-3.5 mr-1.5" />
            {t(composerModeLabelKeys[m])}
          </Button>
        );
      })}
    </div>
  );
}
