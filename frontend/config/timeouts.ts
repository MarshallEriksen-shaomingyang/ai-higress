// 集中管理前端请求相关的超时配置，便于统一调整
export const HTTP_DEFAULT_TIMEOUT_MS = 60_000;

// 聊天相关长耗时接口
export const SEND_MESSAGE_TIMEOUT_MS = 900_000;
export const RUN_DETAIL_TIMEOUT_MS = 900_000;

// Bridge（MCP 工具）相关
// 注意：这是“工具执行超时”而不是前端 HTTP 超时；会透传到后端再下发给 Bridge Gateway/Agent。
export const BRIDGE_TOOL_TIMEOUT_MS = 600_000;

// Eval 相关（非流式创建时可能较慢）
export const CREATE_EVAL_TIMEOUT_MS = 600_000;
