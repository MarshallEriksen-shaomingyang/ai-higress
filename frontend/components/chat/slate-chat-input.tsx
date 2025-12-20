"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import { createEditor, Descendant, Editor, Transforms, Element as SlateElement } from "slate";
import { Slate, Editable, withReact, ReactEditor } from "slate-react";
import { withHistory } from "slate-history";
import { 
  Send, 
  Image as ImageIcon, 
  Trash2, 
  Settings2,
  Zap,
  Loader2 
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n-context";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

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

// 模型参数接口
export interface ModelParameters {
  temperature: number;
  top_p: number;
  frequency_penalty: number;
  presence_penalty: number;
  max_tokens?: number;
}

export interface SlateChatInputProps {
  conversationId: string;
  assistantId?: string;
  disabled?: boolean;
  onSend?: (content: string, images: string[], parameters: ModelParameters) => Promise<void>;
  onClearHistory?: () => Promise<void>;
  onMcpAction?: () => void;
  className?: string;
  defaultParameters?: Partial<ModelParameters>;
}

const DEFAULT_PARAMETERS: ModelParameters = {
  temperature: 1.0,
  top_p: 1.0,
  frequency_penalty: 0.0,
  presence_penalty: 0.0,
};

export function SlateChatInput({
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
  const [images, setImages] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // 模型参数状态
  const [parameters, setParameters] = useState<ModelParameters>({
    ...DEFAULT_PARAMETERS,
    ...defaultParameters,
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

  // 处理图片上传
  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      if (!file.type.startsWith("image/")) {
        toast.error(t("chat.errors.invalid_file_type"));
        return;
      }

      const reader = new FileReader();
      reader.onload = (event) => {
        const url = event.target?.result as string;
        setImages((prev) => [...prev, url]);
      };
      reader.readAsDataURL(file);
    });

    // 重置 input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, [t]);

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
      await onSend?.(content, images, parameters);
      
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
  }, [getTextContent, images, disabled, onSend, parameters, clearEditor, t]);

  // 清空历史记录
  const handleClearHistory = useCallback(async () => {
    if (!onClearHistory) return;

    try {
      await onClearHistory();
      toast.success(t("chat.message.clear_history_success"));
    } catch (error) {
      console.error("Failed to clear history:", error);
      toast.error(t("chat.message.clear_history_failed"));
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
    <div className={cn("flex flex-col gap-3 p-4 border-t bg-background", className)}>
      {/* 图片预览区 */}
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {images.map((url, index) => (
            <div key={index} className="relative group">
              <img
                src={url}
                alt={`${t("chat.message.uploaded_image")} ${index + 1}`}
                className="w-20 h-20 object-cover rounded-md border"
              />
              <button
                type="button"
                onClick={() => removeImage(index)}
                className="absolute -top-2 -right-2 p-1 bg-destructive text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                aria-label={t("chat.message.remove_image")}
              >
                <Trash2 className="size-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 编辑器区域 */}
      <div className="flex items-end gap-2">
        <div className="flex-1 relative">
          <Slate editor={editor} initialValue={initialValue}>
            <Editable
              placeholder={disabled ? t("chat.conversation.archived_notice") : t("chat.message.input_placeholder")}
              disabled={disabled || isSending}
              onKeyDown={handleKeyDown}
              className={cn(
                "min-h-[80px] max-h-[200px] overflow-y-auto",
                "w-full resize-none rounded-md border bg-background px-3 py-2 text-sm",
                "placeholder:text-muted-foreground",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                "disabled:cursor-not-allowed disabled:opacity-50"
              )}
            />
          </Slate>
        </div>

        {/* 操作按钮组 */}
        <TooltipProvider>
          <div className="flex items-center gap-1">
            {/* 图片上传 */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={handleImageUpload}
              className="hidden"
              disabled={disabled || isSending}
            />
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={disabled || isSending}
                >
                  <ImageIcon className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{t("chat.message.upload_image")}</p>
              </TooltipContent>
            </Tooltip>

            {/* 模型参数设置 */}
            <Popover>
              <Tooltip>
                <TooltipTrigger asChild>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      disabled={disabled || isSending}
                    >
                      <Settings2 className="size-4" />
                    </Button>
                  </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t("chat.message.model_parameters")}</p>
                </TooltipContent>
              </Tooltip>
              <PopoverContent className="w-80" align="end">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">{t("chat.message.parameter_temperature")}</Label>
                      <span className="text-xs text-muted-foreground">{parameters.temperature.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[parameters.temperature]}
                      onValueChange={([value]) => setParameters((p) => ({ ...p, temperature: value ?? 1.0 }))}
                      min={0}
                      max={2}
                      step={0.1}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">{t("chat.message.parameter_top_p")}</Label>
                      <span className="text-xs text-muted-foreground">{parameters.top_p.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[parameters.top_p]}
                      onValueChange={([value]) => setParameters((p) => ({ ...p, top_p: value ?? 1.0 }))}
                      min={0}
                      max={1}
                      step={0.1}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">{t("chat.message.parameter_frequency_penalty")}</Label>
                      <span className="text-xs text-muted-foreground">{parameters.frequency_penalty.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[parameters.frequency_penalty]}
                      onValueChange={([value]) => setParameters((p) => ({ ...p, frequency_penalty: value ?? 0.0 }))}
                      min={0}
                      max={2}
                      step={0.1}
                      className="w-full"
                    />
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">{t("chat.message.parameter_presence_penalty")}</Label>
                      <span className="text-xs text-muted-foreground">{parameters.presence_penalty.toFixed(1)}</span>
                    </div>
                    <Slider
                      value={[parameters.presence_penalty]}
                      onValueChange={([value]) => setParameters((p) => ({ ...p, presence_penalty: value ?? 0.0 }))}
                      min={0}
                      max={2}
                      step={0.1}
                      className="w-full"
                    />
                  </div>

                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setParameters(DEFAULT_PARAMETERS)}
                    className="w-full"
                  >
                    {t("chat.message.reset_parameters")}
                  </Button>
                </div>
              </PopoverContent>
            </Popover>

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
            {onClearHistory && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    onClick={handleClearHistory}
                    disabled={disabled || isSending}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>{t("chat.message.clear_history")}</p>
                </TooltipContent>
              </Tooltip>
            )}

            {/* 发送按钮 */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  size="icon"
                  onClick={handleSend}
                  disabled={disabled || isSending}
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
          </div>
        </TooltipProvider>
      </div>

      {/* 提示文本 */}
      <p className="text-xs text-muted-foreground text-center">
        {t("chat.message.send_hint")}
      </p>
    </div>
  );
}
