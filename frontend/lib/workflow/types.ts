/**
 * 工作流自动化类型定义
 * 对应后端 API 结构
 */

export type WorkflowStatus = 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'paused';
export type PausedReason = 'awaiting_approval' | 'step_failed' | 'engine_interrupted';

// 工作流步骤定义
export interface WorkflowStep {
  agent_id: string;
  tool_name: string;
  tool_arguments: Record<string, unknown>;
  require_approval?: boolean;
  on_error?: 'pause' | 'continue';
}

// 工作流规格
export interface WorkflowSpec {
  name: string;
  description?: string;
  steps: WorkflowStep[];
}

// 工作流模板
export interface Workflow {
  id: number;
  name: string;
  description: string | null;
  spec: WorkflowSpec;
  created_at: string;
  updated_at: string;
}

// 步骤执行状态
export interface StepState {
  step_index: number;
  status: StepStatus;
  attempts: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  log_preview: string | null;
  result_summary: Record<string, unknown> | null;
}

// 工作流运行实例
export interface WorkflowRun {
  id: number;
  workflow_id: number;
  status: WorkflowStatus;
  current_step_index: number;
  paused_reason: PausedReason | null;
  steps_state: StepState[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  last_activity_at: string;
  spec_snapshot: WorkflowSpec;
}

// 工作流运行事件（SSE）
export interface WorkflowRunEvent {
  type: 'run.event';
  event_type:
    | 'run.started'
    | 'run.completed'
    | 'run.failed'
    | 'run.cancelled'
    | 'run.paused'
    | 'run.resumed'
    | 'step.started'
    | 'step.completed'
    | 'step.failed'
    | 'step.paused'
    | 'tool.log';
  run_id: number;
  step_index?: number;
  reason?: string;
  log?: string;
  timestamp: string;
}

// Bridge Agent 和 Tool 信息（用于工具库显示）
export interface BridgeAgent {
  id: string;
  name: string;
  description: string;
  tools: BridgeTool[];
}

export interface BridgeTool {
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, {
      type: string;
      description?: string;
      required?: boolean;
    }>;
    required?: string[];
  };
  risk_level?: 'safe' | 'caution' | 'dangerous';
}

// UI 状态
export interface ComposerState {
  workflow: Partial<WorkflowSpec>;
  selectedStepIndex: number | null;
  isEditing: boolean;
}

export interface MonitorState {
  run: WorkflowRun | null;
  events: WorkflowRunEvent[];
  isConnected: boolean;
  autoScroll: boolean;
}
