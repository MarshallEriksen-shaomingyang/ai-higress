"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import { useOverviewActivity } from "@/lib/swr/use-overview-metrics";
import { AreaChart, Area, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

function formatTimeLabel(iso: string): string {
  const d = new Date(iso);
  const hours = d.getHours().toString().padStart(2, "0");
  const minutes = d.getMinutes().toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

import { OverviewTimeRange } from "@/lib/swr/use-overview-metrics";

interface RecentActivityProps {
  timeRange?: OverviewTimeRange;
}

export function RecentActivity({ timeRange = "today" }: RecentActivityProps) {
  const { t } = useI18n();
  const { activity, loading } = useOverviewActivity({
    time_range: timeRange,
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
    <Card className="border-none shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">{t("overview.recent_activity")}</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && !hasData ? (
          <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
            {t("overview.recent_activity_placeholder")}
          </div>
        ) : !hasData ? (
          <div className="h-48 flex items-center justify-center text-sm text-muted-foreground">
            {t("overview.recent_activity_placeholder")}
          </div>
        ) : (
          <ChartContainer
            config={{
              total: {
                label: t("chart.requests"),
                color: "hsl(var(--foreground))",
              },
              errors: {
                label: t("chart.errors"),
                color: "hsl(var(--destructive))",
              },
            }}
            className="h-40 w-full"
          >
            <AreaChart 
              data={chartData}
              margin={{ top: 5, right: 5, left: 0, bottom: 5 }}
            >
              <XAxis
                dataKey="time"
                tick={{ fontSize: 9 }}
                interval="preserveStartEnd"
                minTickGap={30}
                axisLine={false}
                tickLine={false}
                height={20}
              />
              <YAxis
                tick={{ fontSize: 9 }}
                allowDecimals={false}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <ChartTooltip
                content={<ChartTooltipContent />}
                cursor={{ stroke: "hsl(var(--muted-foreground))", strokeWidth: 1 }}
              />
              <Area
                type="monotone"
                dataKey="total"
                stroke="var(--color-total)"
                fill="var(--color-total)"
                fillOpacity={0.1}
                strokeWidth={1.5}
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="errors"
                stroke="var(--color-errors)"
                fill="var(--color-errors)"
                fillOpacity={0.1}
                strokeWidth={1}
                dot={false}
              />
            </AreaChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
