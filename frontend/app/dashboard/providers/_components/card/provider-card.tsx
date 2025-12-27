"use client";

import { useMemo } from "react";
import type { Provider } from "@/http/provider";
import type { DashboardV2ProviderMetricsItem } from "@/lib/api-types";
import { useI18n } from "@/lib/i18n-context";
import { AdaptiveCard, CardContent, CardFooter, CardHeader } from "@/components/cards/adaptive-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Database,
  Eye,
  Key,
  Pencil,
  Settings,
  Trash2,
} from "lucide-react";

function formatCompactNumber(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`;
  return `${value}`;
}

function formatPercent01(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMs(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "--";
  return `${Math.round(value)}ms`;
}

function formatQps(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "--";
  if (value >= 10) return value.toFixed(1);
  if (value >= 1) return value.toFixed(2);
  return value.toFixed(3);
}

function Sparkline({
  values,
  strokeClassName,
}: {
  values: number[];
  strokeClassName: string;
}) {
  const { d, hasData } = useMemo(() => {
    const width = 140;
    const height = 38;
    const padding = 2;

    const sanitized = values.filter((v) => Number.isFinite(v));
    if (sanitized.length < 2) {
      return { d: "", hasData: false };
    }

    const min = Math.min(...sanitized);
    const max = Math.max(...sanitized);
    const range = max - min || 1;

    const pts = values.map((v, i) => {
      const x =
        padding + (i * (width - padding * 2)) / (values.length - 1);
      const ratio = Number.isFinite(v) ? (v - min) / range : 0;
      const y = height - padding - ratio * (height - padding * 2);
      return { x, y };
    });

    const path = pts
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
      .join(" ");

    return { d: path, hasData: true };
  }, [values]);

  if (!hasData) {
    return (
      <div className="h-[38px] w-[140px] rounded-md bg-muted/40" />
    );
  }

  return (
    <svg
      viewBox="0 0 140 38"
      className="h-[38px] w-[140px]"
      aria-hidden="true"
    >
      <path
        d={d}
        fill="none"
        strokeWidth="2"
        className={strokeClassName}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function statusBadgeVariant(providerStatus: Provider["status"]) {
  if (providerStatus === "healthy") return "default";
  if (providerStatus === "degraded") return "secondary";
  return "destructive";
}

export interface ProviderCardProps {
  provider: Provider;
  metrics?: DashboardV2ProviderMetricsItem;
  isMetricsLoading?: boolean;
  onConfigure?: (provider: Provider) => void;
  onDelete?: (providerId: string) => void;
  onViewDetails?: (providerId: string) => void;
  onViewModels?: (providerId: string) => void;
  onManageKeys?: (providerId: string) => void;
  canModify?: boolean;
  canManageKeys?: boolean;
}

export function ProviderCard({
  provider,
  metrics,
  isMetricsLoading,
  onConfigure,
  onDelete,
  onViewDetails,
  onViewModels,
  onManageKeys,
  canModify = true,
  canManageKeys = true,
}: ProviderCardProps) {
  const { t } = useI18n();

  const qpsSeries = useMemo(
    () => (metrics?.points ?? []).map((p) => p.qps),
    [metrics]
  );
  const errorRateSeries = useMemo(
    () => (metrics?.points ?? []).map((p) => p.error_rate),
    [metrics]
  );

  const latencyMs =
    metrics?.latency_p95_ms && metrics.latency_p95_ms > 0
      ? metrics.latency_p95_ms
      : provider.latest_test_result?.latency_ms ?? null;

  const headerRight = isMetricsLoading ? (
    <span className="text-xs text-muted-foreground">
      {t("providers.loading")}
    </span>
  ) : (
    <span className="text-xs text-muted-foreground">
      {t("my_providers.card_latency_p95")}:{" "}
      <span className="text-foreground">
        {formatMs(latencyMs)}
      </span>
    </span>
  );

  return (
    <AdaptiveCard className="group" showDecor={false}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0 space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-md border bg-muted/40 flex items-center justify-center text-sm font-semibold">
                {(provider.name || provider.provider_id || "?")
                  .slice(0, 1)
                  .toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="truncate text-base font-semibold">
                  {provider.name || provider.provider_id}
                </div>
                <div className="truncate text-xs text-muted-foreground font-mono">
                  {provider.provider_id}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={statusBadgeVariant(provider.status)}>
                {provider.status === "healthy"
                  ? t("providers.status_healthy")
                  : provider.status === "degraded"
                    ? t("providers.status_degraded")
                    : t("providers.status_unhealthy")}
              </Badge>
              <Badge variant="outline">
                {provider.transport === "claude_cli"
                  ? "Claude CLI"
                  : provider.transport.toUpperCase()}
              </Badge>
              <Badge variant="outline">
                {provider.provider_type === "native"
                  ? t("providers.type_native")
                  : t("providers.type_aggregator")}
              </Badge>
            </div>
          </div>

          <div className="shrink-0 text-right">{headerRight}</div>
        </div>
      </CardHeader>

      <CardContent className="pb-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">
              {t("my_providers.card_requests_qps")}
            </div>
            <div className="flex items-end justify-between gap-3">
              <div className="text-sm font-semibold">
                {isMetricsLoading
                  ? "--"
                  : metrics
                    ? formatQps(metrics.qps)
                    : "--"}
              </div>
              <Sparkline
                values={qpsSeries}
                strokeClassName="stroke-emerald-500/70"
              />
            </div>
          </div>

          <div className="space-y-1">
            <div className="text-xs text-muted-foreground">
              {t("my_providers.card_error_rate")}
            </div>
            <div className="flex items-end justify-between gap-3">
              <div className="text-sm font-semibold">
                {isMetricsLoading
                  ? "--"
                  : metrics
                    ? formatPercent01(metrics.error_rate)
                    : "--"}
              </div>
              <Sparkline
                values={errorRateSeries}
                strokeClassName="stroke-rose-500/70"
              />
            </div>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between gap-3">
          <div className="text-xs text-muted-foreground">
            {t("providers.table_column_models")}:{" "}
            <span className="text-foreground">
              {provider.static_models?.length
                ? formatCompactNumber(provider.static_models.length)
                : "--"}
            </span>
          </div>

          <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            {onViewDetails && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onViewDetails(provider.provider_id)}
                  >
                    <Eye className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {t("providers.action_view_details")}
                </TooltipContent>
              </Tooltip>
            )}

            {onViewModels && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onViewModels(provider.provider_id)}
                  >
                    <Database className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {t("providers.action_view_models")}
                </TooltipContent>
              </Tooltip>
            )}

            {canManageKeys && onManageKeys && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    data-testid="provider-card-manage-keys"
                    onClick={() => onManageKeys(provider.provider_id)}
                  >
                    <Key className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {t("providers.action_manage_keys")}
                </TooltipContent>
              </Tooltip>
            )}

            {canModify && onConfigure && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onConfigure(provider)}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{t("providers.action_edit")}</TooltipContent>
              </Tooltip>
            )}

            {canModify && onDelete && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive"
                    onClick={() => onDelete(provider.provider_id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{t("providers.action_delete")}</TooltipContent>
              </Tooltip>
            )}
          </div>
        </div>
      </CardContent>

      <CardFooter className="pt-0">
        <Button
          className="w-full"
          onClick={() => onConfigure?.(provider)}
          disabled={!onConfigure}
        >
          <Settings className="h-4 w-4 mr-2" />
          {t("my_providers.card_configure")}
        </Button>
      </CardFooter>
    </AdaptiveCard>
  );
}
