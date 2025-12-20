package config

import (
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
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

func DefaultConfigPath() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return filepath.Join(".ai-bridge", "config.yaml")
	}
	return filepath.Join(home, ".ai-bridge", "config.yaml")
}

func Load(opts LoadOptions) (*Config, error) {
	v := viper.New()
	v.SetConfigType("yaml")
	v.SetEnvPrefix("AI_BRIDGE")
	v.AutomaticEnv()

	path := opts.ConfigFile
	if path == "" {
		path = DefaultConfigPath()
	}
	v.SetConfigFile(path)

	v.SetDefault("server.reconnect_initial", "1s")
	v.SetDefault("server.reconnect_max", "60s")

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
	for i, s := range c.MCPServers {
		if s.Name == "" {
			return fmt.Errorf("mcp_servers[%d].name is required", i)
		}
		if s.Command == "" && s.URL == "" {
			return fmt.Errorf("mcp_servers[%d] must set command or url", i)
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
