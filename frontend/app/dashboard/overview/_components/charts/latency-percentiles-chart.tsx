"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import type { DashboardV2PulseDataPoint } from "@/lib/api-types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

interface LatencyPercentilesChartProps {
  data: DashboardV2PulseDataPoint[];
  isLoading: boolean;
  error?: Error;
}

/**
 * 格式化时间戳为 HH:mm 格式
 */
function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const hours = date.getHours().toString().padStart(2, "0");
    const minutes = date.getMinutes().toString().padStart(2, "0");
    return `${hours}:${minutes}`;
  } catch {
    return "";
  }
}

/**
 * 补零：确保数据连续，缺失的分钟补零
 */
function fillMissingMinutes(data: DashboardV2PulseDataPoint[]): DashboardV2PulseDataPoint[] {
  if (!data || data.length === 0) {
    return [];
  }

  // 按时间排序
  const sorted = [...data].sort(
    (a, b) => new Date(a.window_start).getTime() - new Date(b.window_start).getTime()
  );

  const filled: DashboardV2PulseDataPoint[] = [];
  const firstPoint = sorted[0];
  const lastPoint = sorted[sorted.length - 1];
  
  if (!firstPoint || !lastPoint) {
    return sorted;
  }
  
  const startTime = new Date(firstPoint.window_start);
  const endTime = new Date(lastPoint.window_start);

  // 创建一个 Map 用于快速查找
  const dataMap = new Map<string, DashboardV2PulseDataPoint>();
  sorted.forEach((point) => {
    dataMap.set(point.window_start, point);
  });

  // 遍历每一分钟
  let currentTime = new Date(startTime);
  while (currentTime <= endTime) {
    const timeKey = currentTime.toISOString();
    const existingData = dataMap.get(timeKey);

    if (existingData) {
      filled.push(existingData);
    } else {
      // 补零
      filled.push({
        window_start: timeKey,
        total_requests: 0,
        error_4xx_requests: 0,
        error_5xx_requests: 0,
        error_429_requests: 0,
        error_timeout_requests: 0,
        latency_p50_ms: 0,
        latency_p95_ms: 0,
        latency_p99_ms: 0,
      });
    }

    // 增加一分钟
    currentTime = new Date(currentTime.getTime() + 60 * 1000);
  }

  return filled;
}

export function LatencyPercentilesChart({ data, isLoading, error }: LatencyPercentilesChartProps) {
  const { t } = useI18n();

  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }

    // 补零处理
    const filledData = fillMissingMinutes(data);

    // 转换为图表数据格式
    return filledData.map((point) => ({
      time: formatTime(point.window_start),
      p50: point.latency_p50_ms,
      p95: point.latency_p95_ms,
      p99: point.latency_p99_ms,
    }));
  }, [data]);

  const hasData = chartData.length > 0;

  // 图表配置
  const chartConfig = {
    p50: {
      label: t("dashboard_v2.chart.latency.p50"),
      color: "hsl(var(--chart-2))",
    },
    p95: {
      label: t("dashboard_v2.chart.latency.p95"),
      color: "hsl(var(--chart-3))",
    },
    p99: {
      label: t("dashboard_v2.chart.latency.p99"),
      color: "hsl(var(--chart-4))",
    },
  };

  return (
    <Card className="border-none shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">
          {t("dashboard_v2.chart.latency_percentiles.title")}
        </CardTitle>
        <CardDescription>{t("dashboard_v2.chart.latency_percentiles.subtitle")}</CardDescription>
      </CardHeader>
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
          <ChartContainer config={chartConfig} className="h-64 w-full">
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
            >
              {/* X轴 */}
              <XAxis
                dataKey="time"
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                height={40}
                interval="preserveStartEnd"
                minTickGap={60}
              />

              {/* Y轴 - 显示延迟单位 (ms) */}
              <YAxis
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                width={60}
                allowDecimals={false}
                label={{
                  value: "ms",
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 11, fill: "hsl(var(--muted-foreground))" },
                }}
              />

              {/* 网格 */}
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                opacity={0.3}
              />

              {/* Tooltip */}
              <ChartTooltip
                content={<ChartTooltipContent />}
                cursor={{ stroke: "hsl(var(--muted-foreground))", strokeWidth: 1, strokeDasharray: "5 5" }}
              />

              {/* 图例 */}
              <Legend
                wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }}
                iconType="line"
              />

              {/* 三条折线 - P50/P95/P99 */}
              <Line
                type="monotone"
                dataKey="p50"
                name={chartConfig.p50.label}
                stroke="var(--color-p50)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={true}
                animationDuration={800}
              />
              <Line
                type="monotone"
                dataKey="p95"
                name={chartConfig.p95.label}
                stroke="var(--color-p95)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={true}
                animationDuration={800}
              />
              <Line
                type="monotone"
                dataKey="p99"
                name={chartConfig.p99.label}
                stroke="var(--color-p99)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={true}
                animationDuration={800}
              />
            </LineChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
