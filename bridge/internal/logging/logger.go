package logging

import (
	"context"
	"errors"
	"log/slog"
	"os"
	"strings"
)

type Options struct {
	Level  string
	Format string
}

type Logger interface {
	Debug(msg string, args ...any)
	Info(msg string, args ...any)
	Warn(msg string, args ...any)
	Error(msg string, args ...any)
}

type SlogLogger struct {
	logger *slog.Logger
}

func (l SlogLogger) Debug(msg string, args ...any) { l.logger.Debug(msg, args...) }
func (l SlogLogger) Info(msg string, args ...any)  { l.logger.Info(msg, args...) }
func (l SlogLogger) Warn(msg string, args ...any)  { l.logger.Warn(msg, args...) }
func (l SlogLogger) Error(msg string, args ...any) { l.logger.Error(msg, args...) }

func NewLogger(opts Options) (Logger, error) {
	level := parseLevel(opts.Level)
	var handler slog.Handler

	switch strings.ToLower(strings.TrimSpace(opts.Format)) {
	case "", "text":
		handler = slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: level})
	case "json":
		handler = slog.NewJSONHandler(os.Stderr, &slog.HandlerOptions{Level: level})
	default:
		return nil, errors.New("unsupported log format")
	}

	return SlogLogger{logger: slog.New(handler)}, nil
}

func parseLevel(value string) slog.Level {
	switch strings.ToLower(strings.TrimSpace(value)) {
	case "debug":
		return slog.LevelDebug
	case "warn", "warning":
		return slog.LevelWarn
	case "error":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

type ctxKey struct{}

func WithLogger(ctx context.Context, logger Logger) context.Context {
	return context.WithValue(ctx, ctxKey{}, logger)
}

func FromContext(ctx context.Context) Logger {
	if ctx == nil {
		return SlogLogger{logger: slog.New(slog.NewTextHandler(os.Stderr, nil))}
	}
	if v := ctx.Value(ctxKey{}); v != nil {
		if logger, ok := v.(Logger); ok && logger != nil {
			return logger
		}
	}
	return SlogLogger{logger: slog.New(slog.NewTextHandler(os.Stderr, nil))}
}
