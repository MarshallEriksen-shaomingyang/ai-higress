import { httpClient } from "./client";
import type {
  LogicalModel as LogicalModelApi,
  LogicalModelUpstream,
  LogicalModelsResponse,
  LogicalModelUpstreamsResponse,
} from "@/lib/api-types";

// 兼容旧命名，保持其他模块的导入不变
export type LogicalModel = LogicalModelApi;
export type UpstreamModel = LogicalModelUpstream;
export type UpstreamsResponse = LogicalModelUpstreamsResponse;

// 逻辑模型服务
export const logicalModelService = {
  // 获取逻辑模型列表
  getLogicalModels: async (): Promise<LogicalModelsResponse> => {
    const response = await httpClient.get("/logical-models");
    return response.data;
  },

  // 获取逻辑模型详情
  getLogicalModel: async (logicalModelId: string): Promise<LogicalModel> => {
    const response = await httpClient.get(`/logical-models/${logicalModelId}`);
    return response.data;
  },

  // 获取逻辑模型上游
  getLogicalModelUpstreams: async (
    logicalModelId: string
  ): Promise<UpstreamsResponse> => {
    const response = await httpClient.get(
      `/logical-models/${logicalModelId}/upstreams`
    );
    return response.data;
  },
};
