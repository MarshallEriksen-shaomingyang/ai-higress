"use client";

import { useCallback, useRef } from "react";
import { useApiGet, useApiPost } from "./hooks";
import { swrFetcher } from "./fetcher";
import type {
  VideoGenerationRequest,
  VideoGenerationResponse,
  VideoGenerationTaskCreated,
  VideoGenerationTaskStatusResponse,
  VideoGenerationHistoryResponse,
} from "@/lib/api-types";

// Polling configuration with exponential backoff
const DEFAULT_INITIAL_POLL_INTERVAL = 1000; // Start at 1 second
const DEFAULT_MAX_POLL_INTERVAL = 5000; // Max 5 seconds
const DEFAULT_BACKOFF_MULTIPLIER = 1.5; // Increase by 50% each poll
const MAX_POLL_ATTEMPTS = 600; // 10 minutes max with backoff

// localStorage cache for completed tasks
const COMPLETED_TASKS_CACHE_KEY = "video_generation_completed_tasks";
const COMPLETED_TASKS_CACHE_TTL = 3600000; // 1 hour in milliseconds

interface CachedTask {
  status: VideoGenerationTaskStatusResponse;
  cachedAt: number;
}

function getCachedCompletedTask(taskId: string): VideoGenerationTaskStatusResponse | null {
  try {
    const cached = localStorage.getItem(`${COMPLETED_TASKS_CACHE_KEY}:${taskId}`);
    if (!cached) return null;

    const parsed: CachedTask = JSON.parse(cached);
    const now = Date.now();

    // Check if cache is still valid
    if (now - parsed.cachedAt > COMPLETED_TASKS_CACHE_TTL) {
      localStorage.removeItem(`${COMPLETED_TASKS_CACHE_KEY}:${taskId}`);
      return null;
    }

    return parsed.status;
  } catch {
    return null;
  }
}

function cacheCompletedTask(taskId: string, status: VideoGenerationTaskStatusResponse): void {
  try {
    const cached: CachedTask = {
      status,
      cachedAt: Date.now(),
    };
    localStorage.setItem(`${COMPLETED_TASKS_CACHE_KEY}:${taskId}`, JSON.stringify(cached));
  } catch {
    // Ignore localStorage errors (quota exceeded, etc.)
  }
}

interface UseVideoGenerationsOptions {
  /**
   * Whether to use async mode (default: true)
   * - true: Returns task ID immediately, use pollTaskStatus for results
   * - false: Waits for generation to complete (may timeout for long videos)
   */
  async?: boolean;
  /**
   * Initial polling interval in milliseconds (default: 1000)
   */
  initialPollInterval?: number;
  /**
   * Maximum polling interval in milliseconds (default: 5000)
   */
  maxPollInterval?: number;
  /**
   * Backoff multiplier for exponential backoff (default: 1.5)
   */
  backoffMultiplier?: number;
  /**
   * Maximum number of poll attempts (default: 600)
   */
  maxPollAttempts?: number;
  /**
   * Whether to use localStorage cache for completed tasks (default: true)
   */
  useLocalCache?: boolean;
  /**
   * Callback when task status changes
   */
  onStatusChange?: (status: VideoGenerationTaskStatusResponse) => void;
  /**
   * Callback when task completes successfully
   */
  onSuccess?: (result: VideoGenerationResponse) => void;
  /**
   * Callback when task fails
   */
  onError?: (error: { code: string; message: string }) => void;
}

export function useVideoGenerations(options: UseVideoGenerationsOptions = {}) {
  const {
    async: asyncMode = true,
    initialPollInterval = DEFAULT_INITIAL_POLL_INTERVAL,
    maxPollInterval = DEFAULT_MAX_POLL_INTERVAL,
    backoffMultiplier = DEFAULT_BACKOFF_MULTIPLIER,
    maxPollAttempts = MAX_POLL_ATTEMPTS,
    useLocalCache = true,
    onStatusChange,
    onSuccess,
    onError,
  } = options;

  // Sync mode hook
  const syncMutation = useApiPost<VideoGenerationResponse, VideoGenerationRequest>(
    "/v1/videos/generations?sync=true"
  );

  // Async mode hook
  const asyncMutation = useApiPost<VideoGenerationTaskCreated, VideoGenerationRequest>(
    "/v1/videos/generations"
  );

  // Polling state with current interval for backoff
  const pollingRef = useRef<{
    active: boolean;
    taskId: string | null;
    attempts: number;
    currentInterval: number;
    timeoutId: NodeJS.Timeout | null;
  }>({
    active: false,
    taskId: null,
    attempts: 0,
    currentInterval: initialPollInterval,
    timeoutId: null,
  });

  /**
   * Poll for task status until completion with exponential backoff
   */
  const pollTaskStatus = useCallback(
    async (taskId: string): Promise<VideoGenerationTaskStatusResponse> => {
      // Check localStorage cache first for completed tasks
      if (useLocalCache) {
        const cached = getCachedCompletedTask(taskId);
        if (cached && (cached.status === "succeeded" || cached.status === "failed")) {
          onStatusChange?.(cached);
          if (cached.status === "succeeded" && cached.result) {
            onSuccess?.(cached.result);
          }
          if (cached.status === "failed" && cached.error) {
            onError?.(cached.error);
          }
          return cached;
        }
      }

      pollingRef.current = {
        active: true,
        taskId,
        attempts: 0,
        currentInterval: initialPollInterval,
        timeoutId: null,
      };

      const poll = async (): Promise<VideoGenerationTaskStatusResponse> => {
        if (!pollingRef.current.active) {
          throw new Error("Polling cancelled");
        }

        pollingRef.current.attempts++;
        if (pollingRef.current.attempts > maxPollAttempts) {
          pollingRef.current.active = false;
          throw new Error("Polling timeout exceeded");
        }

        try {
          const status = (await swrFetcher.get(
            `/v1/videos/generations/${taskId}`
          )) as VideoGenerationTaskStatusResponse;

          onStatusChange?.(status);

          if (status.status === "succeeded") {
            pollingRef.current.active = false;
            // Cache completed task in localStorage
            if (useLocalCache) {
              cacheCompletedTask(taskId, status);
            }
            if (status.result) {
              onSuccess?.(status.result);
            }
            return status;
          }

          if (status.status === "failed") {
            pollingRef.current.active = false;
            // Cache failed task in localStorage
            if (useLocalCache) {
              cacheCompletedTask(taskId, status);
            }
            if (status.error) {
              onError?.(status.error);
            }
            return status;
          }

          // Still running, continue polling with exponential backoff
          const currentInterval = pollingRef.current.currentInterval;
          // Calculate next interval with backoff, capped at maxPollInterval
          pollingRef.current.currentInterval = Math.min(
            currentInterval * backoffMultiplier,
            maxPollInterval
          );

          return new Promise((resolve, reject) => {
            pollingRef.current.timeoutId = setTimeout(async () => {
              try {
                const result = await poll();
                resolve(result);
              } catch (e) {
                reject(e);
              }
            }, currentInterval);
          });
        } catch (error) {
          pollingRef.current.active = false;
          throw error;
        }
      };

      return poll();
    },
    [maxPollAttempts, initialPollInterval, maxPollInterval, backoffMultiplier, useLocalCache, onStatusChange, onSuccess, onError]
  );

  /**
   * Cancel ongoing polling
   */
  const cancelPolling = useCallback(() => {
    pollingRef.current.active = false;
    if (pollingRef.current.timeoutId) {
      clearTimeout(pollingRef.current.timeoutId);
      pollingRef.current.timeoutId = null;
    }
  }, []);

  /**
   * Generate video (async mode with polling)
   */
  const generateVideoAsync = useCallback(
    async (
      request: VideoGenerationRequest
    ): Promise<VideoGenerationTaskStatusResponse> => {
      // Create task
      const taskCreated = await asyncMutation.trigger(request);

      // Poll for completion
      return pollTaskStatus(taskCreated.task_id);
    },
    [asyncMutation, pollTaskStatus]
  );

  /**
   * Generate video (sync mode - waits for completion)
   */
  const generateVideoSync = useCallback(
    async (request: VideoGenerationRequest): Promise<VideoGenerationResponse> => {
      return syncMutation.trigger(request);
    },
    [syncMutation]
  );

  /**
   * Generate video using the configured mode
   */
  const generateVideo = useCallback(
    async (
      request: VideoGenerationRequest
    ): Promise<VideoGenerationResponse | VideoGenerationTaskStatusResponse> => {
      if (asyncMode) {
        return generateVideoAsync(request);
      }
      return generateVideoSync(request);
    },
    [asyncMode, generateVideoAsync, generateVideoSync]
  );

  /**
   * Get task status (one-time fetch, not polling)
   */
  const getTaskStatus = useCallback(
    async (taskId: string): Promise<VideoGenerationTaskStatusResponse> => {
      return (await swrFetcher.get(
        `/v1/videos/generations/${taskId}`
      )) as VideoGenerationTaskStatusResponse;
    },
    []
  );

  return {
    // Main API
    generateVideo,
    generateVideoAsync,
    generateVideoSync,

    // Polling
    pollTaskStatus,
    cancelPolling,
    getTaskStatus,

    // Current polling state
    isPolling: pollingRef.current.active,
    currentTaskId: pollingRef.current.taskId,

    // Loading states
    isGenerating: syncMutation.submitting || asyncMutation.submitting,

    // Errors
    error: syncMutation.error || asyncMutation.error,
  };
}

/**
 * Hook for fetching video generation history
 */
export function useVideoGenerationHistory(options: {
  limit?: number;
  offset?: number;
  status?: string;
} = {}) {
  const { limit = 20, offset = 0, status } = options;

  const params = new URLSearchParams();
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  if (status) {
    params.set("status", status);
  }

  const { data, error, loading, validating, refresh } = useApiGet<VideoGenerationHistoryResponse>(
    `/v1/videos/generations?${params.toString()}`,
    { strategy: "frequent" }
  );

  return {
    history: data?.items ?? [],
    total: data?.total ?? 0,
    hasMore: data?.has_more ?? false,
    error,
    loading,
    validating,
    refresh,
  };
}

export default useVideoGenerations;
