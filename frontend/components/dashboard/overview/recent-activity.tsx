"use client";

import React, { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import { useOverviewActivity } from "@/lib/swr/use-overview-metrics";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

function formatTimeLabel(iso: string): string {
  const d = new Date(iso);
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

export function RecentActivity() {
  const { t } = useI18n();
  const { activity, loading } = useOverviewActivity({
    time_range: "today",
  });

  const chartData = useMemo(() => {
    if (!activity) {
      return [];
    }
    const points = activity.points || [];
    if (!points.length) {
      return [];
    }

    // 取最近 60 个时间桶（大约最近 1 小时），按时间顺序
    const recent = points.slice(-60);
    return recent.map((p) => ({
      time: formatTimeLabel(p.window_start),
      total: p.total_requests,
      errors: p.error_requests,
      successRate: p.total_requests > 0 ? 1 - p.error_rate : 0,
    }));
  }, [activity]);

  const hasData = chartData.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("overview.recent_activity")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !hasData ? (
          <div className="h-64 flex items-center justify-center text-muted-foreground">
            {t("overview.recent_activity_placeholder")}
          </div>
        ) : !hasData ? (
          <div className="h-64 flex items-center justify-center text-muted-foreground">
            {t("overview.recent_activity_placeholder")}
          </div>
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ left: 8, right: 16, top: 16 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="time"
                  tick={{ fontSize: 11 }}
                  interval="preserveStartEnd"
                  minTickGap={24}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{
                    fontSize: 12,
                  }}
                  formatter={(value, name) => {
                    if (name === "total") {
                      return [value, "Requests"];
                    }
                    if (name === "errors") {
                      return [value, "Errors"];
                    }
                    if (name === "successRate") {
                      return [`${(Number(value) * 100).toFixed(1)}%`, "Success"];
                    }
                    return [value, name];
                  }}
                  labelFormatter={(label) => `${label}`}
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
  );
}
