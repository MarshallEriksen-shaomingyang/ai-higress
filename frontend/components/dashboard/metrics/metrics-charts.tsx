"use client";

import React, { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useOverviewActivity } from "@/lib/swr/use-overview-metrics";
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
  const { activity, loading } = useOverviewActivity({
    time_range: "7d",
  });

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
          <CardTitle>Request Volume</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              Loading metrics...
            </div>
          ) : !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No metrics data
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
                        return [value, "Requests"];
                      }
                      if (name === "errors") {
                        return [value, "Errors"];
                      }
                      return [value, name];
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
          <CardTitle>Latency & Error Rate</CardTitle>
        </CardHeader>
        <CardContent>
          {loading && !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              Loading metrics...
            </div>
          ) : !hasData ? (
            <div className="h-64 flex items-center justify-center text-muted-foreground">
              No metrics data
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
                        return [`${value} ms`, "P95 Latency"];
                      }
                      if (name === "errorRatePct") {
                        return [`${(Number(value)).toFixed(2)}%`, "Error Rate"];
                      }
                      return [value, name];
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
