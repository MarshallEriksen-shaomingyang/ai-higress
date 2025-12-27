const THINK_BLOCK_RE = /<think>[\s\S]*?<\/think>/gi;
const THINK_UNCLOSED_RE = /<think>[\s\S]*$/gi;
const THINK_CLOSE_TAG_RE = /<\/think>/gi;

export function sanitizeConversationTitle(value?: string): string {
  if (!value) return "";

  let title = value;
  // 先移除完整的 <think>...</think> 块
  title = title.replace(THINK_BLOCK_RE, " ");
  // 再移除未闭合的 <think>... 尾部（部分推理模型可能只输出开标签）
  title = title.replace(THINK_UNCLOSED_RE, " ");
  // 最后清理残留的 </think>
  title = title.replace(THINK_CLOSE_TAG_RE, " ");

  return title.replace(/\s+/g, " ").trim();
}

