"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import type { DashboardV2PulseDataPoint } from "@/lib/api-types";
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";

interface RequestsErrorsChartProps {
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
 * 补零：确保数据连续，缺失的分钟补零（优化版：减少不必要的补零）
 */
function fillMissingMinutes(data: DashboardV2PulseDataPoint[]): DashboardV2PulseDataPoint[] {
  if (!data || data.length === 0) {
    return [];
  }

  // 如果数据点少于 10 个，直接返回排序后的数据，不补零
  if (data.length < 10) {
    return [...data].sort(
      (a, b) => new Date(a.window_start).getTime() - new Date(b.window_start).getTime()
    );
  }

  // 按时间排序
  const sorted = [...data].sort(
    (a, b) => new Date(a.window_start).getTime() - new Date(b.window_start).getTime()
  );

  // 只在数据点之间有较大间隙时才补零（超过 5 分钟）
  const firstPoint = sorted[0];
  if (!firstPoint) {
    return [];
  }
  
  const filled: DashboardV2PulseDataPoint[] = [firstPoint];
  
  for (let i = 1; i < sorted.length; i++) {
    const prevPoint = sorted[i - 1];
    const currPoint = sorted[i];
    
    if (!prevPoint || !currPoint) {
      continue;
    }
    
    const prevTime = new Date(prevPoint.window_start).getTime();
    const currTime = new Date(currPoint.window_start).getTime();
    const gap = (currTime - prevTime) / (60 * 1000); // 分钟数
    
    // 只有间隙超过 5 分钟才补零
    if (gap > 5) {
      let fillTime = prevTime + 60 * 1000;
      while (fillTime < currTime) {
        filled.push({
          window_start: new Date(fillTime).toISOString(),
          total_requests: 0,
          error_4xx_requests: 0,
          error_5xx_requests: 0,
          error_429_requests: 0,
          error_timeout_requests: 0,
          latency_p50_ms: 0,
          latency_p95_ms: 0,
          latency_p99_ms: 0,
        });
        fillTime += 60 * 1000;
      }
    }
    
    filled.push(currPoint);
  }

  return filled;
}

export function RequestsErrorsChart({ data, isLoading, error }: RequestsErrorsChartProps) {
  const { t } = useI18n();

  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }

    // 补零处理（优化后减少了计算量）
    const filledData = fillMissingMinutes(data);

    // 转换为图表数据格式，并限制数据点数量（最多 200 个点）
    const step = Math.max(1, Math.floor(filledData.length / 200));
    return filledData
      .filter((_, index) => index % step === 0)
      .map((point) => ({
        time: formatTime(point.window_start),
        total_requests: point.total_requests,
        error_4xx: point.error_4xx_requests,
        error_5xx: point.error_5xx_requests,
        error_429: point.error_429_requests,
        error_timeout: point.error_timeout_requests,
      }));
  }, [data]);

  const hasData = chartData.length > 0;

  // 图表配置
  const chartConfig = {
    total_requests: {
      label: t("dashboard_v2.kpi.total_requests"),
      color: "hsl(var(--chart-1))",
    },
    error_4xx: {
      label: t("dashboard_v2.chart.error.4xx"),
      color: "hsl(var(--chart-4))",
    },
    error_5xx: {
      label: t("dashboard_v2.chart.error.5xx"),
      color: "hsl(var(--destructive))",
    },
    error_429: {
      label: t("dashboard_v2.chart.error.429"),
      color: "hsl(var(--warning))",
    },
    error_timeout: {
      label: t("dashboard_v2.chart.error.timeout"),
      color: "hsl(var(--chart-5))",
    },
  };

  return (
    <Card className="border-none shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">
          {t("dashboard_v2.chart.requests_errors.title")}
        </CardTitle>
        <CardDescription>{t("dashboard_v2.chart.requests_errors.subtitle")}</CardDescription>
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
            <ComposedChart
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

              {/* Y轴 */}
              <YAxis
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickLine={{ stroke: "hsl(var(--border))" }}
                axisLine={{ stroke: "hsl(var(--border))" }}
                width={60}
                allowDecimals={false}
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
                iconType="rect"
              />

              {/* 堆叠柱状图 - 错误 */}
              <Bar
                dataKey="error_4xx"
                name={chartConfig.error_4xx.label}
                fill="var(--color-error_4xx)"
                stackId="errors"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="error_5xx"
                name={chartConfig.error_5xx.label}
                fill="var(--color-error_5xx)"
                stackId="errors"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="error_429"
                name={chartConfig.error_429.label}
                fill="var(--color-error_429)"
                stackId="errors"
                radius={[0, 0, 0, 0]}
              />
              <Bar
                dataKey="error_timeout"
                name={chartConfig.error_timeout.label}
                fill="var(--color-error_timeout)"
                stackId="errors"
                radius={[4, 4, 0, 0]}
              />

              {/* 折线图 - 总请求数 */}
              <Line
                type="monotone"
                dataKey="total_requests"
                name={chartConfig.total_requests.label}
                stroke="var(--color-total_requests)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
