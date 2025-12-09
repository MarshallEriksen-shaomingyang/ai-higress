"use client";

import React, { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useOverviewActivity } from "@/lib/swr/use-overview-metrics";
import { useI18n } from "@/lib/i18n-context";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LineChart,
  Line,
} from "recharts";

function formatDateLabel(iso: string): string {
  const d = new Date(iso);
  const month = (d.getMonth() + 1).toString().padStart(2, "0");
  const day = d.getDate().toString().padStart(2, "0");
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  return `${month}-${day} ${hours}:${minutes}`;
}

export function MetricsCharts() {
  // 这里用最近 7 天的全局时间序列作为指标图的数据源
  const { t } = useI18n();
  const { activity, loading } = useOverviewActivity({
    time_range: "7d",
  });

  const tooltipLabels = useMemo(
    () => ({
      total: t("metrics.overview.tooltip.requests"),
      errors: t("metrics.overview.tooltip.errors"),
      latencyP95: t("metrics.overview.tooltip.latency_p95"),
      errorRatePct: t("metrics.overview.tooltip.error_rate"),
    }),
    [t]
  );

  const chartData = useMemo(() => {
    if (!activity) {
      return [];
    }
    const points = activity.points || [];
    if (!points.length) {
      return [];
    }

    return points.map((p) => ({
      time: formatDateLabel(p.window_start),
      total: p.total_requests,
      errors: p.error_requests,
      latencyP95: p.latency_p95_ms,
      errorRatePct: p.error_rate * 100,
    }));
  }, [activity]);

  const hasData = chartData.length > 0;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader>
          <CardTitle>{t("metrics.overview.request_volume")}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              {t("metrics.overview.loading")}
            </div>
          ) : !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              {t("metrics.overview.empty")}
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ left: 8, right: 16, top: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 10 }}
                    minTickGap={24}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: 12 }}
                    formatter={(value, name) => {
                      if (name === "total") {
                        return [value, tooltipLabels.total];
                      }
                      if (name === "errors") {
                        return [value, tooltipLabels.errors];
                      }
                      return [value, tooltipLabels[name as keyof typeof tooltipLabels] ?? name];
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="total"
                    name="total"
                    stroke="#16a34a"
                    fill="#16a34a33"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                  <Area
                    type="monotone"
                    dataKey="errors"
                    name="errors"
                    stroke="#ef4444"
                    fill="#ef444433"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("metrics.overview.latency_error_rate")}</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              {t("metrics.overview.loading")}
            </div>
          ) : !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              {t("metrics.overview.empty")}
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ left: 8, right: 16, top: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 10 }}
                    minTickGap={24}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tickFormatter={(v) => `${v.toFixed(0)}%`}
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{ fontSize: 12 }}
                    formatter={(value, name) => {
                      if (name === "latencyP95") {
                        return [`${value} ms`, tooltipLabels.latencyP95];
                      }
                      if (name === "errorRatePct") {
                        return [`${(Number(value)).toFixed(2)}%`, tooltipLabels.errorRatePct];
                      }
                      return [value, tooltipLabels[name as keyof typeof tooltipLabels] ?? name];
                    }}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="latencyP95"
                    name="latencyP95"
                    stroke="#0f766e"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="errorRatePct"
                    name="errorRatePct"
                    stroke="#ef4444"
                    strokeWidth={1.5}
                    dot={false}
                    activeDot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
