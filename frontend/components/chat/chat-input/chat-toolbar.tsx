"use client";

import { Send, Loader2, Plus, Image as ImageIcon, MessageSquare } from "lucide-react";

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

export type ComposerMode = "chat" | "image";

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
}: ChatToolbarProps) {
  const { t } = useI18n();

  return (
    <div className="flex items-center justify-between px-2 py-2 border-t bg-muted/30">
      <div className="flex items-center gap-1">
        {/* Mode Switcher */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon-sm" disabled={disabled || isSending} title="Switch Mode">
              <Plus className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            <DropdownMenuItem onClick={() => onModeChange?.("chat")}>
              <MessageSquare className="size-4 mr-2" />
              {t("chat.image_gen.mode_chat")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onModeChange?.("image")}>
              <ImageIcon className="size-4 mr-2" />
              {t("chat.image_gen.mode_image")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <ImageUploadAction
          disabled={disabled || isSending || mode === "image"}
          onFilesSelected={onFilesSelected}
          uploadLabel={t("chat.message.upload_image")}
        />

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

        <McpSelector conversationId={conversationId} disabled={disabled} isSending={isSending} />

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

      <div className="flex items-center gap-2">
        {isSending ? (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Loader2 className="size-3 animate-spin" />
            <span>{t("chat.message.sending")}</span>
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
