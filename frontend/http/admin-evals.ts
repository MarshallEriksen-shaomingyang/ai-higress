import { httpClient } from "./client";
import type { AdminEvalItem, AdminEvalListResponse } from "@/lib/api-types";

export interface AdminEvalListParams {
  cursor?: string;
  limit?: number;
  status?: string;
  project_id?: string;
  assistant_id?: string;
}

export const adminEvalService = {
  async listEvals(params: AdminEvalListParams = {}): Promise<AdminEvalListResponse> {
    const response = await httpClient.get<AdminEvalListResponse>("/admin/evals", {
      params,
    });
    return response.data;
  },

  async getEval(evalId: string): Promise<AdminEvalItem> {
    const response = await httpClient.get<AdminEvalItem>(`/admin/evals/${evalId}`);
    return response.data;
  },
};

