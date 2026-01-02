"use client";

import { useId, useMemo, useState, useCallback } from "react";
import { Mic, Trash2, UploadCloud, Check, Globe, Lock, Play, Pause, MoreHorizontal } from "lucide-react";
import { toast } from "sonner";

import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import { useResponsiveDrawerDirection } from "@/lib/hooks/use-responsive-drawer-direction";
import { useAudioAssets } from "@/lib/swr/use-audio-assets";
import { audioService, type AudioAssetItem } from "@/http/audio";
import { useAuthStore } from "@/lib/stores/auth-store";
import type { SelectedVoiceAudio } from "@/lib/stores/user-preferences-store";

// ============================================
// Voice Card Component
// ============================================

interface VoiceCardProps {
  item: AudioAssetItem;
  isSelected: boolean;
  isOwner: boolean;
  disabled?: boolean;
  onSelect: () => void;
  onToggleVisibility: (visibility: "private" | "public") => Promise<void>;
  onDelete: () => Promise<void>;
  t: (key: string) => string;
}

function VoiceCard({
  item,
  isSelected,
  isOwner,
  disabled = false,
  onSelect,
  onToggleVisibility,
  onDelete,
  t,
}: VoiceCardProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioEl, setAudioEl] = useState<HTMLAudioElement | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);

  const isPublic = item.visibility === "public";
  const displayName = item.display_name || item.filename || item.audio_id.slice(0, 8);
  const sizeKB = Math.round(item.size_bytes / 1024);

  const handlePlayPause = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    if (!audioEl) {
      const audio = new Audio(item.url);
      audio.onended = () => setIsPlaying(false);
      audio.onpause = () => setIsPlaying(false);
      audio.onplay = () => setIsPlaying(true);
      setAudioEl(audio);
      audio.play().catch(() => setIsPlaying(false));
    } else {
      if (isPlaying) {
        audioEl.pause();
      } else {
        audioEl.play().catch(() => setIsPlaying(false));
      }
    }
  }, [audioEl, isPlaying, item.url]);

  const handleToggleVisibility = useCallback(async () => {
    if (disabled || isUpdating) return;
    setIsUpdating(true);
    try {
      await onToggleVisibility(isPublic ? "private" : "public");
      toast.success(isPublic ? t("chat.voice_card.made_private") : t("chat.voice_card.made_public"));
    } catch {
      toast.error(t("chat.voice_card.update_failed"));
    } finally {
      setIsUpdating(false);
    }
  }, [disabled, isUpdating, isPublic, onToggleVisibility, t]);

  const handleDelete = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (disabled || isUpdating) return;
    setIsUpdating(true);
    try {
      await onDelete();
      toast.success(t("chat.voice_card.deleted"));
    } catch {
      toast.error(t("chat.voice_card.delete_failed"));
    } finally {
      setIsUpdating(false);
    }
  }, [disabled, isUpdating, onDelete, t]);

  return (
    <Card
      className={cn(
        "group relative cursor-pointer transition-all hover:shadow-md",
        isSelected && "ring-2 ring-primary shadow-md",
        disabled && "opacity-60 cursor-not-allowed"
      )}
      onClick={disabled ? undefined : onSelect}
    >
      <div className="p-3">
        {/* 顶部：名称 + 状态 */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              {isSelected && (
                <Check className="size-4 shrink-0 text-primary" />
              )}
              <span className="text-sm font-medium truncate">{displayName}</span>
            </div>
            <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
              <span>{item.format.toUpperCase()}</span>
              <span>·</span>
              <span>{sizeKB} KB</span>
              {!isOwner && (
                <>
                  <span>·</span>
                  <span className="truncate">
                    {t("chat.audio_library.by")} {item.owner_display_name || item.owner_username}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* 右上角：可见性标识 + 更多菜单（仅所有者） */}
          <div className="flex items-center gap-1 shrink-0">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className={cn(
                    "size-6 rounded-full flex items-center justify-center",
                    isPublic ? "bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400" : "bg-muted text-muted-foreground"
                  )}>
                    {isPublic ? <Globe className="size-3" /> : <Lock className="size-3" />}
                  </div>
                </TooltipTrigger>
                <TooltipContent side="top">
                  {isPublic ? t("chat.voice_card.public") : t("chat.voice_card.private")}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {isOwner && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-6 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => e.stopPropagation()}
                    disabled={disabled || isUpdating}
                  >
                    <MoreHorizontal className="size-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
                  <DropdownMenuItem onClick={handleToggleVisibility} disabled={isUpdating}>
                    {isPublic ? (
                      <>
                        <Lock className="size-4 mr-2" />
                        {t("chat.voice_card.make_private")}
                      </>
                    ) : (
                      <>
                        <Globe className="size-4 mr-2" />
                        {t("chat.voice_card.make_public")}
                      </>
                    )}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={handleDelete}
                    disabled={isUpdating}
                    className="text-destructive focus:text-destructive"
                  >
                    <Trash2 className="size-4 mr-2" />
                    {t("chat.audio_library.delete")}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>

        {/* 底部：播放按钮 */}
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="w-full h-8"
          onClick={handlePlayPause}
          disabled={disabled}
        >
          {isPlaying ? (
            <>
              <Pause className="size-3 mr-1.5" />
              {t("chat.voice_card.pause")}
            </>
          ) : (
            <>
              <Play className="size-3 mr-1.5" />
              {t("chat.voice_card.preview")}
            </>
          )}
        </Button>
      </div>
    </Card>
  );
}

// ============================================
// Voice Selector Drawer
// ============================================

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

        <div className="px-4 pb-4 space-y-4">
          {/* Hidden file input */}
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

          {/* Upload Button */}
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

          {/* Toggle: Show shared */}
          <div className="flex items-center justify-between">
            <div className="text-sm font-medium">{t("chat.audio_library.title")}</div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{t("chat.audio_library.show_shared")}</span>
              <Switch checked={showShared} onCheckedChange={setShowShared} disabled={disabled || isUploading} />
            </div>
          </div>

          {/* Voice List */}
          <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
            {isLoading ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                {t("chat.audio_library.loading")}
              </div>
            ) : items.length === 0 ? (
              <div className="text-sm text-muted-foreground text-center py-8">
                {t("chat.audio_library.empty")}
              </div>
            ) : (
              <>
                {/* My Voices */}
                {grouped.mine.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      {t("chat.audio_library.mine")}
                    </div>
                    <div className="grid gap-2">
                      {grouped.mine.map((it) => (
                        <VoiceCard
                          key={it.audio_id}
                          item={it}
                          isSelected={isSelected(it.audio_id)}
                          isOwner={true}
                          disabled={disabled || isUploading}
                          onSelect={() => handleSelectItem(it)}
                          onToggleVisibility={async (visibility) => {
                            await audioService.updateAudioAssetVisibility(it.audio_id, visibility);
                            await mutate();
                          }}
                          onDelete={async () => {
                            if (isSelected(it.audio_id)) {
                              onSelectVoice(null);
                            }
                            await audioService.deleteAudioAsset(it.audio_id);
                            await mutate();
                          }}
                          t={t}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Shared Voices */}
                {showShared && grouped.shared.length > 0 && (
                  <>
                    {grouped.mine.length > 0 && <Separator />}
                    <div className="space-y-2">
                      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        {t("chat.audio_library.shared")}
                      </div>
                      <div className="grid gap-2">
                        {grouped.shared.map((it) => (
                          <VoiceCard
                            key={it.audio_id}
                            item={it}
                            isSelected={isSelected(it.audio_id)}
                            isOwner={false}
                            disabled={disabled || isUploading}
                            onSelect={() => handleSelectItem(it)}
                            onToggleVisibility={async () => {}}
                            onDelete={async () => {}}
                            t={t}
                          />
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          {/* Hint */}
          <div className="text-xs text-muted-foreground text-center">
            {t("chat.voice_selector.hint")}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
