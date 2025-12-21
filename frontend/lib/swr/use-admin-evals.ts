"use client";

import useSWR from "swr";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { adminEvalService, type AdminEvalListParams } from "@/http/admin-evals";
import type { AdminEvalItem } from "@/lib/api-types";
import { useAuthStore } from "@/lib/stores/auth-store";
import { swrKeys } from "./keys";

export type AdminEvalStatusFilter = "all" | "running" | "ready" | "rated";

export interface UseAdminEvalsParams {
  limit?: number;
  status?: AdminEvalStatusFilter;
  projectId?: string;
  assistantId?: string;
}

export function useAdminEvals(params: UseAdminEvalsParams = {}) {
  const user = useAuthStore((state) => state.user);
  const isSuperUser = user?.is_superuser === true;

  const limit = params.limit ?? 30;
  const status = params.status ?? "all";
  const projectId = (params.projectId || "").trim();
  const assistantId = (params.assistantId || "").trim();

  const filterKey = useMemo(
    () => JSON.stringify({ limit, status, projectId, assistantId }),
    [assistantId, limit, projectId, status]
  );

  const [cursor, setCursor] = useState<string | null>(null);
  const [items, setItems] = useState<AdminEvalItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const lastFilterKeyRef = useRef<string>(filterKey);
  useEffect(() => {
    if (lastFilterKeyRef.current === filterKey) return;
    lastFilterKeyRef.current = filterKey;
    setCursor(null);
    setItems([]);
    setNextCursor(null);
  }, [filterKey]);

  const requestParams: AdminEvalListParams = useMemo(() => {
    const out: AdminEvalListParams = {
      limit,
      cursor: cursor ?? undefined,
    };
    if (status !== "all") out.status = status;
    if (projectId) out.project_id = projectId;
    if (assistantId) out.assistant_id = assistantId;
    return out;
  }, [assistantId, cursor, limit, projectId, status]);

  const swrKey = isSuperUser ? [swrKeys.adminEvals(), requestParams] : null;
  const { data, error, isLoading, mutate } = useSWR(
    swrKey,
    async ([, p]) => adminEvalService.listEvals(p as AdminEvalListParams),
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
    }
  );

  useEffect(() => {
    if (!data) return;
    setNextCursor(data.next_cursor ?? null);
    setItems((prev) => {
      if (cursor === null) return data.items ?? [];
      const seen = new Set(prev.map((it) => it.eval_id));
      const merged = [...prev];
      for (const it of data.items ?? []) {
        if (seen.has(it.eval_id)) continue;
        merged.push(it);
      }
      return merged;
    });
  }, [cursor, data]);

  const loadMore = useCallback(() => {
    if (!nextCursor) return;
    if (isLoading) return;
    setCursor(nextCursor);
  }, [isLoading, nextCursor]);

  const refresh = useCallback(() => mutate(), [mutate]);

  return {
    items,
    nextCursor,
    loading: isLoading,
    error,
    refresh,
    loadMore,
    isSuperUser,
  };
}

