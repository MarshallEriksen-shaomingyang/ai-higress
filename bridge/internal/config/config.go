package config

import (
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/spf13/viper"
)

type Config struct {
	Version    string            `mapstructure:"version"`
	Server     ServerConfig      `mapstructure:"server"`
	Agent      AgentConfig       `mapstructure:"agent"`
	MCPServers []MCPServerConfig `mapstructure:"mcp_servers"`
}

type ServerConfig struct {
	URL              string        `mapstructure:"url"`
	Token            string        `mapstructure:"token"`
	ReconnectInitial time.Duration `mapstructure:"reconnect_initial"`
	ReconnectMax     time.Duration `mapstructure:"reconnect_max"`
}

type AgentConfig struct {
	ID    string `mapstructure:"id"`
	Label string `mapstructure:"label"`

	// ChunkBufferBytes limits queued CHUNK messages in-memory for backpressure.
	// When full, logs are dropped and accounted via dropped_bytes/dropped_lines.
	ChunkBufferBytes int64 `mapstructure:"chunk_buffer_bytes"`

	// ChunkMaxFrameBytes limits a single CHUNK frame size (payload data), to avoid
	// oversized WS frames and reduce buffering spikes.
	ChunkMaxFrameBytes int `mapstructure:"chunk_max_frame_bytes"`
}

type MCPServerConfig struct {
	Name    string            `mapstructure:"name"`
	Type    string            `mapstructure:"type"`
	Command string            `mapstructure:"command"`
	Args    []string          `mapstructure:"args"`
	Env     map[string]string `mapstructure:"env"`
	URL     string            `mapstructure:"url"`
	Headers map[string]string `mapstructure:"headers"`
}

type LoadOptions struct {
	ConfigFile string
}

const projectConfigRelPath = ".ai-bridge/config.yaml"

func DefaultConfigPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return filepath.Join(".ai-bridge", "config.yaml")
	}
	return filepath.Join(home, ".ai-bridge", "config.yaml")
}

func ResolveConfigPath(configFile string) string {
	if strings.TrimSpace(configFile) != "" {
		return configFile
	}
	if p := findProjectConfigPath(); p != "" {
		return p
	}
	return DefaultConfigPath()
}

func findProjectConfigPath() string {
	cwd, err := os.Getwd()
	if err != nil || strings.TrimSpace(cwd) == "" {
		return ""
	}
	dir := cwd
	for {
		p := filepath.Join(dir, projectConfigRelPath)
		if fileExists(p) {
			return p
		}

		// Stop after reaching repo root (if any) to avoid walking the entire FS.
		if fileExists(filepath.Join(dir, ".git")) {
			return ""
		}

		parent := filepath.Dir(dir)
		if parent == dir {
			return ""
		}
		dir = parent
	}
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func Load(opts LoadOptions) (*Config, error) {
	v := viper.New()
	v.SetConfigType("yaml")
	v.SetEnvPrefix("AI_BRIDGE")
	v.AutomaticEnv()

	path := ResolveConfigPath(opts.ConfigFile)
	v.SetConfigFile(path)

	v.SetDefault("server.reconnect_initial", "1s")
	v.SetDefault("server.reconnect_max", "60s")
	v.SetDefault("agent.chunk_buffer_bytes", 4*1024*1024)
	v.SetDefault("agent.chunk_max_frame_bytes", 16*1024)

	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("read config: %w", err)
	}

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("decode config: %w", err)
	}
	return &cfg, nil
}

func (c *Config) Validate() error {
	if c == nil {
		return errors.New("config is nil")
	}
	if c.Agent.ID == "" {
		return errors.New("agent.id is required")
	}
	if c.Server.URL == "" {
		return errors.New("server.url is required")
	}
	if c.Server.ReconnectInitial <= 0 {
		return errors.New("server.reconnect_initial must be > 0")
	}
	if c.Server.ReconnectMax <= 0 {
		return errors.New("server.reconnect_max must be > 0")
	}
	if c.Server.ReconnectMax < c.Server.ReconnectInitial {
		return errors.New("server.reconnect_max must be >= server.reconnect_initial")
	}
	if c.Agent.ChunkBufferBytes <= 0 {
		return errors.New("agent.chunk_buffer_bytes must be > 0")
	}
	if c.Agent.ChunkMaxFrameBytes <= 0 {
		return errors.New("agent.chunk_max_frame_bytes must be > 0")
	}
	if c.Agent.ChunkMaxFrameBytes < 1024 || c.Agent.ChunkMaxFrameBytes > 256*1024 {
		return errors.New("agent.chunk_max_frame_bytes must be between 1024 and 262144")
	}
	for i, s := range c.MCPServers {
		if s.Name == "" {
			return fmt.Errorf("mcp_servers[%d].name is required", i)
		}
		if s.Command == "" && s.URL == "" {
			return fmt.Errorf("mcp_servers[%d] must set command or url", i)
		}
		if strings.TrimSpace(s.Type) != "" {
			switch strings.ToLower(strings.TrimSpace(s.Type)) {
			case "command", "auto", "streamable", "streamable_http", "http", "sse", "legacy_sse":
			default:
				return fmt.Errorf("mcp_servers[%d].type is unsupported: %q", i, s.Type)
			}
		}
		if strings.TrimSpace(s.URL) != "" {
			u, err := url.Parse(s.URL)
			if err != nil {
				return fmt.Errorf("mcp_servers[%d].url is invalid: %w", i, err)
			}
			if u.Scheme != "http" && u.Scheme != "https" {
				return fmt.Errorf("mcp_servers[%d].url must start with http:// or https://", i)
			}
		}
	}
	return nil
}

// ValidateForMCPServe validates the subset of config required to run the agent
// as a local stdio MCP server (without connecting to the cloud tunnel).
func (c *Config) ValidateForMCPServe() error {
	if c == nil {
		return errors.New("config is nil")
	}
	if c.Agent.ChunkBufferBytes <= 0 {
		return errors.New("agent.chunk_buffer_bytes must be > 0")
	}
	if c.Agent.ChunkMaxFrameBytes <= 0 {
		return errors.New("agent.chunk_max_frame_bytes must be > 0")
	}
	if c.Agent.ChunkMaxFrameBytes < 1024 || c.Agent.ChunkMaxFrameBytes > 256*1024 {
		return errors.New("agent.chunk_max_frame_bytes must be between 1024 and 262144")
	}
	for i, s := range c.MCPServers {
		if s.Name == "" {
			return fmt.Errorf("mcp_servers[%d].name is required", i)
		}
		if s.Command == "" && s.URL == "" {
			return fmt.Errorf("mcp_servers[%d] must set command or url", i)
		}
		if strings.TrimSpace(s.Type) != "" {
			switch strings.ToLower(strings.TrimSpace(s.Type)) {
			case "command", "auto", "streamable", "streamable_http", "http", "sse", "legacy_sse":
			default:
				return fmt.Errorf("mcp_servers[%d].type is unsupported: %q", i, s.Type)
			}
		}
		if strings.TrimSpace(s.URL) != "" {
			u, err := url.Parse(s.URL)
			if err != nil {
				return fmt.Errorf("mcp_servers[%d].url is invalid: %w", i, err)
			}
			if u.Scheme != "http" && u.Scheme != "https" {
				return fmt.Errorf("mcp_servers[%d].url must start with http:// or https://", i)
			}
		}
	}
	return nil
}

func ApplyFile(srcPath string, dstPath string) error {
	srcFile, err := os.Open(srcPath)
	if err != nil {
		return fmt.Errorf("open source: %w", err)
	}
	defer srcFile.Close()

	if err := os.MkdirAll(filepath.Dir(dstPath), 0o700); err != nil {
		return fmt.Errorf("mkdir config dir: %w", err)
	}

	tmpPath := dstPath + ".tmp"
	dstFile, err := os.OpenFile(tmpPath, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o600)
	if err != nil {
		return fmt.Errorf("open temp dest: %w", err)
	}
	defer func() { _ = dstFile.Close() }()

	if _, err := io.Copy(dstFile, srcFile); err != nil {
		return fmt.Errorf("copy config: %w", err)
	}

	if err := dstFile.Close(); err != nil {
		return fmt.Errorf("close temp dest: %w", err)
	}
	if err := os.Rename(tmpPath, dstPath); err != nil {
		return fmt.Errorf("rename config: %w", err)
	}
	return nil
}
