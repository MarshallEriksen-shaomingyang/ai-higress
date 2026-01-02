"use client";

import { useId, useMemo, useState } from "react";
import { Mic, Trash2, UploadCloud, Check } from "lucide-react";
import { toast } from "sonner";

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
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import { useResponsiveDrawerDirection } from "@/lib/hooks/use-responsive-drawer-direction";
import { useAudioAssets } from "@/lib/swr/use-audio-assets";
import { audioService } from "@/http/audio";
import { useAuthStore } from "@/lib/stores/auth-store";
import type { SelectedVoiceAudio } from "@/lib/stores/user-preferences-store";

export interface VoiceSelectorDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  disabled?: boolean;
  selectedVoice: SelectedVoiceAudio | null;
  onSelectVoice: (voice: SelectedVoiceAudio | null) => void;
  conversationId: string;
}

export function VoiceSelectorDrawer({
  open,
  onOpenChange,
  disabled = false,
  selectedVoice,
  onSelectVoice,
  conversationId,
}: VoiceSelectorDrawerProps) {
  const { t } = useI18n();
  const direction = useResponsiveDrawerDirection();
  const inputId = useId();
  const [showShared, setShowShared] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const currentUserId = useAuthStore((s) => s.user?.id ?? null);

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
        if (it.visibility === "public") shared.push(it);
      }
    }
    return { mine, shared };
  }, [currentUserId, items]);

  const handleUploadFile = async (file: File | null) => {
    if (!file) return;
    if (disabled || isUploading) return;

    const MAX_AUDIO_BYTES = 10 * 1024 * 1024;
    if (file.size > MAX_AUDIO_BYTES) {
      toast.error(t("chat.audio_input.too_large"));
      return;
    }
    if (!String(file.type || "").startsWith("audio/")) {
      toast.error(t("chat.audio_input.unsupported"));
      return;
    }

    setIsUploading(true);
    try {
      const uploaded = await audioService.uploadConversationAudio(conversationId, file);
      onSelectVoice({
        audio_id: uploaded.audio_id,
        object_key: uploaded.object_key,
        url: uploaded.url,
        filename: file.name,
        format: uploaded.format,
      });
      await mutate();
      toast.success(t("chat.audio_input.upload_success"));
    } catch (error) {
      console.error("Audio upload failed", error);
      toast.error(t("chat.audio_input.upload_failed"));
    } finally {
      setIsUploading(false);
    }
  };

  const isSelected = (audioId: string) => selectedVoice?.audio_id === audioId;

  const handleSelectItem = (it: typeof items[number]) => {
    if (isSelected(it.audio_id)) {
      onSelectVoice(null);
    } else {
      onSelectVoice({
        audio_id: it.audio_id,
        object_key: it.object_key,
        url: it.url,
        filename: it.filename ?? undefined,
        format: it.format,
      });
    }
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange} direction={direction}>
      <DrawerContent className="mx-auto w-full max-w-md">
        <DrawerHeader className="pb-2">
          <DrawerTitle className="inline-flex items-center gap-2">
            <Mic className="size-4" />
            {t("chat.voice_selector.title")}
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
              void handleUploadFile(file);
              e.target.value = "";
            }}
          />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("chat.voice_selector.upload")}</CardTitle>
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
                {isUploading ? t("chat.audio_input.uploading") : t("chat.voice_selector.upload_new")}
              </Button>
            </CardContent>
          </Card>

          {selectedVoice && (
            <Card className="border-primary">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Check className="size-4 text-primary" />
                  {t("chat.voice_selector.selected")}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="text-sm truncate">{selectedVoice.filename || selectedVoice.audio_id}</div>
                <audio controls src={selectedVoice.url} className="w-full h-8" />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={disabled}
                  onClick={() => onSelectVoice(null)}
                  className="w-full"
                >
                  <Trash2 className="size-4 mr-2" />
                  {t("chat.voice_selector.clear_selection")}
                </Button>
              </CardContent>
            </Card>
          )}

          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">{t("chat.audio_library.title")}</div>
            <div className="flex items-center gap-2">
              <div className="text-xs text-muted-foreground">{t("chat.audio_library.show_shared")}</div>
              <Switch checked={showShared} onCheckedChange={setShowShared} disabled={disabled || isUploading} />
            </div>
          </div>

          <Card>
            <CardContent className="pt-4 space-y-3 max-h-64 overflow-y-auto">
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
                        <div
                          key={it.audio_id}
                          className={cn(
                            "flex items-center justify-between gap-2 p-2 rounded-md cursor-pointer transition-colors",
                            isSelected(it.audio_id)
                              ? "bg-primary/10 border border-primary"
                              : "hover:bg-muted/50"
                          )}
                          onClick={() => handleSelectItem(it)}
                        >
                          <div className="min-w-0 flex-1">
                            <div className="text-sm truncate">{it.display_name || it.filename || it.audio_id}</div>
                            <div className="text-xs text-muted-foreground">
                              {it.format.toUpperCase()} · {Math.round(it.size_bytes / 1024)} KB
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {isSelected(it.audio_id) && <Check className="size-4 text-primary" />}
                            <Switch
                              checked={it.visibility === "public"}
                              disabled={disabled || isUploading}
                              onClick={(e) => e.stopPropagation()}
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
                              variant="destructive"
                              disabled={disabled || isUploading}
                              onClick={async (e) => {
                                e.stopPropagation();
                                try {
                                  if (isSelected(it.audio_id)) {
                                    onSelectVoice(null);
                                  }
                                  await audioService.deleteAudioAsset(it.audio_id);
                                  await mutate();
                                } catch (err) {
                                  console.error("deleteAudioAsset failed", err);
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
                          <div
                            key={it.audio_id}
                            className={cn(
                              "flex items-center justify-between gap-2 p-2 rounded-md cursor-pointer transition-colors",
                              isSelected(it.audio_id)
                                ? "bg-primary/10 border border-primary"
                                : "hover:bg-muted/50"
                            )}
                            onClick={() => handleSelectItem(it)}
                          >
                            <div className="min-w-0 flex-1">
                              <div className="text-sm truncate">{it.display_name || it.filename || it.audio_id}</div>
                              <div className="text-xs text-muted-foreground truncate">
                                {t("chat.audio_library.by")}{" "}
                                {it.owner_display_name || it.owner_username}
                              </div>
                            </div>
                            {isSelected(it.audio_id) && <Check className="size-4 text-primary" />}
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
            {t("chat.voice_selector.hint")}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
