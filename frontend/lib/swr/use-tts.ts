"use client";

import useSWRMutation from "swr/mutation";
import { messageService } from "@/http/message";
import type { MessageSpeechRequest } from "@/lib/api-types";

type CachedAudio = {
  blob: Blob;
  contentType: string | null;
  objectUrl: string;
  createdAt: number;
};

const AUDIO_CACHE_MAX_ITEMS = 32;
const AUDIO_CACHE_TTL_MS = 30 * 60 * 1000;

const audioCache = new Map<string, CachedAudio>();

function getCurrentPlayingObjectUrl(): string | null {
  if (typeof window === "undefined") return null;
  const anyWin = window as any;
  const audio = anyWin.__apiproxy_tts_audio__ as HTMLAudioElement | null | undefined;
  const src = audio?.src;
  return typeof src === "string" && src ? src : null;
}

function buildAudioCacheKey(messageId: string, payload: MessageSpeechRequest): string {
  const model = String(payload.model ?? "").trim();
  const voice = payload.voice ?? "alloy";
  const responseFormat = payload.response_format ?? "mp3";
  const speed = Number.isFinite(payload.speed) ? String(payload.speed) : "1";
  const promptAudioId = String(payload.prompt_audio_id ?? "").trim();
  return `msg:${messageId}|m:${model}|v:${voice}|f:${responseFormat}|s:${speed}|pa:${promptAudioId}`;
}

function pruneAudioCache(now: number) {
  const playingUrl = getCurrentPlayingObjectUrl();
  for (const [key, item] of audioCache.entries()) {
    if (playingUrl && item.objectUrl === playingUrl) continue;
    if (now - item.createdAt > AUDIO_CACHE_TTL_MS) {
      URL.revokeObjectURL(item.objectUrl);
      audioCache.delete(key);
    }
  }

  if (audioCache.size <= AUDIO_CACHE_MAX_ITEMS) return;

  const entries = Array.from(audioCache.entries()).sort((a, b) => a[1].createdAt - b[1].createdAt);
  for (const [key, item] of entries) {
    if (audioCache.size <= AUDIO_CACHE_MAX_ITEMS) break;
    if (playingUrl && item.objectUrl === playingUrl) continue;
    URL.revokeObjectURL(item.objectUrl);
    audioCache.delete(key);
  }
}

function getCachedAudio(key: string): CachedAudio | null {
  const item = audioCache.get(key);
  if (!item) return null;
  const now = Date.now();
  if (now - item.createdAt > AUDIO_CACHE_TTL_MS) {
    URL.revokeObjectURL(item.objectUrl);
    audioCache.delete(key);
    return null;
  }
  return item;
}

function storeCachedAudio(key: string, blob: Blob, contentType: string | null): CachedAudio {
  const now = Date.now();
  pruneAudioCache(now);

  const objectUrl = URL.createObjectURL(blob);
  const item: CachedAudio = {
    blob,
    contentType,
    objectUrl,
    createdAt: now,
  };
  audioCache.set(key, item);
  return item;
}

export function useMessageSpeechAudio(messageId: string) {
  const key = `/v1/messages/${messageId}/speech`;

  const { trigger, data, error, isMutating, reset } = useSWRMutation<
    CachedAudio,
    any,
    string,
    MessageSpeechRequest
  >(
    key,
    async (_url, { arg }) => {
      const payload: MessageSpeechRequest = {
        model: arg?.model,
        voice: arg?.voice ?? "alloy",
        response_format: arg?.response_format ?? "mp3",
        speed: arg?.speed ?? 1.0,
        prompt_audio_id: arg?.prompt_audio_id,
      };
      if (!payload.model || !String(payload.model).trim()) {
        throw new Error("Missing TTS model");
      }

      const audioKey = buildAudioCacheKey(messageId, payload);
      const cached = getCachedAudio(audioKey);
      if (cached) return cached;

      const { blob, contentType } = await messageService.getMessageSpeechAudio(messageId, payload);
      return storeCachedAudio(audioKey, blob, contentType);
    },
    {
      revalidate: false,
      populateCache: false,
    }
  );

  return {
    getAudio: trigger,
    audio: data,
    error,
    loading: isMutating,
    reset,
  };
}
