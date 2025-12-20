package mcpbridge

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"bridge/internal/config"
	"bridge/internal/logging"
	"bridge/internal/protocol"

	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
)

var validNameRe = regexp.MustCompile(`[^a-zA-Z0-9_]+`)

type ProgressEvent struct {
	ReqID      string
	ServerName string
	Message    string
	Progress   float64
	Total      float64
}

type Aggregator struct {
	logger logging.Logger

	mu        sync.RWMutex
	servers   map[string]*serverClient
	tools     map[string]toolRef
	toolDescs map[string]protocol.ToolDescriptor

	progressCh chan ProgressEvent
}

type toolRef struct {
	serverName string
	toolName   string
}

type serverClient struct {
	name    string
	session *sdk.ClientSession
	close   func() error
}

func NewAggregator(logger logging.Logger) *Aggregator {
	return &Aggregator{
		logger:     logger,
		servers:    make(map[string]*serverClient),
		tools:      make(map[string]toolRef),
		toolDescs:  make(map[string]protocol.ToolDescriptor),
		progressCh: make(chan ProgressEvent, 256),
	}
}

func (a *Aggregator) ProgressEvents() <-chan ProgressEvent {
	return a.progressCh
}

func (a *Aggregator) Start(ctx context.Context, servers []config.MCPServerConfig) error {
	if a == nil {
		return errors.New("aggregator is nil")
	}

	a.mu.Lock()
	defer a.mu.Unlock()

	// Reset previous state.
	for _, s := range a.servers {
		if s != nil && s.close != nil {
			_ = s.close()
		}
	}
	a.servers = make(map[string]*serverClient)
	a.tools = make(map[string]toolRef)
	a.toolDescs = make(map[string]protocol.ToolDescriptor)

	// Built-in tool (for end-to-end validation).
	a.tools["bridge__echo"] = toolRef{serverName: "bridge", toolName: "echo"}
	a.toolDescs["bridge__echo"] = protocol.ToolDescriptor{
		Name:        "bridge__echo",
		Description: "Built-in test tool for streaming/RESULT validation",
		InputSchema: map[string]any{"type": "object", "properties": map[string]any{
			"lines":    map[string]any{"type": "array", "items": map[string]any{"type": "string"}},
			"sleep_ms": map[string]any{"type": "number"},
		}},
		Meta: map[string]string{"server": "bridge", "original_tool": "echo"},
	}

	var errs []error
	for _, s := range servers {
		if strings.TrimSpace(s.Name) == "" {
			continue
		}
		name := sanitizeName(s.Name)
		if name == "" {
			errs = append(errs, fmt.Errorf("invalid mcp server name: %q", s.Name))
			continue
		}
		if s.Command == "" && s.URL == "" {
			errs = append(errs, fmt.Errorf("mcp server %q: missing command or url", s.Name))
			continue
		}
		if s.Command == "" {
			// Remote transports are an extension; keep stubbed for now.
			errs = append(errs, fmt.Errorf("mcp server %q: remote url transport not implemented yet", s.Name))
			continue
		}

		session, closeFn, err := a.connectCommandServer(ctx, s)
		if err != nil {
			errs = append(errs, fmt.Errorf("connect mcp server %q: %w", s.Name, err))
			continue
		}
		a.servers[name] = &serverClient{name: name, session: session, close: closeFn}

		tools, err := listAllTools(ctx, session)
		if err != nil {
			errs = append(errs, fmt.Errorf("list tools %q: %w", s.Name, err))
			continue
		}
		for _, t := range tools {
			if t == nil {
				continue
			}
			toolName := sanitizeName(t.Name)
			if toolName == "" {
				continue
			}
			nsName := name + "__" + toolName
			a.tools[nsName] = toolRef{serverName: name, toolName: t.Name}
			inputSchema, _ := t.InputSchema.(map[string]any)
			a.toolDescs[nsName] = protocol.ToolDescriptor{
				Name:        nsName,
				Description: t.Description,
				InputSchema: inputSchema,
				Meta: map[string]string{
					"server":        name,
					"original_tool": t.Name,
				},
			}
		}
	}

	return errors.Join(errs...)
}

func (a *Aggregator) ListTools(ctx context.Context) []protocol.ToolDescriptor {
	if a == nil {
		return nil
	}
	a.mu.RLock()
	defer a.mu.RUnlock()

	names := make([]string, 0, len(a.toolDescs))
	for name := range a.toolDescs {
		names = append(names, name)
	}
	sort.Strings(names)

	out := make([]protocol.ToolDescriptor, 0, len(names))
	for _, name := range names {
		out = append(out, a.toolDescs[name])
	}
	return out
}

func (a *Aggregator) CallTool(ctx context.Context, reqID string, namespacedTool string, args map[string]any) (any, error) {
	if a == nil {
		return nil, errors.New("aggregator is nil")
	}
	if strings.TrimSpace(namespacedTool) == "" {
		return nil, errors.New("missing tool name")
	}

	if namespacedTool == "bridge__echo" {
		return map[string]any{"echo": args}, nil
	}

	a.mu.RLock()
	ref, ok := a.tools[namespacedTool]
	s := a.servers[ref.serverName]
	a.mu.RUnlock()

	if !ok || ref.serverName == "" || ref.toolName == "" || s == nil || s.session == nil {
		return nil, fmt.Errorf("tool not found: %s", namespacedTool)
	}

	params := &sdk.CallToolParams{
		Name:      ref.toolName,
		Arguments: args,
	}
	if reqID != "" {
		params.SetProgressToken(reqID)
	}

	res, err := s.session.CallTool(ctx, params)
	if err != nil {
		return nil, err
	}

	b, err := json.Marshal(res)
	if err != nil {
		return nil, err
	}
	var anyValue any
	if err := json.Unmarshal(b, &anyValue); err != nil {
		return nil, err
	}
	return anyValue, nil
}

func sanitizeName(raw string) string {
	s := strings.TrimSpace(raw)
	if s == "" {
		return ""
	}
	s = strings.ReplaceAll(s, "-", "_")
	s = strings.ReplaceAll(s, ".", "_")
	s = validNameRe.ReplaceAllString(s, "_")
	s = strings.Trim(s, "_")
	return s
}

func (a *Aggregator) connectCommandServer(ctx context.Context, cfg config.MCPServerConfig) (*sdk.ClientSession, func() error, error) {
	impl := &sdk.Implementation{
		Name:    "ai-bridge-agent",
		Version: "v0",
	}

	client := sdk.NewClient(impl, &sdk.ClientOptions{
		ProgressNotificationHandler: func(_ context.Context, req *sdk.ProgressNotificationClientRequest) {
			if req == nil || req.Params == nil {
				return
			}
			token, _ := req.Params.ProgressToken.(string)
			if token == "" {
				return
			}
			select {
			case a.progressCh <- ProgressEvent{
				ReqID:      token,
				ServerName: cfg.Name,
				Message:    req.Params.Message,
				Progress:   req.Params.Progress,
				Total:      req.Params.Total,
			}:
			default:
			}
		},
		LoggingMessageHandler: func(_ context.Context, req *sdk.LoggingMessageRequest) {
			if req == nil || req.Params == nil {
				return
			}
			a.logger.Debug("mcp log", "server", cfg.Name, "level", string(req.Params.Level), "data", req.Params.Data)
		},
		KeepAlive: 30 * time.Second,
	})

	cmd := exec.CommandContext(ctx, cfg.Command, cfg.Args...)
	cmd.Env = mergeEnv(os.Environ(), cfg.Env)

	transport := &sdk.CommandTransport{Command: cmd}
	session, err := client.Connect(ctx, transport, nil)
	if err != nil {
		return nil, nil, err
	}
	return session, session.Close, nil
}

func mergeEnv(base []string, extra map[string]string) []string {
	if len(extra) == 0 {
		return base
	}
	out := append([]string{}, base...)
	for k, v := range extra {
		out = append(out, fmt.Sprintf("%s=%s", k, v))
	}
	return out
}

func listAllTools(ctx context.Context, session *sdk.ClientSession) ([]*sdk.Tool, error) {
	var out []*sdk.Tool
	cursor := ""
	for {
		res, err := session.ListTools(ctx, &sdk.ListToolsParams{Cursor: cursor})
		if err != nil {
			return nil, err
		}
		out = append(out, res.Tools...)
		if strings.TrimSpace(res.NextCursor) == "" {
			return out, nil
		}
		cursor = res.NextCursor
	}
}

func findTool(ctx context.Context, session *sdk.ClientSession, name string) (*sdk.Tool, error) {
	cursor := ""
	for {
		res, err := session.ListTools(ctx, &sdk.ListToolsParams{Cursor: cursor})
		if err != nil {
			return nil, err
		}
		for _, t := range res.Tools {
			if t != nil && t.Name == name {
				return t, nil
			}
		}
		if strings.TrimSpace(res.NextCursor) == "" {
			return nil, nil
		}
		cursor = res.NextCursor
	}
}
