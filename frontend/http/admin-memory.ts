import { httpClient } from './client';

// Admin Memory Types
export interface AdminMemoryItem {
  id: string;
  content: string;
  categories: string[] | null;
  keywords: string[] | null;
  created_at: string | null;
  scope: 'user' | 'system';
  approved: boolean;
  submitted_by_user_id: string | null;
  source_id: string | null;
}

export interface AdminMemoryListResponse {
  items: AdminMemoryItem[];
  next_offset: string | null;
  total: number | null;
}

export interface AdminMemoryApproveRequest {
  project_id: string;
  content?: string;
  categories?: string[];
  keywords?: string[];
}

export interface AdminMemoryCreateRequest {
  project_id: string;
  content: string;
  categories: string[];
  keywords: string[];
}

// Admin Memory Service
export const adminMemoryService = {
  /**
   * List pending system memory candidates (scope=system, approved=false)
   */
  listCandidates: async (
    limit: number = 20,
    offset?: string
  ): Promise<AdminMemoryListResponse> => {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (offset) {
      params.set('offset', offset);
    }
    const response = await httpClient.get(`/admin/memories/candidates?${params.toString()}`);
    return response.data;
  },

  /**
   * List published system memories (scope=system, approved=true)
   */
  listPublished: async (
    limit: number = 20,
    offset?: string
  ): Promise<AdminMemoryListResponse> => {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    if (offset) {
      params.set('offset', offset);
    }
    const response = await httpClient.get(`/admin/memories/published?${params.toString()}`);
    return response.data;
  },

  /**
   * Approve a system memory candidate
   */
  approve: async (
    pointId: string,
    data: AdminMemoryApproveRequest
  ): Promise<AdminMemoryItem> => {
    const response = await httpClient.post(`/admin/memories/${pointId}/approve`, data);
    return response.data;
  },

  /**
   * Create a new system memory (directly published)
   */
  create: async (data: AdminMemoryCreateRequest): Promise<AdminMemoryItem> => {
    const response = await httpClient.post('/admin/memories', data);
    return response.data;
  },

  /**
   * Delete a system memory (candidate or published)
   */
  delete: async (pointId: string): Promise<void> => {
    await httpClient.delete(`/admin/memories/${pointId}`);
  },
};
