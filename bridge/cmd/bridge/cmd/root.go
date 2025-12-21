package cmd

import (
	"fmt"
	"os"

	"bridge/internal/logging"

	"github.com/spf13/cobra"
)

var (
	globalConfigFile string
	globalLogFormat  string
	globalLogLevel   string
)

func NewRootCmd() *cobra.Command {
	rootCmd := &cobra.Command{
		Use:           "bridge",
		Short:         "AI Bridge (MCP Agent + Tunnel Gateway)",
		SilenceUsage:  true,
		SilenceErrors: true,
		PersistentPreRunE: func(cmd *cobra.Command, args []string) error {
			logger, err := logging.NewLogger(logging.Options{
				Level:  globalLogLevel,
				Format: globalLogFormat,
			})
			if err != nil {
				return err
			}
			cmd.SetContext(logging.WithLogger(cmd.Context(), logger))
			return nil
		},
	}

	rootCmd.PersistentFlags().StringVar(
		&globalConfigFile,
		"config",
		"",
		"config file (default: search up for .ai-bridge/config.yaml, fallback: ~/.ai-bridge/config.yaml)",
	)
	rootCmd.PersistentFlags().StringVar(&globalLogFormat, "log-format", "text", "log format: text|json")
	rootCmd.PersistentFlags().StringVar(&globalLogLevel, "log-level", "info", "log level: debug|info|warn|error")

	rootCmd.AddCommand(NewConfigCmd())
	rootCmd.AddCommand(NewAgentCmd())
	rootCmd.AddCommand(NewGatewayCmd())

	return rootCmd
}

func Execute() {
	if err := NewRootCmd().Execute(); err != nil {
		_, _ = fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(1)
	}
}

func GetConfigFileFlag() string {
	return globalConfigFile
}
