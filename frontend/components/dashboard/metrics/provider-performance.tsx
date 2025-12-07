"use client";

import React, { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useActiveProvidersOverview } from "@/lib/swr/use-overview-metrics";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

export function ProviderPerformance() {
  const { data, loading } = useActiveProvidersOverview({
    time_range: "7d",
  });

  const chartData = useMemo(() => {
    if (!data) {
      return [];
    }
    const items = data.items || [];
    return items.map((item) => ({
      provider: item.provider_id,
      latency: item.latency_p95_ms ?? 0,
      successRatePct: item.success_rate * 100,
    }));
  }, [data]);

  const hasData = chartData.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Provider Performance</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !hasData ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            Loading provider metrics...
          </div>
        ) : !hasData ? (
          <div className="h-80 flex items-center justify-center text-muted-foreground">
            No provider metrics
          </div>
        ) : (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                margin={{ top: 16, left: 8, right: 16, bottom: 24 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="provider"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  label={{
                    value: "P95 Latency (ms)",
                    angle: -90,
                    position: "insideLeft",
                    fontSize: 11,
                  }}
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
                    if (name === "latency") {
                      return [`${value} ms`, "P95 Latency"];
                    }
                    if (name === "successRatePct") {
                      return [`${(Number(value)).toFixed(1)}%`, "Success Rate"];
                    }
                    return [value, name];
                  }}
                />
                <Bar
                  yAxisId="left"
                  dataKey="latency"
                  name="latency"
                  fill="#0f766e"
                  radius={4}
                />
                <Bar
                  yAxisId="right"
                  dataKey="successRatePct"
                  name="successRatePct"
                  fill="#22c55e"
                  radius={4}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
