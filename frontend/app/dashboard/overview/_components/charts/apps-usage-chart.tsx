"use client";

import { useMemo } from "react";
import { AdaptiveCard, CardContent } from "@/components/cards/adaptive-card";
import { useI18n } from "@/lib/i18n-context";
import type { UserAppUsageMetrics } from "@/lib/api-types";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

interface AppsUsageChartProps {
  data: UserAppUsageMetrics[];
  isLoading: boolean;
  error?: Error;
  limit: number;
}

function formatCount(value: number): string {
  return value.toLocaleString();
}

function truncateLabel(label: string, maxLen: number = 16): string {
  if (!label) return "";
  if (label.length <= maxLen) return label;
  return `${label.slice(0, maxLen)}…`;
}

export function AppsUsageChart({ data, isLoading, error, limit }: AppsUsageChartProps) {
  const { t } = useI18n();

  const sorted = useMemo(() => {
    return [...(data || [])]
      .filter((item) => item && typeof item.total_requests === "number")
      .sort((a, b) => b.total_requests - a.total_requests)
      .slice(0, Math.max(1, limit));
  }, [data, limit]);

  const chartData = useMemo(() => {
    return sorted.map((item) => ({
      app_name: item.app_name,
      requests: item.total_requests,
    }));
  }, [sorted]);

  const hasData = chartData.length > 0;

  const heightClass =
    chartData.length > 8 ? "h-96" : chartData.length > 5 ? "h-80" : "h-64";

  const chartConfig = {
    requests: {
      label: t("dashboard_v2.chart.apps_usage.requests"),
      color: "hsl(var(--chart-1))",
    },
  };

  return (
    <AdaptiveCard
      title={t("dashboard_v2.chart.apps_usage.title")}
      description={t("dashboard_v2.chart.apps_usage.subtitle", { limit })}
    >
      <CardContent>
        {isLoading && !hasData ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            {t("dashboard_v2.loading")}
          </div>
        ) : error ? (
          <div className="h-64 flex flex-col items-center justify-center gap-2">
            <p className="text-sm text-destructive">{t("dashboard_v2.error")}</p>
            <p className="text-xs text-muted-foreground">{error.message}</p>
          </div>
        ) : !hasData ? (
          <div className="h-64 flex items-center justify-center text-sm text-muted-foreground">
            {t("dashboard_v2.empty")}
          </div>
        ) : (
          <ChartContainer config={chartConfig} className={`${heightClass} w-full`}>
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 10, right: 20, left: 10, bottom: 10 }}
              barCategoryGap={10}
            >
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.25}
                horizontal={false}
              />

              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                allowDecimals={false}
                tickFormatter={formatCount}
              />

              <YAxis
                type="category"
                dataKey="app_name"
                width={130}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={false}
                axisLine={{ stroke: "hsl(var(--border))" }}
                tickFormatter={(value) => truncateLabel(String(value))}
              />

              <ChartTooltip
                content={<ChartTooltipContent />}
                cursor={{ fill: "hsl(var(--muted))", opacity: 0.15 }}
              />

              <Bar
                dataKey="requests"
                name={chartConfig.requests.label}
                fill="var(--color-requests)"
                radius={[4, 4, 4, 4]}
                isAnimationActive={false}
              />
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </AdaptiveCard>
  );
}

