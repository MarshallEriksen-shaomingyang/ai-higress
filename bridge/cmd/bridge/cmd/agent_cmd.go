package cmd

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"
	"unicode/utf8"

	"bridge/internal/backpressure"
	"bridge/internal/config"
	"bridge/internal/logging"
	"bridge/internal/mcpbridge"
	"bridge/internal/mcpserver"
	"bridge/internal/protocol"

	"github.com/google/uuid"
	sdk "github.com/modelcontextprotocol/go-sdk/mcp"
	"github.com/spf13/cobra"
	"nhooyr.io/websocket"
)

func NewAgentCmd() *cobra.Command {
	agentCmd := &cobra.Command{
		Use:   "agent",
		Short: "Bridge agent (runs on user machines)",
	}
	agentCmd.AddCommand(newAgentStartCmd())
	agentCmd.AddCommand(newAgentServeMCPCmd())
	return agentCmd
}

func newAgentStartCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "start",
		Short: "Start bridge agent",
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx, stop := signal.NotifyContext(cmd.Context(), os.Interrupt, syscall.SIGTERM)
			defer stop()
			return runAgent(ctx, GetConfigFileFlag())
		},
	}
}

func newAgentServeMCPCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "serve-mcp",
		Short: "Run as a local stdio MCP server (aggregate configured MCP servers)",
		RunE: func(cmd *cobra.Command, args []string) error {
			ctx, stop := signal.NotifyContext(cmd.Context(), os.Interrupt, syscall.SIGTERM)
			defer stop()
			return runAgentServeMCP(ctx, GetConfigFileFlag())
		},
	}
}

type agentRuntime struct {
	agentID string
	agg     *mcpbridge.Aggregator
	pendingMu      sync.Mutex
	pendingResults map[string]protocol.Envelope
}

func newAgentRuntime(agentID string, agg *mcpbridge.Aggregator) *agentRuntime {
	return &agentRuntime{
		agentID:        agentID,
		agg:            agg,
		pendingResults: make(map[string]protocol.Envelope),
	}
}

func (r *agentRuntime) pendingReqIDs() []string {
	r.pendingMu.Lock()
	defer r.pendingMu.Unlock()
	ids := make([]string, 0, len(r.pendingResults))
	for id := range r.pendingResults {
		ids = append(ids, id)
	}
	return ids
}

func (r *agentRuntime) storePendingResult(env protocol.Envelope) {
	if env.ReqID == "" {
		return
	}
	r.pendingMu.Lock()
	defer r.pendingMu.Unlock()
	r.pendingResults[env.ReqID] = env
}

func (r *agentRuntime) deletePendingResult(reqID string) {
	if reqID == "" {
		return
	}
	r.pendingMu.Lock()
	defer r.pendingMu.Unlock()
	delete(r.pendingResults, reqID)
}

func (r *agentRuntime) snapshotPendingResults() []protocol.Envelope {
	r.pendingMu.Lock()
	defer r.pendingMu.Unlock()
	out := make([]protocol.Envelope, 0, len(r.pendingResults))
	for _, env := range r.pendingResults {
		out = append(out, env)
	}
	return out
}

type agentSession struct {
	agentID string
	conn    *websocket.Conn
	agg     *mcpbridge.Aggregator
	rt      *agentRuntime

	chunkQ             *backpressure.BoundedBytesChannel
	chunkMaxFrameBytes int

	writeMu sync.Mutex

	chunkMu      sync.Mutex
	droppedBytes int64
	droppedLines int64

	cancelMu sync.Mutex
	cancels  map[string]context.CancelFunc
}

func runAgent(ctx context.Context, configFile string) error {
	logger := logging.FromContext(ctx)

	cfg, err := config.Load(config.LoadOptions{ConfigFile: configFile})
	if err != nil {
		return err
	}
	if err := cfg.Validate(); err != nil {
		return err
	}

	agg := mcpbridge.NewAggregator(logger)
	if err := agg.Start(ctx, cfg.MCPServers); err != nil {
		// Non-fatal: still allow connecting to tunnel, but tools may be incomplete.
		logger.Warn("mcp aggregator start failed", "err", err.Error())
	}

	rt := newAgentRuntime(cfg.Agent.ID, agg)
	rt.agg = agg

	backoff := cfg.Server.ReconnectInitial
	if backoff <= 0 {
		backoff = 1 * time.Second
	}
	maxBackoff := cfg.Server.ReconnectMax
	if maxBackoff <= 0 {
		maxBackoff = 60 * time.Second
	}

	for {
		if ctx.Err() != nil {
			return nil
		}
		if err := connectAndServe(ctx, cfg, rt); err != nil {
			logger.Warn("tunnel session ended", "err", err.Error())
		}
		if ctx.Err() != nil {
			return nil
		}
		time.Sleep(backoff)
		backoff *= 2
		if backoff > maxBackoff {
			backoff = maxBackoff
		}
	}
}

func runAgentServeMCP(ctx context.Context, configFile string) error {
	logger := logging.FromContext(ctx)

	cfg, err := config.Load(config.LoadOptions{ConfigFile: configFile})
	if err != nil {
		return err
	}
	if err := cfg.ValidateForMCPServe(); err != nil {
		return err
	}

	agg := mcpbridge.NewAggregator(logger)
	if err := agg.Start(ctx, cfg.MCPServers); err != nil {
		logger.Warn("mcp aggregator start failed", "err", err.Error())
	}

	srv := mcpserver.NewAggregatorStdioServer(logger, agg)
	return srv.Run(ctx, &sdk.StdioTransport{})
}

func connectAndServe(ctx context.Context, cfg *config.Config, rt *agentRuntime) error {
	logger := logging.FromContext(ctx)

	sessionCtx, sessionCancel := context.WithCancel(ctx)
	defer sessionCancel()

	conn, _, err := websocket.Dial(sessionCtx, cfg.Server.URL, nil)
	if err != nil {
		return fmt.Errorf("dial tunnel: %w", err)
	}
	defer conn.Close(websocket.StatusNormalClosure, "")

	session := &agentSession{
		agentID:            cfg.Agent.ID,
		conn:               conn,
		agg:                rt.agg,
		rt:                 rt,
		cancels:            make(map[string]context.CancelFunc),
		chunkQ:             backpressure.NewBoundedBytesChannel(cfg.Agent.ChunkBufferBytes, 512),
		chunkMaxFrameBytes: cfg.Agent.ChunkMaxFrameBytes,
	}
	go session.chunkWriter(sessionCtx)

	connSessionID := "ws_" + uuid.NewString()
	now := time.Now().Unix()

	helloPayload := protocol.HelloPayload{
		AgentMeta: map[string]string{
			"pid":      fmt.Sprintf("%d", os.Getpid()),
			"hostname": hostname(),
		},
		Resume: &protocol.ResumePayload{
			PendingResultReqIDs: rt.pendingReqIDs(),
		},
	}
	if err := session.sendEnvelope(ctx, protocol.Envelope{
		V:             1,
		Type:          protocol.TypeHello,
		AgentID:       cfg.Agent.ID,
		ConnSessionID: connSessionID,
		Ts:            now,
		Payload:       mustMarshalJSON(helloPayload),
	}); err != nil {
		return err
	}

	authPayload := protocol.AuthPayload{Token: cfg.Server.Token}
	if err := session.sendEnvelope(ctx, protocol.Envelope{
		V:             1,
		Type:          protocol.TypeAuth,
		AgentID:       cfg.Agent.ID,
		ConnSessionID: connSessionID,
		Ts:            now,
		Payload:       mustMarshalJSON(authPayload),
	}); err != nil {
		return err
	}

	logger.Info("agent connected", "agent_id", cfg.Agent.ID, "server_url", cfg.Server.URL)

	if err := session.sendTools(ctx); err != nil {
		logger.Warn("send tools failed", "err", err.Error())
	}

	// Best-effort resend pending results after reconnect.
	for _, env := range rt.snapshotPendingResults() {
		_ = session.sendEnvelope(ctx, env)
	}

	go session.pingLoop(sessionCtx, 25*time.Second)
	go session.progressLoop(sessionCtx)
	go session.logLoop(sessionCtx)
	return session.readLoop(sessionCtx)
}

func (s *agentSession) chunkWriter(ctx context.Context) {
	logger := logging.FromContext(ctx)
	if s == nil || s.chunkQ == nil {
		return
	}
	for {
		msg, ok := s.chunkQ.Receive(ctx)
		if !ok {
			return
		}
		s.writeMu.Lock()
		err := s.conn.Write(ctx, websocket.MessageText, msg)
		s.writeMu.Unlock()
		if err != nil {
			logger.Debug("chunk writer stopped", "err", err.Error())
			return
		}
	}
}

func (s *agentSession) pingLoop(ctx context.Context, interval time.Duration) {
	t := time.NewTicker(interval)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			_ = s.sendEnvelope(ctx, protocol.Envelope{
				V:       1,
				Type:    protocol.TypePing,
				AgentID: s.agentID,
				Ts:      time.Now().Unix(),
			})
		}
	}
}

func (s *agentSession) progressLoop(ctx context.Context) {
	logger := logging.FromContext(ctx)
	if s.agg == nil {
		return
	}
	for {
		select {
		case <-ctx.Done():
			return
		case ev := <-s.agg.ProgressEvents():
			if ev.ReqID == "" {
				continue
			}
			// Only forward progress for active invocations.
			if s.getCancel(ev.ReqID) == nil {
				continue
			}
			msg := ev.Message
			if msg == "" {
				if ev.Total > 0 {
					msg = fmt.Sprintf("progress %.0f/%.0f", ev.Progress, ev.Total)
				} else {
					msg = fmt.Sprintf("progress %.0f", ev.Progress)
				}
			}
			if err := s.sendChunk(ctx, ev.ReqID, "stdout", msg+"\n"); err != nil {
				logger.Debug("send progress chunk failed", "req_id", ev.ReqID, "err", err.Error())
			}
		}
	}
}

func (s *agentSession) logLoop(ctx context.Context) {
	logger := logging.FromContext(ctx)
	if s.agg == nil {
		return
	}
	for {
		select {
		case <-ctx.Done():
			return
		case ev := <-s.agg.LogEvents():
			reqID := s.singleActiveReqID()
			raw, err := json.Marshal(ev.Data)
			if err != nil {
				raw = []byte(fmt.Sprintf("%v", ev.Data))
			}
			prefix := ""
			if ev.ServerName != "" {
				prefix = "[" + ev.ServerName + "] "
			}
			if ev.Level != "" {
				prefix = prefix + "(" + ev.Level + ") "
			}
			if err := s.sendChunk(ctx, reqID, "stderr", prefix+string(raw)+"\n"); err != nil {
				logger.Debug("send log chunk failed", "err", err.Error())
			}
		}
	}
}

func (s *agentSession) singleActiveReqID() string {
	s.cancelMu.Lock()
	defer s.cancelMu.Unlock()
	if len(s.cancels) != 1 {
		return ""
	}
	for reqID := range s.cancels {
		return reqID
	}
	return ""
}

func (s *agentSession) sendTools(ctx context.Context) error {
	var tools []protocol.ToolDescriptor
	if s.agg != nil {
		tools = s.agg.ListTools(ctx)
	}
	return s.sendEnvelope(ctx, protocol.Envelope{
		V:       1,
		Type:    protocol.TypeTools,
		AgentID: s.agentID,
		Ts:      time.Now().Unix(),
		Payload: mustMarshalJSON(protocol.ToolsPayload{Tools: tools}),
	})
}

func (s *agentSession) readLoop(ctx context.Context) error {
	logger := logging.FromContext(ctx)
	if s.chunkQ != nil {
		defer s.chunkQ.Close()
	}
	defer s.cancelAll()
	for {
		_, data, err := s.conn.Read(ctx)
		if err != nil {
			if websocket.CloseStatus(err) != -1 {
				return nil
			}
			return err
		}

		env, err := protocol.DecodeEnvelope(data)
		if err != nil {
			logger.Warn("invalid envelope", "err", err.Error())
			continue
		}

		switch env.Type {
		case protocol.TypePing:
			_ = s.sendEnvelope(ctx, protocol.Envelope{
				V:       1,
				Type:    protocol.TypePong,
				AgentID: s.agentID,
				Ts:      time.Now().Unix(),
			})
		case protocol.TypeInvoke:
			go s.handleInvoke(ctx, env)
		case protocol.TypeCancel:
			s.handleCancel(ctx, env)
		case protocol.TypeResultAck:
			s.clearCancel(env.ReqID)
			if s.rt != nil {
				s.rt.deletePendingResult(env.ReqID)
			}
		default:
			logger.Debug("ignored message", "type", env.Type)
		}
	}
}

func (s *agentSession) handleInvoke(parentCtx context.Context, env *protocol.Envelope) {
	logger := logging.FromContext(parentCtx)

	var payload protocol.InvokePayload
	if err := json.Unmarshal(env.Payload, &payload); err != nil {
		_ = s.sendEnvelope(parentCtx, protocol.Envelope{
			V:       1,
			Type:    protocol.TypeInvokeAck,
			AgentID: s.agentID,
			ReqID:   env.ReqID,
			Ts:      time.Now().Unix(),
			Payload: mustMarshalJSON(protocol.InvokeAckPayload{Accepted: false, Reason: "invalid_payload"}),
		})
		return
	}

	if err := s.sendEnvelope(parentCtx, protocol.Envelope{
		V:       1,
		Type:    protocol.TypeInvokeAck,
		AgentID: s.agentID,
		ReqID:   env.ReqID,
		Ts:      time.Now().Unix(),
		Payload: mustMarshalJSON(protocol.InvokeAckPayload{Accepted: true}),
	}); err != nil {
		logger.Warn("send invoke ack failed", "req_id", env.ReqID, "err", err.Error())
		return
	}

	ctx := parentCtx
	var cancel context.CancelFunc
	if payload.TimeoutMs > 0 {
		ctx, cancel = context.WithTimeout(parentCtx, time.Duration(payload.TimeoutMs)*time.Millisecond)
	} else {
		ctx, cancel = context.WithCancel(parentCtx)
	}
	s.setCancel(env.ReqID, cancel)
	defer s.clearCancel(env.ReqID)

	toolName := strings.TrimSpace(payload.Tool.Name)
	if toolName == "" {
		_ = s.sendResult(ctx, env.ReqID, protocol.ResultPayload{
			OK:    false,
			Error: &protocol.ResultError{Message: "missing tool name", Code: "tool_not_found"},
		})
		return
	}

	_ = s.sendChunk(ctx, env.ReqID, "stderr", fmt.Sprintf("running tool: %s\n", toolName))

	switch toolName {
	case "echo", "bridge__echo":
		s.simulateEchoTool(ctx, env.ReqID, payload.Tool.Args)
		return
	}

	if s.agg == nil {
		_ = s.sendResult(ctx, env.ReqID, protocol.ResultPayload{
			OK:    false,
			Error: &protocol.ResultError{Message: "mcp aggregator not initialized", Code: "internal_error"},
		})
		return
	}

	result, err := s.agg.CallTool(ctx, env.ReqID, toolName, payload.Tool.Args)
	if err != nil {
		if errors.Is(err, context.Canceled) || errors.Is(ctx.Err(), context.Canceled) {
			_ = s.sendResult(ctx, env.ReqID, protocol.ResultPayload{
				OK:       false,
				Canceled: true,
				Error:    &protocol.ResultError{Message: "canceled", Code: "canceled"},
			})
			return
		}
		if errors.Is(err, context.DeadlineExceeded) || errors.Is(ctx.Err(), context.DeadlineExceeded) {
			_ = s.sendResult(ctx, env.ReqID, protocol.ResultPayload{
				OK:    false,
				Error: &protocol.ResultError{Message: "timeout", Code: "timeout"},
			})
			return
		}
		_ = s.sendResult(ctx, env.ReqID, protocol.ResultPayload{
			OK:    false,
			Error: &protocol.ResultError{Message: err.Error(), Code: "tool_call_failed"},
		})
		return
	}
	_ = s.sendResult(ctx, env.ReqID, protocol.ResultPayload{
		OK:     true,
		Result: result,
	})
}

func (s *agentSession) simulateEchoTool(ctx context.Context, reqID string, args map[string]any) {
	sleepMs := int64(0)
	if v, ok := args["sleep_ms"].(float64); ok {
		sleepMs = int64(v)
	}
	linesAny, _ := args["lines"].([]any)
	if len(linesAny) == 0 {
		if t, ok := args["text"].(string); ok && t != "" {
			linesAny = []any{t}
		}
	}

	for _, line := range linesAny {
		select {
		case <-ctx.Done():
			_ = s.sendResult(ctx, reqID, protocol.ResultPayload{
				OK:       false,
				Canceled: true,
				Error:    &protocol.ResultError{Message: "canceled", Code: "canceled"},
			})
			return
		default:
		}
		_ = s.sendChunk(ctx, reqID, "stdout", fmt.Sprintf("%v\n", line))
		if sleepMs > 0 {
			time.Sleep(time.Duration(sleepMs) * time.Millisecond)
		}
	}

	_ = s.sendResult(ctx, reqID, protocol.ResultPayload{
		OK: true,
		Result: map[string]any{
			"echo": args,
		},
	})
}

func (s *agentSession) handleCancel(ctx context.Context, env *protocol.Envelope) {
	cancel := s.getCancel(env.ReqID)
	if cancel == nil {
		_ = s.sendEnvelope(ctx, protocol.Envelope{
			V:       1,
			Type:    protocol.TypeCancelAck,
			AgentID: s.agentID,
			ReqID:   env.ReqID,
			Ts:      time.Now().Unix(),
			Payload: mustMarshalJSON(protocol.CancelAckPayload{WillCancel: false, Reason: "unknown_req_id"}),
		})
		return
	}
	cancel()
	_ = s.sendEnvelope(ctx, protocol.Envelope{
		V:       1,
		Type:    protocol.TypeCancelAck,
		AgentID: s.agentID,
		ReqID:   env.ReqID,
		Ts:      time.Now().Unix(),
		Payload: mustMarshalJSON(protocol.CancelAckPayload{WillCancel: true}),
	})
}

func (s *agentSession) sendChunk(ctx context.Context, reqID string, channel string, data string) error {
	if s == nil || s.chunkQ == nil {
		return nil
	}
	if data == "" {
		return nil
	}
	if s.chunkMaxFrameBytes <= 0 {
		s.chunkMaxFrameBytes = 16 * 1024
	}

	parts := splitUTF8StringByBytes(data, s.chunkMaxFrameBytes)
	for _, part := range parts {
		if part == "" {
			continue
		}
		partBytes := int64(len([]byte(part)))
		partLines := countNewlines(part)

		s.chunkMu.Lock()
		droppedBytes := s.droppedBytes
		droppedLines := s.droppedLines

		env := protocol.Envelope{
			V:       1,
			Type:    protocol.TypeChunk,
			AgentID: s.agentID,
			ReqID:   reqID,
			Ts:      time.Now().Unix(),
			Payload: mustMarshalJSON(protocol.ChunkPayload{
				Channel:      channel,
				Data:         part,
				DroppedBytes: droppedBytes,
				DroppedLines: droppedLines,
			}),
		}
		msg, err := protocol.EncodeEnvelope(env)
		if err != nil {
			s.chunkMu.Unlock()
			return err
		}

		if ok := s.chunkQ.TrySend(msg); ok {
			s.droppedBytes = 0
			s.droppedLines = 0
			s.chunkMu.Unlock()
			continue
		}

		// Queue full: drop this CHUNK and accumulate loss for observability.
		s.droppedBytes += partBytes
		s.droppedLines += partLines
		s.chunkMu.Unlock()
	}
	return nil
}

func (s *agentSession) sendResult(ctx context.Context, reqID string, payload protocol.ResultPayload) error {
	env := protocol.Envelope{
		V:       1,
		Type:    protocol.TypeResult,
		AgentID: s.agentID,
		ReqID:   reqID,
		Ts:      time.Now().Unix(),
		Payload: mustMarshalJSON(payload),
	}
	if s.rt != nil {
		s.rt.storePendingResult(env)
	}
	return s.sendEnvelope(ctx, env)
}

func (s *agentSession) sendEnvelope(ctx context.Context, env protocol.Envelope) error {
	data, err := protocol.EncodeEnvelope(env)
	if err != nil {
		return err
	}
	s.writeMu.Lock()
	defer s.writeMu.Unlock()
	return s.conn.Write(ctx, websocket.MessageText, data)
}

func (s *agentSession) setCancel(reqID string, cancel context.CancelFunc) {
	if reqID == "" || cancel == nil {
		return
	}
	s.cancelMu.Lock()
	defer s.cancelMu.Unlock()
	s.cancels[reqID] = cancel
}

func (s *agentSession) getCancel(reqID string) context.CancelFunc {
	s.cancelMu.Lock()
	defer s.cancelMu.Unlock()
	return s.cancels[reqID]
}

func (s *agentSession) clearCancel(reqID string) {
	s.cancelMu.Lock()
	defer s.cancelMu.Unlock()
	delete(s.cancels, reqID)
}

func (s *agentSession) cancelAll() {
	s.cancelMu.Lock()
	defer s.cancelMu.Unlock()
	for _, cancel := range s.cancels {
		if cancel != nil {
			cancel()
		}
	}
	s.cancels = make(map[string]context.CancelFunc)
}

func splitUTF8StringByBytes(s string, maxBytes int) []string {
	if s == "" {
		return nil
	}
	if maxBytes <= 0 || len(s) <= maxBytes {
		return []string{s}
	}

	b := []byte(s)
	out := make([]string, 0, (len(b)/maxBytes)+1)
	for len(b) > 0 {
		n := maxBytes
		if n > len(b) {
			n = len(b)
		}
		for n > 0 && !utf8.Valid(b[:n]) {
			n--
		}
		if n <= 0 {
			_, size := utf8.DecodeRune(b)
			if size <= 0 {
				break
			}
			n = size
		}
		out = append(out, string(b[:n]))
		b = b[n:]
	}
	return out
}

func countNewlines(s string) int64 {
	var n int64
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			n++
		}
	}
	return n
}

func hostname() string {
	h, err := os.Hostname()
	if err != nil {
		return ""
	}
	return h
}
