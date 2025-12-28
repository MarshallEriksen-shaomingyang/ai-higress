// 后端响应类型定义文件
// 此文件定义后端 API 实际返回的数据结构
// 这些类型与前端使用的类型（api-types.ts）存在差异，需要通过规范化函数转换

// ============= 助手相关 =============

/**
 * 后端实际返回的助手类型
 * 与前端类型的差异：
 * - archived_at: string | null（后端使用 datetime 或 null）
 * - 前端使用 archived: boolean
 */
export interface AssistantBackend {
  assistant_id: string;
  project_id: string;
  name: string;
  system_prompt?: string;
  default_logical_model: string;
  title_logical_model?: string | null;
  model_preset?: Record<string, any>;
  archived_at?: string | null; // 列表接口可能省略该字段
  created_at: string;
  updated_at: string;
}

export interface AssistantsResponseBackend {
  items: AssistantBackend[];
  next_cursor?: string;
}

// ============= 会话相关 =============

/**
 * 后端实际返回的会话类型
 * 与前端类型的差异：
 * - archived_at: string | null（后端使用 datetime 或 null）
 * - 前端使用 archived: boolean
 */
export interface ConversationBackend {
  conversation_id: string;
  assistant_id: string;
  project_id: string;
  title?: string;
  archived_at: string | null; // 后端使用 datetime 或 null
  last_activity_at: string;
  summary_text?: string | null;
  summary_until_sequence?: number;
  summary_updated_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConversationsResponseBackend {
  items: ConversationBackend[];
  next_cursor?: string;
}

// ============= 消息相关 =============

export interface TextMessageContentBackend {
  type: "text";
  text: string;
}

export interface ImageMessageContentBackend {
  type: "image" | "image_url" | "input_image";
  image_url?: string | { url?: string };
  text?: string;
}

export interface FileMessageContentBackend {
  type: "file";
  file_url?: string;
  text?: string;
}

export interface ImageGenerationMessageContentBackend {
  type: "image_generation";
  status: "pending" | "succeeded" | "failed";
  prompt: string;
  params: Record<string, any>;
  images: Array<{
    url?: string;
    object_key?: string | null;
    b64_json?: string;
    revised_prompt?: string | null;
  }>;
  error?: string;
  created?: number;
}

/**
 * 消息内容结构
 * 后端返回的是结构化对象，而非字符串
 */
export type MessageContent =
  | TextMessageContentBackend
  | ImageMessageContentBackend
  | FileMessageContentBackend
  | ImageGenerationMessageContentBackend
  | Record<string, any>;

/**
 * 后端实际返回的消息类型
 * 与前端类型的差异：
 * - content: MessageContent（结构化对象）
 * - 前端使用 content: string
 */
export interface MessageBackend {
  message_id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: MessageContent; // 结构化对象
  created_at: string;
}

/**
 * 后端实际返回的 run 摘要类型
 * 与前端类型的差异：
 * - latency_ms: number（后端使用 latency_ms）
 * - cost_credits: number（后端使用 cost_credits）
 * - 前端使用 latency 和 cost
 */
export interface RunSummaryBackend {
  run_id: string;
  requested_logical_model: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
  output_preview?: string;
  latency_ms?: number; // 后端使用 latency_ms
  cost_credits?: number; // 后端使用 cost_credits
  error_code?: string;
  tool_invocations?: Array<{
    req_id: string;
    agent_id: string;
    tool_name: string;
    tool_call_id?: string | null;
    state?: 'running' | 'done' | 'failed' | 'timeout' | 'canceled';
    duration_ms?: number;
    ok?: boolean;
    canceled?: boolean;
    exit_code?: number;
    error?: Record<string, any> | null;
    result_preview?: string | null;
  }>;
}

/**
 * 后端实际返回的 run 详情类型
 * 与前端类型的差异：
 * - request_payload: Record<string, any>（后端使用 request_payload）
 * - response_payload: Record<string, any>（后端使用 response_payload）
 * - 前端使用 request 和 response
 */
export interface RunDetailBackend extends RunSummaryBackend {
  request_payload: Record<string, any>; // 后端使用 request_payload
  response_payload: Record<string, any>; // 后端使用 response_payload
  output_text: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
}

/**
 * 后端实际返回的消息列表结构
 * 与前端类型的差异：
 * - 每条消息包含 runs 数组（而非单个 run）
 * - messages 接口当前返回“扁平化 message 字段”（不再嵌套在 message 对象里）
 */
export interface MessagesResponseBackend {
  items: Array<{
    message_id: string;
    role: 'user' | 'assistant';
    content: MessageContent;
    created_at: string;
    runs: RunSummaryBackend[]; // 后端返回 runs 数组
  }>;
  next_cursor?: string;
}

/**
 * 后端实际返回的发送消息响应
 * 与前端类型的差异：
 * - baseline_run 使用 RunSummaryBackend 类型
 */
export interface SendMessageResponseBackend {
  message_id: string;
  baseline_run: RunSummaryBackend;
}

// ============= 评测相关 =============

/**
 * 后端实际返回的挑战者 run 类型
 * 与前端类型的差异：
 * - latency_ms: number（后端使用 latency_ms）
 * - 前端使用 latency
 */
export interface ChallengerRunBackend {
  run_id: string;
  requested_logical_model: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  output_preview?: string;
  latency_ms?: number; // 后端使用 latency_ms
  error_code?: string;
}

/**
 * 后端实际返回的评测响应
 * 与前端类型的差异：
 * - challengers 使用 ChallengerRunBackend 类型
 */
export interface EvalResponseBackend {
  eval_id: string;
  status: 'running' | 'ready' | 'rated';
  baseline_run_id: string;
  challengers: ChallengerRunBackend[];
  explanation: {
    summary: string;
    evidence?: {
      policy_version?: string;
      exploration?: boolean;
      [key: string]: any;
    };
  };
  created_at: string;
}
