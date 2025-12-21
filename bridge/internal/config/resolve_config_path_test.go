package config_test

import (
	"os"
	"path/filepath"
	"testing"

	"bridge/internal/config"
)

func TestResolveConfigPath_PrefersProjectRootConfig(t *testing.T) {
	root := t.TempDir()
	if err := os.MkdirAll(filepath.Join(root, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir .git: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(root, ".ai-bridge"), 0o755); err != nil {
		t.Fatalf("mkdir .ai-bridge: %v", err)
	}
	cfgPath := filepath.Join(root, ".ai-bridge", "config.yaml")
	if err := os.WriteFile(cfgPath, []byte("version: \"1.0\"\n"), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}
	sub := filepath.Join(root, "nested", "dir")
	if err := os.MkdirAll(sub, 0o755); err != nil {
		t.Fatalf("mkdir sub: %v", err)
	}

	oldWd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	t.Cleanup(func() { _ = os.Chdir(oldWd) })
	if err := os.Chdir(sub); err != nil {
		t.Fatalf("chdir: %v", err)
	}

	got := config.ResolveConfigPath("")
	if got != cfgPath {
		t.Fatalf("expected %q, got %q", cfgPath, got)
	}
}
