// 聊天助手系统规范化函数
// 此文件提供数据转换函数，将后端响应转换为前端使用的类型

// 重新导出后端类型，供 HTTP 层使用
export type {
  AssistantBackend,
  AssistantsResponseBackend,
  ConversationBackend,
  ConversationsResponseBackend,
  MessageBackend,
  MessageContent,
  RunSummaryBackend,
  RunDetailBackend,
  MessagesResponseBackend,
  SendMessageResponseBackend,
  ChallengerRunBackend,
  EvalResponseBackend,
} from '@/lib/api-types-backend';

import type {
  AssistantBackend,
  AssistantsResponseBackend,
  ConversationBackend,
  ConversationsResponseBackend,
  MessageBackend,
  MessageContent,
  RunSummaryBackend,
  RunDetailBackend,
  MessagesResponseBackend,
  SendMessageResponseBackend,
  ChallengerRunBackend,
  EvalResponseBackend,
} from '@/lib/api-types-backend';
import type {
  Assistant,
  AssistantsResponse,
  Conversation,
  ConversationsResponse,
  Message,
  ImageGenerationRequest,
  RunSummary,
  RunDetail,
  MessagesResponse,
  SendMessageResponse,
  ChallengerRun,
  EvalResponse,
} from '@/lib/api-types';

// ============= 助手相关规范化函数 =============

/**
 * 规范化助手数据
 * 将后端的 archived_at 转换为前端的 archived boolean
 * 
 * @param backend - 后端返回的助手数据
 * @returns 前端使用的助手数据
 */
export function normalizeAssistant(backend: AssistantBackend): Assistant {
  return {
    assistant_id: backend.assistant_id,
    project_id: backend.project_id,
    name: backend.name,
    system_prompt: backend.system_prompt,
    default_logical_model: backend.default_logical_model,
    title_logical_model: backend.title_logical_model ?? null,
    model_preset: backend.model_preset,
    archived: backend.archived_at != null, // 转换为 boolean（兼容 undefined）
    created_at: backend.created_at,
    updated_at: backend.updated_at,
  };
}

/**
 * 规范化助手列表响应
 * 
 * @param backend - 后端返回的助手列表响应
 * @returns 前端使用的助手列表响应
 */
export function normalizeAssistantsResponse(
  backend: AssistantsResponseBackend
): AssistantsResponse {
  return {
    items: backend.items.map(normalizeAssistant),
    next_cursor: backend.next_cursor,
  };
}

// ============= 会话相关规范化函数 =============

/**
 * 规范化会话数据
 * 将后端的 archived_at 转换为前端的 archived boolean
 * 
 * @param backend - 后端返回的会话数据
 * @returns 前端使用的会话数据
 */
export function normalizeConversation(backend: ConversationBackend): Conversation {
  return {
    conversation_id: backend.conversation_id,
    assistant_id: backend.assistant_id,
    project_id: backend.project_id,
    title: backend.title,
    archived: backend.archived_at != null, // 转换为 boolean（兼容 undefined）
    last_activity_at: backend.last_activity_at,
    summary_text: backend.summary_text ?? null,
    summary_until_sequence:
      typeof backend.summary_until_sequence === "number" ? backend.summary_until_sequence : undefined,
    summary_updated_at: backend.summary_updated_at ?? null,
    created_at: backend.created_at,
    updated_at: backend.updated_at,
  };
}

/**
 * 规范化会话列表响应
 * 
 * @param backend - 后端返回的会话列表响应
 * @returns 前端使用的会话列表响应
 */
export function normalizeConversationsResponse(
  backend: ConversationsResponseBackend
): ConversationsResponse {
  return {
    items: backend.items.map(normalizeConversation),
    next_cursor: backend.next_cursor,
  };
}

// ============= 消息相关规范化函数 =============

/**
 * 规范化消息内容
 * 将后端的结构化 content 转换为前端的字符串
 * 
 * @param content - 后端返回的消息内容结构
 * @returns 前端使用的消息内容字符串
 */
function extractUrl(value: unknown): string | null {
  if (typeof value === 'string') {
    const trimmed = value.trim();
    return trimmed || null;
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>;
    const nested = record.url ?? record.image_url ?? record.imageUrl;
    if (typeof nested === 'string') {
      const trimmed = nested.trim();
      if (trimmed) return trimmed;
    }
  }
  return null;
}

function stringifyContentSegment(segment: any): string {
  if (!segment) return '';
  if (typeof segment === 'string') return segment;
  if (typeof segment !== 'object') return '';

  const type = typeof segment.type === 'string' ? segment.type.toLowerCase() : '';
  const text = typeof segment.text === 'string' ? segment.text : '';

  if (text && (!type || type === 'text')) {
    return text;
  }

  const imageUrl =
    extractUrl(segment.image_url) ??
    extractUrl(segment.imageUrl);
  if (imageUrl && (type === 'image' || type === 'image_url' || type === 'input_image')) {
    return imageUrl;
  }

  const fileUrl = extractUrl(segment.file_url) ?? extractUrl(segment.fileUrl);
  if (fileUrl && type === 'file') {
    return `[文件: ${fileUrl}]`;
  }

  const audioUrl =
    extractUrl(segment.input_audio) ??
    extractUrl(segment.inputAudio) ??
    extractUrl(segment.audio_url) ??
    extractUrl(segment.audioUrl);
  if (type === "input_audio" || type === "audio") {
    return audioUrl ? `[语音: ${audioUrl}]` : "[语音]";
  }

  if (text) {
    return text;
  }
  if (imageUrl) {
    return imageUrl;
  }
  if (fileUrl) {
    return `[文件: ${fileUrl}]`;
  }
  return '';
}

function toRecord(value: unknown): Record<string, any> | null {
  if (!value || typeof value !== "object") return null;
  return value as Record<string, any>;
}

function normalizeImageGenerationContent(content: unknown): Message["image_generation"] | null {
  const record = toRecord(content);
  if (!record) return null;
  if (record.type !== "image_generation") return null;

  const status =
    record.status === "pending" || record.status === "succeeded" || record.status === "failed"
      ? (record.status as "pending" | "succeeded" | "failed")
      : "pending";
  const prompt = typeof record.prompt === "string" ? record.prompt : "";
  const paramsRaw = toRecord(record.params) ?? {};

  const model = typeof paramsRaw.model === "string" ? paramsRaw.model : "";
  const n = typeof paramsRaw.n === "number" ? paramsRaw.n : 1;
  const size = typeof paramsRaw.size === "string" ? paramsRaw.size : undefined;
  const response_format =
    paramsRaw.response_format === "b64_json" || paramsRaw.response_format === "url"
      ? (paramsRaw.response_format as "url" | "b64_json")
      : undefined;

  const params: ImageGenerationRequest = {
    model,
    prompt,
    ...(typeof n === "number" ? { n } : {}),
    ...(size ? { size } : {}),
    ...(response_format ? { response_format } : {}),
  };

  const imagesRaw = Array.isArray(record.images) ? record.images : [];
  const images = imagesRaw
    .map((img) => {
      const r = toRecord(img);
      if (!r) return null;
      return {
        url: typeof r.url === "string" ? r.url : undefined,
        object_key: typeof r.object_key === "string" ? r.object_key : (r.object_key === null ? null : undefined),
        b64_json: typeof r.b64_json === "string" ? r.b64_json : undefined,
        revised_prompt: typeof r.revised_prompt === "string" ? r.revised_prompt : (r.revised_prompt === null ? null : undefined),
      };
    })
    .filter((x): x is NonNullable<typeof x> => !!x);

  return {
    type: "image_generation",
    status,
    prompt,
    params,
    images,
    error: typeof record.error === "string" ? record.error : undefined,
    created: typeof record.created === "number" ? record.created : undefined,
  };
}

export function normalizeMessageContent(content: MessageContent | unknown): string {
  // 兼容后端返回字符串或未知结构，尽量保留已有文本，避免回流时把流式内容清空
  if (typeof content === 'string') {
    return content;
  }

  // 文生图消息：不强行塞进文本（由 UI 专用组件渲染），这里只给一个稳定的兜底。
  const imgGen = normalizeImageGenerationContent(content);
  if (imgGen) {
    if (imgGen.status === "failed") return "[图片生成失败]";
    if (imgGen.status === "pending") return "[图片生成中]";
    return "[图片]";
  }

  if (Array.isArray(content)) {
    const merged = content
      .map((item) => stringifyContentSegment(item))
      .filter(Boolean)
      .join('\n\n');
    if (merged) return merged;
  }

  if (!content || typeof content !== 'object') return '';

  const record = content as Record<string, unknown>;
  const inputAudio = record["input_audio"];
  if (inputAudio && typeof inputAudio === "object") {
    const text = typeof record.text === "string" ? record.text.trim() : "";
    if (!text) return "[语音]";
  }
  if (typeof record.text === 'string' && !record.type) {
    return record.text;
  }

  const single = stringifyContentSegment(record);
  if (single) return single;

  return '';
}

/**
 * 规范化消息数据
 * 将后端的结构化 content 转换为前端的字符串
 * 
 * @param backend - 后端返回的消息数据
 * @returns 前端使用的消息数据
 */
export function normalizeMessage(backend: MessageBackend): Message {
  const image_generation = normalizeImageGenerationContent(backend.content);
  return {
    message_id: backend.message_id,
    conversation_id: backend.conversation_id,
    role: backend.role,
    content: normalizeMessageContent(backend.content), // 转换为字符串
    image_generation: image_generation ?? undefined,
    created_at: backend.created_at,
  };
}

/**
 * 规范化 run 摘要数据
 * 映射字段名称：latency_ms -> latency, cost_credits -> cost
 * 
 * @param backend - 后端返回的 run 摘要数据
 * @returns 前端使用的 run 摘要数据
 */
export function normalizeRunSummary(backend: RunSummaryBackend): RunSummary {
  return {
    run_id: backend.run_id,
    requested_logical_model: backend.requested_logical_model,
    status: backend.status,
    output_preview: backend.output_preview,
    latency: backend.latency_ms, // 映射字段名
    error_code: backend.error_code,
    tool_invocations: Array.isArray(backend.tool_invocations) ? backend.tool_invocations : undefined,
  };
}

/**
 * 规范化 run 详情数据
 * 映射字段名称：request_payload -> request, response_payload -> response
 * 
 * @param backend - 后端返回的 run 详情数据
 * @returns 前端使用的 run 详情数据
 */
export function normalizeRunDetail(backend: RunDetailBackend): RunDetail {
  return {
    ...normalizeRunSummary(backend),
    request: backend.request_payload, // 映射字段名
    response: backend.response_payload, // 映射字段名
    output_text: backend.output_text,
    input_tokens: backend.input_tokens,
    output_tokens: backend.output_tokens,
    total_tokens: backend.total_tokens,
    cost: backend.cost_credits, // 映射字段名
  };
}

/**
 * 规范化消息列表响应
 * 处理 runs 数组和消息内容
 * 
 * @param backend - 后端返回的消息列表响应
 * @returns 前端使用的消息列表响应
 */
export function normalizeMessagesResponse(
  backend: MessagesResponseBackend,
  conversationId: string
): MessagesResponse {
  return {
    items: backend.items.map((item) => {
      const image_generation = normalizeImageGenerationContent(item.content);
      const normalizedMessage: Message = {
        message_id: item.message_id,
        conversation_id: conversationId,
        role: item.role,
        content: normalizeMessageContent(item.content),
        image_generation: image_generation ?? undefined,
        created_at: item.created_at,
      };

      const normalizedRuns = (item.runs ?? []).map(normalizeRunSummary);

      // 前端列表目前只消费单个 run（用于展示/详情/评测入口）
      const run = normalizedRuns.length > 0 ? normalizedRuns[0] : undefined;
      
      return {
        message: normalizedMessage,
        run,
        runs: normalizedRuns,
      };
    }),
    next_cursor: backend.next_cursor,
  };
}

/**
 * 规范化发送消息响应
 * 
 * @param backend - 后端返回的发送消息响应
 * @returns 前端使用的发送消息响应
 */
export function normalizeSendMessageResponse(
  backend: SendMessageResponseBackend
): SendMessageResponse {
  return {
    message_id: backend.message_id,
    baseline_run: normalizeRunSummary(backend.baseline_run),
  };
}

// ============= 评测相关规范化函数 =============

/**
 * 规范化挑战者 run 数据
 * 映射字段名称：latency_ms -> latency
 * 
 * @param backend - 后端返回的挑战者 run 数据
 * @returns 前端使用的挑战者 run 数据
 */
export function normalizeChallengerRun(backend: ChallengerRunBackend): ChallengerRun {
  return {
    run_id: backend.run_id,
    requested_logical_model: backend.requested_logical_model,
    status: backend.status,
    output_preview: backend.output_preview,
    latency: backend.latency_ms, // 映射字段名
    error_code: backend.error_code,
  };
}

/**
 * 规范化评测响应
 * 
 * @param backend - 后端返回的评测响应
 * @returns 前端使用的评测响应
 */
export function normalizeEvalResponse(backend: EvalResponseBackend): EvalResponse {
  return {
    eval_id: backend.eval_id,
    status: backend.status,
    baseline_run_id: backend.baseline_run_id,
    challengers: backend.challengers.map(normalizeChallengerRun),
    explanation: backend.explanation,
    created_at: backend.created_at,
  };
}
