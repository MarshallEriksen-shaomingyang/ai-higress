"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Pause, Volume2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n-context";
import { useMessageSpeechAudio } from "@/lib/swr/use-tts";
import { useUserPreferencesStore } from "@/lib/stores/user-preferences-store";
import type { MessageSpeechRequest } from "@/lib/api-types";

declare global {
  interface Window {
    __apiproxy_tts_audio__?: HTMLAudioElement | null;
  }
}

function isNotSupportedMediaError(err: unknown): boolean {
  const anyErr = err as { name?: unknown; message?: unknown };
  const name = typeof anyErr?.name === "string" ? anyErr.name : "";
  if (name === "NotSupportedError") return true;
  const message = typeof anyErr?.message === "string" ? anyErr.message : String(err ?? "");
  return message.toLowerCase().includes("no supported source");
}

export interface MessageTtsControlProps {
  messageId: string;
  projectId?: string | null;
  fallbackModel?: string | null;
  disabled?: boolean;
}

export function MessageTtsControl({
  messageId,
  projectId = null,
  fallbackModel = null,
  disabled = false,
}: MessageTtsControlProps) {
  const { t } = useI18n();
  const { getAudio, loading } = useMessageSpeechAudio(messageId);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const preferredTtsModel = useUserPreferencesStore((s) => {
    const key = (projectId || "").trim();
    if (!key) return null;
    return s.preferences.preferredTtsModelByProject?.[key] ?? null;
  });
  const preferredTtsFormat = useUserPreferencesStore((s) => {
    const key = (projectId || "").trim();
    if (!key) return null;
    return s.preferences.preferredTtsFormatByProject?.[key] ?? null;
  });
  const preferredTtsVoice = useUserPreferencesStore((s) => {
    const key = (projectId || "").trim();
    if (!key) return null;
    return s.preferences.preferredTtsVoiceByProject?.[key] ?? null;
  });
  const preferredTtsSpeed = useUserPreferencesStore((s) => {
    const key = (projectId || "").trim();
    if (!key) return null;
    return s.preferences.preferredTtsSpeedByProject?.[key] ?? null;
  });
  const effectiveModel = preferredTtsModel || fallbackModel;
  const effectiveFormat = preferredTtsFormat || "mp3";
  const effectiveVoice = preferredTtsVoice || "alloy";
  const effectiveSpeedRaw = Number.isFinite(preferredTtsSpeed) ? (preferredTtsSpeed as number) : 1.0;
  const effectiveSpeed = Math.min(4.0, Math.max(0.25, effectiveSpeedRaw));

  const payload = useMemo<MessageSpeechRequest>(
    () => ({
      model: effectiveModel || undefined,
      voice: effectiveVoice,
      response_format: effectiveFormat,
      speed: effectiveSpeed,
    }),
    [effectiveFormat, effectiveModel, effectiveSpeed, effectiveVoice]
  );

  const resetAudio = useCallback(() => {
    const a = audioRef.current;
    if (window.__apiproxy_tts_audio__ === a) {
      window.__apiproxy_tts_audio__ = null;
    }
    if (a) {
      try {
        a.pause();
        a.currentTime = 0;
      } catch {
        // 忽略清理过程中的媒体状态异常
      }
    }
    audioRef.current = null;
    setIsPlaying(false);
  }, []);

  const play = useCallback(async () => {
    if (disabled) return;
    if (!effectiveModel) {
      toast.error(t("chat.tts.model_not_set"));
      return;
    }

    try {
      if (audioRef.current) {
        try {
          // 确保同一时间只有一个音频播放
          if (window.__apiproxy_tts_audio__ && window.__apiproxy_tts_audio__ !== audioRef.current) {
            window.__apiproxy_tts_audio__.pause();
          }
          window.__apiproxy_tts_audio__ = audioRef.current;

          await audioRef.current.play();
          setIsPlaying(true);
          return;
        } catch (err) {
          // Object URL 可能已被缓存层淘汰并 revoke，或浏览器无法识别旧音源；
          // 这类情况下需要清理本地引用并重新拉取音频，否则会“点击播放不发请求直接报错”。
          if (!isNotSupportedMediaError(err)) throw err;
          resetAudio();
        }
      }

      const result = await getAudio(payload);
      const next = new Audio(result.objectUrl);
      next.preload = "auto";

      next.onended = () => {
        setIsPlaying(false);
      };
      next.onpause = () => {
        setIsPlaying(false);
      };
      next.onplay = () => {
        setIsPlaying(true);
      };

      // 先暂停其他音频再开始播放
      if (window.__apiproxy_tts_audio__ && window.__apiproxy_tts_audio__ !== next) {
        window.__apiproxy_tts_audio__.pause();
      }
      window.__apiproxy_tts_audio__ = next;

      audioRef.current = next;
      await next.play();
      setIsPlaying(true);
    } catch (err) {
      toast.error(t("chat.tts.failed"));
      resetAudio();
    }
  }, [disabled, effectiveModel, getAudio, payload, resetAudio, t]);

  const toggle = useCallback(() => {
    if (disabled) return;
    if (loading) return;

    const a = audioRef.current;
    if (a && isPlaying) {
      a.pause();
      return;
    }
    void play();
  }, [disabled, isPlaying, loading, play]);

  useEffect(() => {
    return () => {
      // 组件卸载时清理本地 Audio 引用（Object URL 由缓存层统一管理）
      if (window.__apiproxy_tts_audio__ === audioRef.current) {
        window.__apiproxy_tts_audio__ = null;
      }
      audioRef.current?.pause();
      audioRef.current = null;
    };
  }, []);

  const tooltip = loading
    ? t("chat.tts.loading")
    : isPlaying
      ? t("chat.tts.pause")
      : t("chat.tts.play");

  const Icon = loading ? Loader2 : isPlaying ? Pause : Volume2;

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon-sm"
            disabled={disabled || loading}
            onClick={toggle}
            aria-label={tooltip}
            title={tooltip}
          >
            <Icon className={loading ? "size-3.5 animate-spin" : "size-3.5"} />
          </Button>
        </TooltipTrigger>
        <TooltipContent sideOffset={6}>{tooltip}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
