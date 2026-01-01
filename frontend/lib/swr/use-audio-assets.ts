"use client";

import useSWR from "swr";

import { audioService, type AudioAssetListResponse } from "@/http/audio";
import { cacheStrategies } from "@/lib/swr/cache";

export function useAudioAssets(params?: { visibility?: "all" | "private" | "public"; limit?: number }) {
  const key = `/v1/audio-assets?visibility=${params?.visibility ?? "all"}&limit=${params?.limit ?? 50}`;
  const { data, error, isLoading, mutate } = useSWR<AudioAssetListResponse>(
    key,
    () => audioService.listAudioAssets(params),
    cacheStrategies.frequent
  );

  return {
    items: data?.items ?? [],
    isLoading,
    error,
    mutate,
  };
}

