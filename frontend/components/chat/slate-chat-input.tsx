"use client";

import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import { createEditor, Descendant, Editor, Transforms, Element as SlateElement } from "slate";
import { Slate, Editable, withReact, ReactEditor } from "slate-react";
import { withHistory } from "slate-history";
import { useSize, useDebounceFn } from "ahooks";
import { 
  Send, 
  Zap,
  Loader2 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { ClearHistoryAction } from "./chat-input/clear-history-action";
import { ImagePreviewGrid, ImageUploadAction } from "./chat-input/image-attachments";
import { ModelParametersPopover, type ModelParameterEnabled } from "./chat-input/model-parameters-popover";
import { buildModelPreset } from "./chat-input/model-preset";
import { encodeImageFileToCompactDataUrl } from "./chat-input/image-encoding";
import { composeMessageContent, isMessageTooLong } from "./chat-input/message-content";
import {
  DEFAULT_MODEL_PARAMETERS,
  type ModelParameters,
} from "./chat-input/types";

export type { ModelParameters } from "./chat-input/types";

// Slate 类型定义
type CustomElement = 
  | { type: "paragraph"; children: CustomText[] }
  | { type: "image"; url: string; children: CustomText[] };

type CustomText = { text: string };

declare module "slate" {
  interface CustomTypes {
    Editor: ReactEditor;
    Element: CustomElement;
    Text: CustomText;
  }
}

const IMAGE_DATA_URL_MAX_CHARS = 9000;
const MAX_IMAGES = 3;

export interface SlateChatInputProps {
  conversationId: string;
  assistantId?: string;
  disabled?: boolean;
  onSend?:
    | ((
        content: string,
        images: string[],
        parameters: ModelParameters
      ) => Promise<void>)
    | ((
        payload: {
          content: string;
          images: string[];
          model_preset?: Record<string, number>;
          parameters: ModelParameters;
        }
      ) => Promise<void>);
  onClearHistory?: () => Promise<void>;
  onMcpAction?: () => void;
  className?: string;
  defaultParameters?: Partial<ModelParameters>;
}

export function SlateChatInput({
  conversationId,
  disabled = false,
  onSend,
  onClearHistory,
  onMcpAction,
  className,
  defaultParameters = {},
}: SlateChatInputProps) {
  const { t } = useI18n();
  const [editor] = useState(() => withHistory(withReact(createEditor())));
  const [isSending, setIsSending] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [images, setImages] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  
  // 监听容器大小变化
  const containerSize = useSize(containerRef);
  
  // 模型参数状态
  const [parameters, setParameters] = useState<ModelParameters>({
    ...DEFAULT_MODEL_PARAMETERS,
    ...defaultParameters,
  });
  const [paramEnabled, setParamEnabled] = useState<ModelParameterEnabled>({
    temperature: false,
    top_p: false,
    frequency_penalty: false,
    presence_penalty: false,
  });

  // 初始化编辑器内容
  const initialValue: Descendant[] = useMemo(
    () => [
      {
        type: "paragraph",
        children: [{ text: "" }],
      },
    ],
    []
  );

  // 防抖调整编辑器高度
  const { run: adjustEditorHeight } = useDebounceFn(
    () => {
      if (!editorRef.current || !containerSize) return;
      
      // 计算可用高度：容器高度 - 工具栏高度(约44px) - padding
      const toolbarHeight = 44;
      const padding = 32; // 上下 padding
      const availableHeight = (containerSize.height || 0) - toolbarHeight - padding;
      
      // 设置最小高度为3行（约72px），最大为可用高度
      const minHeight = 72;
      const maxHeight = Math.max(minHeight, availableHeight);
      
      editorRef.current.style.minHeight = `${minHeight}px`;
      editorRef.current.style.maxHeight = `${maxHeight}px`;
    },
    { wait: 150 }
  );

  // 当容器大小变化时调整编辑器高度
  useEffect(() => {
    adjustEditorHeight();
  }, [containerSize, adjustEditorHeight]);

  // 获取纯文本内容
  const getTextContent = useCallback(() => {
    return editor.children
      .map((n) => SlateElement.isElement(n) ? Editor.string(editor, [editor.children.indexOf(n)]) : "")
      .join("\n")
      .trim();
  }, [editor]);

  // 清空编辑器
  const clearEditor = useCallback(() => {
    Transforms.delete(editor, {
      at: {
        anchor: Editor.start(editor, []),
        focus: Editor.end(editor, []),
      },
    });
    Transforms.insertNodes(editor, {
      type: "paragraph",
      children: [{ text: "" }],
    });
  }, [editor]);

  const handleFilesSelected = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;

      const queued = Array.from(files);
      const baseImages = images;
      const remainingSlots = Math.max(0, MAX_IMAGES - baseImages.length);
      const toProcess = queued.slice(0, remainingSlots);
      if (toProcess.length < queued.length) {
        toast.error(t("chat.errors.too_many_images"));
      }

      const nextImages: string[] = [...baseImages];

      for (const file of toProcess) {
        if (!file.type.startsWith("image/")) {
          toast.error(t("chat.errors.invalid_file_type"));
          continue;
        }

        try {
          const encoded = await encodeImageFileToCompactDataUrl(file, {
            maxChars: IMAGE_DATA_URL_MAX_CHARS,
          });
          if (!encoded || encoded.length > IMAGE_DATA_URL_MAX_CHARS) {
            toast.error(t("chat.errors.image_too_large"));
            continue;
          }
          const proposed = composeMessageContent(getTextContent(), [...nextImages, encoded]);
          if (isMessageTooLong(proposed)) {
            toast.error(t("chat.errors.message_too_long"));
            continue;
          }
          nextImages.push(encoded);
        } catch (err) {
          console.error("Failed to encode image:", err);
          toast.error(t("chat.errors.image_too_large"));
        }
      }

      if (nextImages.length !== baseImages.length) {
        setImages(nextImages);
      }
    },
    [images, t, getTextContent]
  );

  // 移除图片
  const removeImage = useCallback((index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // 发送消息
  const handleSend = useCallback(async () => {
    const content = getTextContent();
    
    if (!content && images.length === 0) {
      toast.error(t("chat.message.input_placeholder"));
      return;
    }

    if (disabled) {
      toast.error(t("chat.conversation.archived_notice"));
      return;
    }

    setIsSending(true);

    try {
      const composed = composeMessageContent(content, images);
      if (!composed) {
        toast.error(t("chat.message.input_placeholder"));
        return;
      }
      if (isMessageTooLong(composed)) {
        toast.error(t("chat.errors.message_too_long"));
        return;
      }

      const model_preset = buildModelPreset(paramEnabled, parameters);
      if (onSend) {
        if (onSend.length <= 1) {
          await (onSend as any)({
            content: composed,
            images,
            model_preset,
            parameters,
          });
        } else {
          await (onSend as any)(composed, images, parameters);
        }
      }
      
      // 清空编辑器和图片
      clearEditor();
      setImages([]);
      
      toast.success(t("chat.message.sent"));
    } catch (error) {
      console.error("Failed to send message:", error);
      toast.error(t("chat.message.failed"));
    } finally {
      setIsSending(false);
    }
  }, [getTextContent, images, disabled, onSend, parameters, clearEditor, t, paramEnabled]);

  // 清空历史记录
  const handleClearHistory = useCallback(async () => {
    if (!onClearHistory) return;

    try {
      setIsClearing(true);
      await onClearHistory();
      toast.success(t("chat.message.clear_history_success"));
    } catch (error) {
      console.error("Failed to clear history:", error);
      toast.error(t("chat.message.clear_history_failed"));
    } finally {
      setIsClearing(false);
      setClearDialogOpen(false);
    }
  }, [onClearHistory, t]);

  // 键盘快捷键
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  return (
    <div 
      ref={containerRef}
      className={cn("flex flex-col gap-3 p-4 border-t bg-background h-full", className)}
    >
      <ImagePreviewGrid
        images={images}
        disabled={disabled || isSending}
        onRemoveImage={removeImage}
        uploadedAltPrefix={t("chat.message.uploaded_image")}
        removeLabel={t("chat.message.remove_image")}
      />

      {/* 输入框容器 - 包含编辑器和工具栏 */}
      <div className="relative flex flex-col border rounded-md bg-background focus-within:ring-2 focus-within:ring-ring flex-1">
        {/* 编辑器区域 */}
        <div 
          ref={editorRef}
          className="flex-1 px-3 pt-3 pb-2 overflow-y-auto"
        >
          <Slate editor={editor} initialValue={initialValue}>
            <Editable
              placeholder={disabled ? t("chat.conversation.archived_notice") : t("chat.message.input_placeholder")}
              readOnly={disabled || isSending}
              aria-disabled={disabled || isSending}
              onKeyDown={handleKeyDown}
              className={cn(
                "w-full h-full resize-none text-sm outline-none",
                "placeholder:text-muted-foreground",
                (disabled || isSending) && "cursor-not-allowed opacity-50"
              )}
            />
          </Slate>
        </div>

        {/* 工具栏 - 在输入框底部 */}
        <div className="flex items-center justify-between px-2 py-2 border-t bg-muted/30">
          <TooltipProvider>
            <div className="flex items-center gap-1">
              <ImageUploadAction
                disabled={disabled || isSending}
                onFilesSelected={handleFilesSelected}
                uploadLabel={t("chat.message.upload_image")}
              />

              <ModelParametersPopover
                idPrefix={`chat-${conversationId}`}
                disabled={disabled || isSending}
                enabled={paramEnabled}
                parameters={parameters}
                onEnabledChange={setParamEnabled}
                onParametersChange={setParameters}
                onReset={() => {
                  setParameters({ ...DEFAULT_MODEL_PARAMETERS, ...defaultParameters });
                  setParamEnabled({
                    temperature: false,
                    top_p: false,
                    frequency_penalty: false,
                    presence_penalty: false,
                  });
                }}
                title={t("chat.message.model_parameters")}
                resetLabel={t("chat.message.reset_parameters")}
                labels={{
                  temperature: t("chat.message.parameter_temperature"),
                  top_p: t("chat.message.parameter_top_p"),
                  frequency_penalty: t("chat.message.parameter_frequency_penalty"),
                  presence_penalty: t("chat.message.parameter_presence_penalty"),
                }}
              />

              {/* MCP 按钮 */}
              {onMcpAction && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      onClick={onMcpAction}
                      disabled={disabled || isSending}
                    >
                      <Zap className="size-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{t("chat.message.mcp_tools")}</p>
                  </TooltipContent>
                </Tooltip>
              )}

              {/* 清空历史 */}
              {onClearHistory ? (
                <ClearHistoryAction
                  disabled={disabled || isSending}
                  isBusy={isClearing}
                  onConfirm={() => void handleClearHistory()}
                  title={t("chat.message.clear_history")}
                  description={t("chat.message.clear_history_confirm")}
                  confirmText={t("chat.action.confirm")}
                  cancelText={t("chat.action.cancel")}
                  tooltip={t("chat.message.clear_history")}
                  open={clearDialogOpen}
                  onOpenChange={setClearDialogOpen}
                />
              ) : null}
            </div>

            {/* 右侧：发送按钮 */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon-sm"
                  onClick={handleSend}
                  disabled={disabled || isSending}
                  aria-label={isSending ? t("chat.message.sending") : t("chat.message.send")}
                >
                  {isSending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Send className="size-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{t("chat.message.send_hint")}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      <div className="text-xs text-muted-foreground text-center">
        {t("chat.message.send_hint")}
      </div>
    </div>
  );
}
