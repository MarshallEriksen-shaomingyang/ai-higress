"use client";

import { useId, useMemo, useState } from "react";
import { Mic, Trash2, UploadCloud } from "lucide-react";

import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { useI18n } from "@/lib/i18n-context";
import { useResponsiveDrawerDirection } from "@/lib/hooks/use-responsive-drawer-direction";
import { useAudioAssets } from "@/lib/swr/use-audio-assets";
import { audioService } from "@/http/audio";
import { useAuthStore } from "@/lib/stores/auth-store";

export type UploadedAudioAttachment = {
  audio_id: string;
  object_key: string;
  url: string;
  content_type: string;
  size_bytes: number;
  format: "wav" | "mp3";
  filename?: string;
  visibility?: "private" | "public";
  owner_id?: string;
};

export function AudioInputSettingsDrawer({
  open,
  onOpenChange,
  disabled = false,
  isUploading = false,
  isTranscribing = false,
  audio,
  onPickFile,
  onPickFromLibrary,
  onRemove,
  onTranscribeToText,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  disabled?: boolean;
  isUploading?: boolean;
  isTranscribing?: boolean;
  audio: UploadedAudioAttachment | null;
  onPickFile: (file: File | null) => void | Promise<void>;
  onPickFromLibrary: (asset: UploadedAudioAttachment) => void;
  onRemove: () => void;
  onTranscribeToText: (params: {
    model?: string | null;
    language?: string | null;
    prompt?: string | null;
  }) => void | Promise<void>;
}) {
  const { t } = useI18n();
  const direction = useResponsiveDrawerDirection();
  const inputId = useId();
  const [showShared, setShowShared] = useState(true);
  const currentUserId = useAuthStore((s) => s.user?.id ?? null);
  const [sttModel, setSttModel] = useState("");
  const [sttLanguage, setSttLanguage] = useState("");
  const [sttPrompt, setSttPrompt] = useState("");

  const { items, isLoading, mutate } = useAudioAssets({
    visibility: showShared ? "all" : "private",
    limit: 100,
  });

  const grouped = useMemo(() => {
    const mine: typeof items = [];
    const shared: typeof items = [];
    for (const it of items) {
      if (currentUserId && it.owner_id === currentUserId) {
        mine.push(it);
      } else {
        // 只有 public 才会出现在列表（除非是自己的 private）
        if (it.visibility === "public") shared.push(it);
      }
    }
    return { mine, shared };
  }, [currentUserId, items]);

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction={direction}>
      <DrawerContent className="mx-auto w-full max-w-md">
        <DrawerHeader className="pb-2">
          <DrawerTitle className="inline-flex items-center gap-2">
            <Mic className="size-4" />
            {t("chat.audio_input.title")}
          </DrawerTitle>
        </DrawerHeader>

        <div className="px-4 pb-4 space-y-3">
          <Input
            id={inputId}
            type="file"
            accept="audio/*"
            className="hidden"
            disabled={disabled || isUploading}
            onChange={(e) => {
              const file = e.target.files?.[0] ?? null;
              onPickFile(file);
              e.target.value = "";
            }}
          />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("chat.audio_input.upload")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button
                type="button"
                variant="outline"
                disabled={disabled || isUploading}
                onClick={() => {
                  const el = document.getElementById(inputId);
                  if (el instanceof HTMLInputElement) el.click();
                }}
                className="w-full"
              >
                <UploadCloud className="size-4 mr-2" />
                {isUploading ? t("chat.audio_input.uploading") : t("chat.audio_input.pick_file")}
              </Button>

              {audio ? (
                <div className="space-y-2">
                  <div className="text-xs text-muted-foreground">
                    {audio.filename ? `${audio.filename} · ` : ""}
                    {audio.format.toUpperCase()} · {Math.round(audio.size_bytes / 1024)} KB
                  </div>
                  {/* 浏览器原生音频控件；无需复杂样式 */}
                  <audio controls src={audio.url} className="w-full" />
                  <Button
                    type="button"
                    variant="destructive"
                    disabled={disabled || isUploading}
                    onClick={onRemove}
                    className="w-full"
                  >
                    <Trash2 className="size-4 mr-2" />
                    {t("chat.audio_input.remove")}
                  </Button>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">
                  {t("chat.audio_input.empty")}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("chat.audio_input.transcribe_title")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-2">
                <div className="text-xs text-muted-foreground">
                  {t("chat.audio_input.transcribe_help")}
                </div>
                <Input
                  value={sttModel}
                  onChange={(e) => setSttModel(e.target.value)}
                  placeholder={t("chat.audio_input.transcribe_model_placeholder")}
                  disabled={disabled || isUploading || isTranscribing}
                />
                <Input
                  value={sttLanguage}
                  onChange={(e) => setSttLanguage(e.target.value)}
                  placeholder={t("chat.audio_input.transcribe_language_placeholder")}
                  disabled={disabled || isUploading || isTranscribing}
                />
                <Input
                  value={sttPrompt}
                  onChange={(e) => setSttPrompt(e.target.value)}
                  placeholder={t("chat.audio_input.transcribe_prompt_placeholder")}
                  disabled={disabled || isUploading || isTranscribing}
                />
              </div>

              <Button
                type="button"
                className="w-full"
                disabled={disabled || isUploading || isTranscribing || !audio}
                onClick={async () => {
                  if (!audio) return;
                  await onTranscribeToText({
                    model: sttModel.trim() || null,
                    language: sttLanguage.trim() || null,
                    prompt: sttPrompt.trim() || null,
                  });
                }}
              >
                {isTranscribing
                  ? t("chat.audio_input.transcribing")
                  : t("chat.audio_input.transcribe_action")}
              </Button>
            </CardContent>
          </Card>

          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">{t("chat.audio_library.title")}</div>
            <div className="flex items-center gap-2">
              <div className="text-xs text-muted-foreground">{t("chat.audio_library.show_shared")}</div>
              <Switch checked={showShared} onCheckedChange={setShowShared} disabled={disabled || isUploading} />
            </div>
          </div>

          <Card>
            <CardContent className="pt-4 space-y-3">
              {isLoading ? (
                <div className="text-xs text-muted-foreground">{t("chat.audio_library.loading")}</div>
              ) : items.length === 0 ? (
                <div className="text-xs text-muted-foreground">{t("chat.audio_library.empty")}</div>
              ) : (
                <div className="space-y-3">
                  {grouped.mine.length ? (
                    <div className="space-y-2">
                      <div className="text-xs text-muted-foreground">{t("chat.audio_library.mine")}</div>
                      {grouped.mine.map((it) => (
                        <div key={it.audio_id} className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="text-sm truncate">{it.display_name || it.filename || it.audio_id}</div>
                            <div className="text-xs text-muted-foreground">
                              {it.format.toUpperCase()} · {Math.round(it.size_bytes / 1024)} KB
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Switch
                              checked={it.visibility === "public"}
                              disabled={disabled || isUploading}
                              onCheckedChange={async (checked) => {
                                try {
                                  await audioService.updateAudioAssetVisibility(it.audio_id, checked ? "public" : "private");
                                  await mutate();
                                } catch (e) {
                                  console.error("updateAudioAssetVisibility failed", e);
                                }
                              }}
                            />
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={disabled || isUploading}
                              onClick={() =>
                                onPickFromLibrary({
                                  audio_id: it.audio_id,
                                  object_key: it.object_key,
                                  url: it.url,
                                  content_type: it.content_type,
                                  size_bytes: it.size_bytes,
                                  format: it.format,
                                  filename: it.filename ?? undefined,
                                  visibility: it.visibility,
                                  owner_id: it.owner_id,
                                })
                              }
                            >
                              {t("chat.audio_library.use")}
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="destructive"
                              disabled={disabled || isUploading}
                              onClick={async () => {
                                try {
                                  await audioService.deleteAudioAsset(it.audio_id);
                                  await mutate();
                                } catch (e) {
                                  console.error("deleteAudioAsset failed", e);
                                }
                              }}
                            >
                              {t("chat.audio_library.delete")}
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {showShared && grouped.shared.length ? (
                    <>
                      <Separator />
                      <div className="space-y-2">
                        <div className="text-xs text-muted-foreground">{t("chat.audio_library.shared")}</div>
                        {grouped.shared.map((it) => (
                          <div key={it.audio_id} className="flex items-center justify-between gap-2">
                            <div className="min-w-0">
                              <div className="text-sm truncate">{it.display_name || it.filename || it.audio_id}</div>
                              <div className="text-xs text-muted-foreground truncate">
                                {t("chat.audio_library.by")}{" "}
                                {it.owner_display_name || it.owner_username}
                              </div>
                            </div>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={disabled || isUploading}
                              onClick={() =>
                                onPickFromLibrary({
                                  audio_id: it.audio_id,
                                  object_key: it.object_key,
                                  url: it.url,
                                  content_type: it.content_type,
                                  size_bytes: it.size_bytes,
                                  format: it.format,
                                  filename: it.filename ?? undefined,
                                  visibility: it.visibility,
                                  owner_id: it.owner_id,
                                })
                              }
                            >
                              {t("chat.audio_library.use")}
                            </Button>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : null}
                </div>
              )}
            </CardContent>
          </Card>

          <div className="text-xs text-muted-foreground">
            {t("chat.audio_input.hint")}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
