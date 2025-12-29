/**
 * 工作流自动化 API 服务
 * 对应后端 /v1/workflows 和 /v1/workflow-runs 接口
 */

import { httpClient } from '@/http/client';
import type {
  Workflow,
  WorkflowSpec,
  WorkflowRun,
  BridgeAgent,
} from '@/lib/workflow/types';

const API_BASE = '/v1';

// ==================== Workflow 模板 ====================

/**
 * 创建工作流模板
 */
export async function createWorkflow(spec: WorkflowSpec): Promise<Workflow> {
  const response = await httpClient.post<Workflow>(`${API_BASE}/workflows`, spec);
  return response.data;
}

/**
 * 获取工作流列表
 * TODO: 后端需要新增此接口
 */
export async function getWorkflows(): Promise<Workflow[]> {
  const response = await httpClient.get<Workflow[]>(`${API_BASE}/workflows`);
  return response.data;
}

/**
 * 获取单个工作流模板
 */
export async function getWorkflow(id: number): Promise<Workflow> {
  const response = await httpClient.get<Workflow>(`${API_BASE}/workflows/${id}`);
  return response.data;
}

// ==================== Workflow Run ====================

/**
 * 创建并启动工作流运行实例
 */
export async function createWorkflowRun(workflowId: number): Promise<WorkflowRun> {
  const response = await httpClient.post<WorkflowRun>(`${API_BASE}/workflow-runs`, {
    workflow_id: workflowId,
  });
  return response.data;
}

/**
 * 获取运行实例状态
 */
export async function getWorkflowRun(runId: number): Promise<WorkflowRun> {
  const response = await httpClient.get<WorkflowRun>(`${API_BASE}/workflow-runs/${runId}`);
  return response.data;
}

/**
 * 恢复暂停的运行实例（审批 / 重试）
 */
export async function resumeWorkflowRun(runId: number): Promise<WorkflowRun> {
  const response = await httpClient.post<WorkflowRun>(`${API_BASE}/workflow-runs/${runId}/resume`);
  return response.data;
}

/**
 * 取消运行实例
 */
export async function cancelWorkflowRun(runId: number): Promise<WorkflowRun> {
  const response = await httpClient.post<WorkflowRun>(`${API_BASE}/workflow-runs/${runId}/cancel`);
  return response.data;
}

/**
 * 连接 SSE 事件流
 * @param runId 运行实例 ID
 * @param onEvent 事件回调
 * @param onError 错误回调
 * @returns 关闭连接的函数
 */
export function subscribeWorkflowRunEvents(
  runId: number,
  onEvent: (event: { type: string; data: unknown }) => void,
  onError?: (error: Error) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/workflow-runs/${runId}/events`);

  eventSource.addEventListener('run.event', (e) => {
    try {
      const data = JSON.parse(e.data);
      onEvent({ type: 'run.event', data });
    } catch (err) {
      console.error('Failed to parse SSE event:', err);
    }
  });

  eventSource.onerror = (err) => {
    console.error('SSE connection error:', err);
    onError?.(new Error('SSE connection failed'));
  };

  // 返回关闭函数
  return () => {
    eventSource.close();
  };
}

// ==================== Bridge Agents & Tools ====================

/**
 * 获取可用的 Bridge Agents 列表
 * TODO: 后端需要新增此接口，或从现有 Bridge API 扩展
 */
export async function getBridgeAgents(): Promise<BridgeAgent[]> {
  // 临时实现：返回模拟数据
  // 生产环境应该调用实际接口
  const response = await httpClient.get<BridgeAgent[]>(`${API_BASE}/bridge/agents`);
  return response.data;
}
