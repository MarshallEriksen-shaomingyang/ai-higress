package protocol

type HelloPayload struct {
	AgentMeta map[string]string `json:"agent_meta,omitempty"`
	Resume    *ResumePayload    `json:"resume,omitempty"`
}

type ResumePayload struct {
	PendingResultReqIDs []string `json:"pending_result_req_ids,omitempty"`
}

type AuthPayload struct {
	Token             string `json:"token,omitempty"`
	DeviceFingerprint string `json:"device_fingerprint,omitempty"`
}

type ToolsPayload struct {
	Tools []ToolDescriptor `json:"tools"`
}

type ToolDescriptor struct {
	Name        string            `json:"name"`
	Description string            `json:"description,omitempty"`
	InputSchema map[string]any    `json:"input_schema,omitempty"`
	Meta        map[string]string `json:"meta,omitempty"`
}

type InvokePayload struct {
	Tool      ToolCall      `json:"tool"`
	TimeoutMs int           `json:"timeout_ms,omitempty"`
	Stream    StreamOptions `json:"stream,omitempty"`
}

type StreamOptions struct {
	Enabled bool `json:"enabled"`
}

type ToolCall struct {
	Name string         `json:"name"`
	Args map[string]any `json:"args,omitempty"`
}

type InvokeAckPayload struct {
	Accepted bool   `json:"accepted"`
	Reason   string `json:"reason,omitempty"`
}

type ChunkPayload struct {
	StreamID     string `json:"stream_id,omitempty"`
	Channel      string `json:"channel"`
	Data         string `json:"data"`
	DroppedBytes int64  `json:"dropped_bytes,omitempty"`
	DroppedLines int64  `json:"dropped_lines,omitempty"`
}

type ResultPayload struct {
	OK       bool         `json:"ok"`
	ExitCode int          `json:"exit_code,omitempty"`
	Canceled bool         `json:"canceled,omitempty"`
	Result   any          `json:"result_json,omitempty"`
	Error    *ResultError `json:"error,omitempty"`
}

type ResultError struct {
	Message string         `json:"message"`
	Code    string         `json:"code,omitempty"`
	Details map[string]any `json:"details,omitempty"`
}

type CancelPayload struct {
	Reason string `json:"reason,omitempty"`
}

type CancelAckPayload struct {
	WillCancel bool   `json:"will_cancel"`
	Reason     string `json:"reason,omitempty"`
}
