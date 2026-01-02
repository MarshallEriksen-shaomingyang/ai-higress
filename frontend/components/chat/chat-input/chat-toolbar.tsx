"use client";

import {
  Send,
  Loader2,
  Image as ImageIcon,
  MessageSquare,
  SlidersHorizontal,
  Mic,
  Volume2,
  ChevronDown,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ClearHistoryAction } from "@/components/chat/chat-input/clear-history-action";
import { ImageUploadAction } from "@/components/chat/chat-input/image-attachments";
import { ModelParametersPopover } from "@/components/chat/chat-input/model-parameters-popover";
import { McpSelector } from "@/components/chat/chat-input/mcp-selector";
import { useI18n } from "@/lib/i18n-context";
import type { ModelParameters } from "@/components/chat/chat-input/types";
import { composerModeLabelKeys, composerModes } from "@/lib/chat/composer-modes";
import type { ComposerMode } from "@/lib/chat/composer-modes";
import { cn } from "@/lib/utils";

export type { ComposerMode } from "@/lib/chat/composer-modes";

interface ChatToolbarProps {
  mode?: ComposerMode;
  onModeChange?: (mode: ComposerMode) => void;
  conversationId: string;
  disabled: boolean;
  isSending: boolean;
  isClearing: boolean;
  clearDialogOpen: boolean;
  onClearDialogOpenChange: (open: boolean) => void;
  onClearHistory?: () => void;
  onSend: () => void;
  sendHint: string;
  parameters: ModelParameters;
  onParametersChange: (params: ModelParameters) => void;
  onResetParameters: () => void;
  onFilesSelected: (files: FileList | null) => Promise<void>;
  hideModeSwitcher?: boolean;
  onOpenImageSettings?: () => void;
  onOpenAudioSettings?: () => void;
  onOpenVoiceSelector?: () => void;
}

export function ChatToolbar({
  mode = "chat",
  onModeChange,
  conversationId,
  disabled,
  isSending,
  isClearing,
  clearDialogOpen,
  onClearDialogOpenChange,
  onClearHistory,
  onSend,
  sendHint,
  parameters,
  onParametersChange,
  onResetParameters,
  onFilesSelected,
  hideModeSwitcher = false,
  onOpenImageSettings,
  onOpenAudioSettings,
  onOpenVoiceSelector,
}: ChatToolbarProps) {
  const { t } = useI18n();
  const modeIcons: Record<ComposerMode, typeof MessageSquare> = {
    chat: MessageSquare,
    image: ImageIcon,
    speech: Volume2,
  };

  // 当前模式的颜色配置
  const modeColors: Record<ComposerMode, string> = {
    chat: "text-blue-600 dark:text-blue-400",
    image: "text-purple-600 dark:text-purple-400",
    speech: "text-emerald-600 dark:text-emerald-400",
  };

  const CurrentModeIcon = modeIcons[mode];

  return (
    <div className="flex items-center justify-between px-2 py-2 border-t bg-muted/30">
      <div className="flex items-center gap-1">
        {/* Mode Switcher with Current Mode Indicator */}
        {!hideModeSwitcher && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled || isSending}
                title={t("chat.image_gen.switch_mode")}
                className="h-7 gap-1.5 px-2"
              >
                <CurrentModeIcon className={cn("size-4", modeColors[mode])} />
                <span className={cn("text-xs font-medium", modeColors[mode])}>
                  {t(composerModeLabelKeys[mode])}
                </span>
                <ChevronDown className="size-3 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {composerModes.map((m) => {
                const Icon = modeIcons[m];
                const isActive = m === mode;
                return (
                  <DropdownMenuItem
                    key={m}
                    onClick={() => onModeChange?.(m)}
                    className={cn(isActive && "bg-accent")}
                  >
                    <Icon className={cn("size-4 mr-2", isActive && modeColors[m])} />
                    <span className={cn(isActive && "font-medium")}>
                      {t(composerModeLabelKeys[m])}
                    </span>
                  </DropdownMenuItem>
                );
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        )}

        <ImageUploadAction
          disabled={disabled || isSending || mode === "image"}
          onFilesSelected={onFilesSelected}
          uploadLabel={t("chat.message.upload_image")}
        />

        {mode === "chat" && onOpenAudioSettings ? (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onOpenAudioSettings}
            disabled={disabled || isSending}
            title={t("chat.message.upload_audio")}
            aria-label={t("chat.message.upload_audio")}
          >
            <Mic className="size-4" />
          </Button>
        ) : null}

        {mode === "chat" ? (
          <ModelParametersPopover
            disabled={disabled || isSending}
            parameters={parameters}
            onParametersChange={onParametersChange}
            onReset={onResetParameters}
            title={t("chat.message.model_parameters")}
            resetLabel={t("chat.message.reset_parameters")}
            labels={{
              temperature: t("chat.message.parameter_temperature"),
              top_p: t("chat.message.parameter_top_p"),
              frequency_penalty: t("chat.message.parameter_frequency_penalty"),
              presence_penalty: t("chat.message.parameter_presence_penalty"),
            }}
          />
        ) : null}

        <McpSelector conversationId={conversationId} disabled={disabled} isSending={isSending} />

        {mode === "image" && onOpenImageSettings ? (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onOpenImageSettings}
            disabled={disabled || isSending}
            title={t("chat.image_gen.params")}
            aria-label={t("chat.image_gen.params")}
          >
            <SlidersHorizontal className="size-4" />
          </Button>
        ) : null}

        {mode === "speech" && onOpenVoiceSelector ? (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onOpenVoiceSelector}
            disabled={disabled || isSending}
            title={t("chat.voice_selector.settings")}
            aria-label={t("chat.voice_selector.settings")}
          >
            <SlidersHorizontal className="size-4" />
          </Button>
        ) : null}

        {onClearHistory ? (
          <ClearHistoryAction
            disabled={disabled || isSending}
            isBusy={isClearing}
            onConfirm={() => void onClearHistory()}
            title={t("chat.message.clear_history")}
            description={t("chat.message.clear_history_confirm")}
            confirmText={t("chat.action.confirm")}
            cancelText={t("chat.action.cancel")}
            tooltip={t("chat.message.clear_history")}
            open={clearDialogOpen}
            onOpenChange={onClearDialogOpenChange}
          />
        ) : null}
      </div>

      <div className="flex items-center gap-1.5 md:gap-2">
        {isSending ? (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="size-3 animate-spin" />
            <span className="hidden sm:inline">{t("chat.message.sending")}</span>
          </div>
        ) : null}

        <Button
          type="button"
          size="icon-sm"
          onClick={onSend}
          disabled={disabled || isSending}
          aria-label={isSending ? t("chat.message.sending") : t("chat.message.send")}
          title={sendHint}
        >
          {isSending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
        </Button>
      </div>
    </div>
  );
}
