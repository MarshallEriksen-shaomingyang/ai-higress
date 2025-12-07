"use client";

import { useApiGet } from "./hooks";
import type {
  LogicalModelsResponse,
  LogicalModelUpstreamsResponse,
} from "@/lib/api-types";

/**
 * 获取所有逻辑模型列表（从 /logical-models）
 */
export const useLogicalModels = () => {
  const { data, error, loading, refresh } =
    useApiGet<LogicalModelsResponse>("/logical-models", {
      strategy: "frequent",
    });

  return {
    models: data?.models ?? [],
    total: data?.total ?? 0,
    loading,
    error,
    refresh,
  };
};

/**
 * 获取单个逻辑模型的上游列表
 */
export const useLogicalModelUpstreams = (logicalId: string | null) => {
  const { data, error, loading, refresh } =
    useApiGet<LogicalModelUpstreamsResponse>(
      logicalId ? `/logical-models/${logicalId}/upstreams` : null,
      {
        strategy: "frequent",
        revalidateOnFocus: false,
      }
    );

  return {
    upstreams: data?.upstreams ?? [],
    loading,
    error,
    refresh,
  };
};

