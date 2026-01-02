"use client";

import { useEffect, useState, useCallback, useMemo, useRef } from "react";
import type { ClipboardEvent, KeyboardEvent } from "react";
import { createEditor, Descendant, Editor, Transforms, Element as SlateElement } from "slate";
import { withReact, ReactEditor } from "slate-react";
import { withHistory } from "slate-history";
import { toast } from "sonner";

import { useI18n } from "@/lib/i18n-context";
import { useChatModelParametersStore } from "@/lib/stores/chat-model-parameters-store";
import { useUserPreferencesStore } from "@/lib/stores/user-preferences-store";
import { cn } from "@/lib/utils";

import type { ComposerSubmitPayload } from "@/lib/chat/composer-submit";
import { ChatEditor } from "./chat-input/chat-editor";
import { ChatToolbar } from "./chat-input/chat-toolbar";
import { ImagePreviewGrid } from "./chat-input/image-attachments";
import { buildModelPreset } from "./chat-input/model-preset";
import { encodeImageFileToCompactDataUrl } from "./chat-input/image-encoding";
import { composeMessageContent, isMessageTooLong } from "./chat-input/message-content";
import type { ModelParameters } from "./chat-input/types";
import { type ImageGenParams } from "./chat-input/image-gen-params-bar";
import type { ComposerMode } from "./chat-input/chat-toolbar";
import { ImageGenSettingsDrawer } from "./chat-input/image-gen-settings-drawer";
import {
  AudioInputSettingsDrawer,
  type UploadedAudioAttachment,
} from "./chat-input/audio-input-settings-drawer";
import { VoiceSelectorDrawer } from "./chat-input/voice-selector-drawer";
import { SlashCommandMenu, isSlashCommandInput } from "./chat-input/slash-command-menu";
import { audioService } from "@/http/audio";
import { Button } from "@/components/ui/button";
import type { SelectedVoiceAudio } from "@/lib/stores/user-preferences-store";

export type { ModelParameters } from "./chat-input/types";
export type { ImageGenParams };

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
const MAX_AUDIO_BYTES = 10 * 1024 * 1024;

export interface SlateChatInputProps {
  conversationId: string;
  assistantId?: string;
  projectId?: string | null;
  disabled?: boolean;
  
  // Mode support
  mode?: ComposerMode;
  onModeChange?: (mode: ComposerMode) => void;
  imageGenParams?: ImageGenParams;
  onImageGenParamsChange?: (params: ImageGenParams) => void;
  hideModeSwitcher?: boolean;
  imageSettingsShowModelSelect?: boolean;

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
  
  onImageSend?: (payload: {
    prompt: string;
    params: ImageGenParams;
  }) => Promise<void>;

  onSubmit?: (payload: ComposerSubmitPayload) => Promise<void>;

  onClearHistory?: () => Promise<void>;
  className?: string;
}

export function SlateChatInput({
  conversationId,
  projectId = null,
  disabled = false,
  mode = "chat",
  onModeChange,
  imageGenParams,
  onImageGenParamsChange,
  hideModeSwitcher = false,
  imageSettingsShowModelSelect = true,
  onSend,
  onImageSend,
  onSubmit,
  onClearHistory,
  className,
}: SlateChatInputProps) {
  const { t } = useI18n();
  const {
    preferences,
    setSelectedVoiceAudio,
    setSpeechModeEnabled,
  } = useUserPreferencesStore();
  const [editor] = useState(() => withHistory(withReact(createEditor())));
  const [isSending, setIsSending] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [clearDialogOpen, setClearDialogOpen] = useState(false);
  const [images, setImages] = useState<string[]>([]);
  const editorRef = useRef<HTMLDivElement>(null);
  const [imageSettingsOpen, setImageSettingsOpen] = useState(false);
  const [audioSettingsOpen, setAudioSettingsOpen] = useState(false);
  const [audioAttachment, setAudioAttachment] = useState<UploadedAudioAttachment | null>(null);
  const [isUploadingAudio, setIsUploadingAudio] = useState(false);
  const [isTranscribingAudio, setIsTranscribingAudio] = useState(false);
  const [audioLocalFile, setAudioLocalFile] = useState<File | null>(null);
  const [voiceSelectorOpen, setVoiceSelectorOpen] = useState(false);
  const [slashCommandInput, setSlashCommandInput] = useState("");
  const [showSlashMenu, setShowSlashMenu] = useState(false);

  // 语音模式：选中的参考音频
  const selectedVoiceAudio = projectId
    ? preferences.selectedVoiceAudioByProject[projectId] ?? null
    : null;

  // 语音克隆开关状态
  const voiceEnabled = projectId
    ? preferences.speechModeEnabledByProject[projectId] ?? false
    : false;

  // 模型参数状态（持久化）：用户设置后后续每次发送都会沿用
  const parameters = useChatModelParametersStore((s) => s.parameters);
  const setParameters = useChatModelParametersStore((s) => s.setParameters);
  const resetModelParameters = useChatModelParametersStore((s) => s.reset);

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

  const insertTextToEditor = useCallback(
    (text: string) => {
      const next = String(text || "").trim();
      if (!next) return;

      try {
        ReactEditor.focus(editor);
      } catch {
        // ignore focus errors
      }
      try {
        Transforms.select(editor, Editor.end(editor, []));
      } catch {
        // ignore selection errors
      }

      const existing = getTextContent();
      const prefix = existing ? "\n" : "";
      Transforms.insertText(editor, `${prefix}${next}`);
    },
    [editor, getTextContent]
  );

  const resolveAudioFileForTranscription = useCallback(async () => {
    if (audioLocalFile) return audioLocalFile;
    if (!audioAttachment?.url) return null;

    const resp = await fetch(audioAttachment.url);
    if (!resp.ok) {
      throw new Error(`Failed to fetch audio asset: ${resp.status}`);
    }
    const blob = await resp.blob();
    const fallbackName = audioAttachment.filename
      ? audioAttachment.filename
      : `audio.${audioAttachment.format}`;
    return new File([blob], fallbackName, {
      type: audioAttachment.content_type || blob.type || "application/octet-stream",
    });
  }, [audioAttachment, audioLocalFile]);

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

  const handlePaste = useCallback(
    async (event: ClipboardEvent) => {
      const { clipboardData } = event;
      if (!clipboardData) return;

      const imageFiles = Array.from(clipboardData.items || [])
        .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
        .map((item) => item.getAsFile())
        .filter((file): file is File => Boolean(file));

      if (imageFiles.length === 0) return;

      // 使用浏览器原生 DataTransfer 构造 FileList，复用现有文件处理逻辑。
      const dt = new DataTransfer();
      imageFiles.forEach((file) => dt.items.add(file));
      event.preventDefault();
      await handleFilesSelected(dt.files);
    },
    [handleFilesSelected]
  );

  // 移除图片
  const removeImage = useCallback((index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // 发送消息
  const handleSend = useCallback(async () => {
    const content = getTextContent();
    
    if (isUploadingAudio) {
      toast.error(t("chat.audio_input.uploading"));
      return;
    }

    if (!content && images.length === 0 && !audioAttachment) {
      toast.error(t("chat.message.input_placeholder"));
      return;
    }

    if (disabled) {
      toast.error(t("chat.conversation.archived_notice"));
      return;
    }

    setIsSending(true);

    try {
      if (mode === "image") {
        if (!imageGenParams) {
          console.error("Image generation params missing");
          return;
        }
        if (onSubmit) {
          await onSubmit({
            mode: "image",
            prompt: content,
            params: imageGenParams,
          });
        } else {
          if (!onImageSend) {
            console.error("Image generation handler missing");
            return;
          }
          await onImageSend({
            prompt: content,
            params: imageGenParams,
          });
        }
      } else if (mode === "speech") {
        // 语音模式：发送文本内容用于语音合成
        if (!content) {
          toast.error(t("chat.message.input_placeholder"));
          return;
        }
        const model_preset = buildModelPreset(parameters);
        const voice_audio = selectedVoiceAudio
          ? { audio_id: selectedVoiceAudio.audio_id, format: selectedVoiceAudio.format }
          : null;
        if (onSubmit) {
          await onSubmit({
            mode: "speech",
            content,
            voice_audio,
            model_preset,
            parameters,
          });
        }
      } else {
        const composed = composeMessageContent(content, images);
        if (!composed && !audioAttachment) {
          toast.error(t("chat.message.input_placeholder"));
          return;
        }
        if (isMessageTooLong(composed)) {
          toast.error(t("chat.errors.message_too_long"));
          return;
        }

        const model_preset = buildModelPreset(parameters);
        const input_audio = audioAttachment
          ? { audio_id: audioAttachment.audio_id, format: audioAttachment.format }
          : null;
        if (onSubmit) {
          await onSubmit({
            mode: "chat",
            content: composed,
            images,
            input_audio,
            model_preset,
            parameters,
          });
        } else if (onSend) {
          if (onSend.length <= 1) {
            await (onSend as any)({
              content: composed,
              images,
              input_audio,
              model_preset,
              parameters,
            });
          } else {
            await (onSend as any)(composed, images, parameters);
          }
        }
      }
      
      // 清空编辑器和图片
      clearEditor();
      setImages([]);
      setAudioAttachment(null);
    } catch (error) {
      console.error("Failed to send message:", error);
    } finally {
      setIsSending(false);
    }
  }, [getTextContent, images, audioAttachment, isUploadingAudio, disabled, onSend, onImageSend, parameters, clearEditor, t, mode, imageGenParams]);

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

  const sendHint = useMemo(
    () =>
      preferences.sendShortcut === "enter"
        ? t("chat.settings.preferences.send_shortcut_enter_desc")
        : t("chat.settings.preferences.send_shortcut_ctrl_enter_desc"),
    [preferences.sendShortcut, t]
  );

  // 键盘快捷键
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.nativeEvent.isComposing) return;

      if (preferences.sendShortcut === "enter") {
        if (
          event.key === "Enter" &&
          !event.shiftKey &&
          !event.ctrlKey &&
          !event.metaKey &&
          !event.altKey
        ) {
          event.preventDefault();
          void handleSend();
        }
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        void handleSend();
      }
    },
    [handleSend, preferences.sendShortcut]
  );

  useEffect(() => {
    if (mode !== "image" && imageSettingsOpen) {
      setImageSettingsOpen(false);
    }
  }, [imageSettingsOpen, mode]);

  useEffect(() => {
    if (mode !== "chat" && mode !== "speech") {
      setAudioSettingsOpen(false);
      setAudioAttachment(null);
      setIsUploadingAudio(false);
    }
    if (mode !== "speech") {
      setVoiceSelectorOpen(false);
    }
  }, [mode]);

  const handleSelectVoice = useCallback(
    (voice: SelectedVoiceAudio | null) => {
      if (!projectId) return;
      setSelectedVoiceAudio(projectId, voice);
    },
    [projectId, setSelectedVoiceAudio]
  );

  const handleVoiceEnabledChange = useCallback(
    (enabled: boolean) => {
      if (!projectId) return;
      setSpeechModeEnabled(projectId, enabled);
    },
    [projectId, setSpeechModeEnabled]
  );

  const handleOpenVoiceSelector = useCallback(() => {
    setVoiceSelectorOpen(true);
  }, []);

  // 处理斜杠命令选择
  const handleSlashCommandSelect = useCallback(
    (selectedMode: ComposerMode) => {
      // 清空编辑器
      clearEditor();
      setSlashCommandInput("");
      setShowSlashMenu(false);
      // 切换模式
      onModeChange?.(selectedMode);
    },
    [clearEditor, onModeChange]
  );

  // 监听编辑器内容变化，检测斜杠命令
  const handleEditorChange = useCallback(() => {
    const content = getTextContent();
    if (isSlashCommandInput(content)) {
      setSlashCommandInput(content);
      setShowSlashMenu(true);
    } else {
      setSlashCommandInput("");
      setShowSlashMenu(false);
    }
  }, [getTextContent]);

  return (
    <div className={cn("relative flex h-full flex-col bg-background", className)}>
      <div className="flex min-h-0 flex-1 flex-col justify-end px-2 md:px-4 pt-1 pb-2 md:pb-[calc(env(safe-area-inset-bottom)+1.25rem)]">
        <div className="mx-auto flex min-h-0 w-full max-w-3xl flex-1 flex-col gap-2 md:gap-3">
          {mode === "chat" && (
            <ImagePreviewGrid
              images={images}
              disabled={disabled || isSending}
              onRemoveImage={removeImage}
              uploadedAltPrefix={t("chat.message.uploaded_image")}
              removeLabel={t("chat.message.remove_image")}
            />
          )}

          {mode === "chat" && audioAttachment ? (
            <div className="flex items-center justify-between gap-2 rounded-md border bg-muted/30 px-3 py-2">
              <div className="text-xs text-muted-foreground truncate">
                {t("chat.audio_input.title")}:{" "}
                {audioAttachment.filename || audioAttachment.object_key}
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={disabled || isSending}
                onClick={() => setAudioSettingsOpen(true)}
              >
                {t("chat.action.edit")}
              </Button>
            </div>
          ) : null}

          <div
            className={cn(
              "relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl md:rounded-2xl border bg-background shadow-[0_8px_24px_rgba(0,0,0,0.08)] md:shadow-[0_16px_48px_rgba(0,0,0,0.10)]",
              "supports-[backdrop-filter]:bg-background/80 supports-[backdrop-filter]:backdrop-blur-md",
              "dark:shadow-[0_8px_24px_rgba(0,0,0,0.25)] dark:md:shadow-[0_16px_48px_rgba(0,0,0,0.35)]",
              "focus-within:ring-2 focus-within:ring-ring/40"
            )}
          >
            {/* 斜杠命令菜单 */}
            {showSlashMenu && (
              <SlashCommandMenu
                inputText={slashCommandInput}
                onSelectCommand={handleSlashCommandSelect}
                onClose={() => setShowSlashMenu(false)}
              />
            )}

            <ChatEditor
              editor={editor}
              editorRef={editorRef}
              initialValue={initialValue}
              disabled={disabled}
              isSending={isSending}
              isSlashCommand={showSlashMenu}
              placeholder={
                disabled
                  ? t("chat.conversation.archived_notice")
                  : mode === "image"
                    ? t("chat.image_gen.prompt")
                    : mode === "speech"
                      ? t("chat.speech.prompt")
                      : t("chat.message.input_placeholder")
              }
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              onChange={handleEditorChange}
            />

            <ChatToolbar
              mode={mode}
              onModeChange={onModeChange}
              conversationId={conversationId}
              disabled={disabled}
              isSending={isSending}
              isClearing={isClearing}
              clearDialogOpen={clearDialogOpen}
              onClearDialogOpenChange={setClearDialogOpen}
              onClearHistory={onClearHistory ? () => void handleClearHistory() : undefined}
              onSend={() => void handleSend()}
              sendHint={sendHint}
              parameters={parameters}
              onParametersChange={setParameters}
              onResetParameters={() => {
                resetModelParameters();
              }}
              onFilesSelected={handleFilesSelected}
              hideModeSwitcher={hideModeSwitcher}
              onOpenImageSettings={
                mode === "image" && imageGenParams && onImageGenParamsChange
                  ? () => setImageSettingsOpen(true)
                  : undefined
              }
              onOpenAudioSettings={mode === "chat" ? () => setAudioSettingsOpen(true) : undefined}
              onOpenVoiceSelector={projectId ? handleOpenVoiceSelector : undefined}
            />
          </div>

          <div className="text-[10px] md:text-xs text-muted-foreground text-center px-2">
            {isSending
              ? mode === "image"
                ? t("chat.image_gen.generating")
                : mode === "speech"
                  ? t("chat.speech.generating")
                  : t("chat.message.sending")
              : sendHint}
          </div>
        </div>
      </div>

      {imageGenParams && onImageGenParamsChange ? (
        <ImageGenSettingsDrawer
          projectId={projectId}
          open={imageSettingsOpen}
          onOpenChange={setImageSettingsOpen}
          params={imageGenParams}
          onChange={onImageGenParamsChange}
          disabled={disabled || isSending}
          showModelSelect={imageSettingsShowModelSelect}
        />
      ) : null}

      <AudioInputSettingsDrawer
        open={audioSettingsOpen}
        onOpenChange={setAudioSettingsOpen}
        disabled={disabled || isSending}
        isUploading={isUploadingAudio}
        isTranscribing={isTranscribingAudio}
        audio={audioAttachment}
        onRemove={() => {
          setAudioAttachment(null);
          setAudioLocalFile(null);
        }}
        onPickFromLibrary={(asset) => {
          setAudioAttachment(asset);
          setAudioLocalFile(null);
          setAudioSettingsOpen(false);
        }}
        onPickFile={async (file) => {
          if (!file) return;
          if (disabled || isSending) return;
          if (file.size > MAX_AUDIO_BYTES) {
            toast.error(t("chat.audio_input.too_large"));
            return;
          }
          if (!String(file.type || "").startsWith("audio/")) {
            toast.error(t("chat.audio_input.unsupported"));
            return;
          }
          setAudioLocalFile(file);
          setIsUploadingAudio(true);
          try {
            const uploaded = await audioService.uploadConversationAudio(conversationId, file);
            setAudioAttachment({
              ...uploaded,
              filename: file.name,
            });
            toast.success(t("chat.audio_input.upload_success"));
          } catch (error) {
            console.error("Audio upload failed", error);
            toast.error(t("chat.audio_input.upload_failed"));
          } finally {
            setIsUploadingAudio(false);
          }
        }}
        onTranscribeToText={async (params) => {
          if (disabled || isSending) return;
          if (isUploadingAudio) {
            toast.error(t("chat.audio_input.uploading"));
            return;
          }
          if (!audioAttachment) {
            toast.error(t("chat.audio_input.empty"));
            return;
          }
          setIsTranscribingAudio(true);
          try {
            const file = await resolveAudioFileForTranscription();
            if (!file) {
              toast.error(t("chat.audio_input.empty"));
              return;
            }
            const res = await audioService.transcribeConversationAudio(conversationId, file, params);
            insertTextToEditor(res.text);
            toast.success(t("chat.audio_input.transcribe_success"));
            setAudioSettingsOpen(false);
          } catch (e) {
            console.error("Audio transcription failed", e);
            toast.error(t("chat.audio_input.transcribe_failed"));
          } finally {
            setIsTranscribingAudio(false);
          }
        }}
      />

      <VoiceSelectorDrawer
        open={voiceSelectorOpen}
        onOpenChange={setVoiceSelectorOpen}
        disabled={disabled || isSending}
        selectedVoice={selectedVoiceAudio}
        onSelectVoice={handleSelectVoice}
        conversationId={conversationId}
        voiceEnabled={voiceEnabled}
        onVoiceEnabledChange={projectId ? handleVoiceEnabledChange : undefined}
      />
    </div>
  );
}
