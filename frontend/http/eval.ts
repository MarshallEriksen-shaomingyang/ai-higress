import { httpClient } from './client';
import type {
  CreateEvalRequest,
  EvalResponse,
  SubmitRatingRequest,
  RatingResponse,
} from '@/lib/api-types';
import {
  normalizeEvalResponse,
  type EvalResponseBackend,
} from '@/lib/normalizers/chat-normalizers';
import { CREATE_EVAL_TIMEOUT_MS } from '@/config/timeouts';

/**
 * 评测服务 HTTP client
 * 提供评测创建、查询和评分提交功能
 */
export const evalService = {
  /**
   * 创建评测
   * 基于 baseline run 触发推荐评测
   */
  async createEval(data: CreateEvalRequest): Promise<EvalResponse> {
    // 验证 message_id 必填
    if (!data.message_id) {
      throw new Error('message_id is required to create eval');
    }
    const response = await httpClient.post<EvalResponseBackend>('/v1/evals', data, {
      timeout: CREATE_EVAL_TIMEOUT_MS,
    });
    return normalizeEvalResponse(response.data);
  },

  /**
   * 获取评测状态
   * 查询评测的当前状态和所有 challenger runs 的状态
   */
  async getEval(evalId: string): Promise<EvalResponse> {
    const response = await httpClient.get<EvalResponseBackend>(`/v1/evals/${evalId}`);
    return normalizeEvalResponse(response.data);
  },

  /**
   * 提交评测评分
   * 选择最佳模型并提交原因标签
   */
  async submitRating(evalId: string, data: SubmitRatingRequest): Promise<RatingResponse> {
    const response = await httpClient.post<RatingResponse>(
      `/v1/evals/${evalId}/rating`,
      data
    );
    return response.data;
  },
};
