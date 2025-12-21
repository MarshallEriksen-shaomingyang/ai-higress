package cmd

import (
	"fmt"
	"os"

	"bridge/internal/config"
	"bridge/internal/logging"

	"github.com/spf13/cobra"
)

func NewConfigCmd() *cobra.Command {
	configCmd := &cobra.Command{
		Use:   "config",
		Short: "Manage bridge config",
	}

	configCmd.AddCommand(newConfigPathCmd())
	configCmd.AddCommand(newConfigValidateCmd())
	configCmd.AddCommand(newConfigApplyCmd())
	return configCmd
}

func newConfigPathCmd() *cobra.Command {
	return &cobra.Command{
		Use:   "path",
		Short: "Print resolved config path",
		RunE: func(cmd *cobra.Command, args []string) error {
			fmt.Fprintln(os.Stdout, config.ResolveConfigPath(""))
			return nil
		},
	}
}

func newConfigValidateCmd() *cobra.Command {
	var file string
	validateCmd := &cobra.Command{
		Use:   "validate",
		Short: "Validate a config file",
		RunE: func(cmd *cobra.Command, args []string) error {
			logger := logging.FromContext(cmd.Context())
			cfg, err := config.Load(config.LoadOptions{
				ConfigFile: firstNonEmpty(file, GetConfigFileFlag()),
			})
			if err != nil {
				return err
			}
			if err := cfg.Validate(); err != nil {
				return err
			}
			logger.Info("config valid", "agent_id", cfg.Agent.ID, "server_url", cfg.Server.URL)
			fmt.Fprintln(os.Stdout, "ok")
			return nil
		},
	}
	validateCmd.Flags().StringVar(&file, "file", "", "config file path (default: search up for .ai-bridge/config.yaml, fallback: ~/.ai-bridge/config.yaml)")
	return validateCmd
}

func newConfigApplyCmd() *cobra.Command {
	var file string
	applyCmd := &cobra.Command{
		Use:   "apply",
		Short: "Apply config file to default location",
		RunE: func(cmd *cobra.Command, args []string) error {
			logger := logging.FromContext(cmd.Context())
			src := firstNonEmpty(file, GetConfigFileFlag())
			if src == "" {
				return fmt.Errorf("missing --file (or --config)")
			}
			dst := config.DefaultConfigPath()
			if err := config.ApplyFile(src, dst); err != nil {
				return err
			}
			logger.Info("config applied", "path", dst)
			fmt.Fprintln(os.Stdout, dst)
			return nil
		},
	}
	applyCmd.Flags().StringVar(&file, "file", "", "source config file path")
	return applyCmd
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}
