"use client";

import { useMemo } from "react";
import { AdaptiveCard, CardContent } from "@/components/cards/adaptive-card";
import { useI18n } from "@/lib/i18n-context";
import type { DashboardV2TokenDataPoint } from "@/lib/api-types";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Info } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface TokenUsageChartProps {
  data: DashboardV2TokenDataPoint[];
  bucket: "hour" | "day";
  isLoading: boolean;
  error?: Error;
  estimatedRequests?: number;
}

/**
 * 格式化时间戳
 * - hour bucket: HH:mm 格式
 * - day bucket: MM-DD 格式
 */
function formatTime(isoString: string, bucket: "hour" | "day"): string {
  try {
    const date = new Date(isoString);
    if (bucket === "hour") {
      const hours = date.getHours().toString().padStart(2, "0");
      const minutes = date.getMinutes().toString().padStart(2, "0");
      return `${hours}:${minutes}`;
    } else {
      const month = (date.getMonth() + 1).toString().padStart(2, "0");
      const day = date.getDate().toString().padStart(2, "0");
      return `${month}-${day}`;
    }
  } catch {
    return "";
  }
}

/**
 * 格式化 Token 数量（添加千位分隔符）
 */
function formatTokenCount(count: number): string {
  return count.toLocaleString();
}

export function TokenUsageChart({
  data,
  bucket,
  isLoading,
  error,
  estimatedRequests = 0,
}: TokenUsageChartProps) {
  const { t } = useI18n();

  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }

    // 转换为图表数据格式，并限制数据点数量（最多 200 个点）
    const step = Math.max(1, Math.floor(data.length / 200));
    return data
      .filter((_, index) => index % step === 0)
      .map((point) => ({
        time: formatTime(point.window_start, bucket),
        input_tokens: point.input_tokens,
        output_tokens: point.output_tokens,
        total_tokens: point.total_tokens,
      }));
  }, [data, bucket]);

  const hasData = chartData.length > 0;
  const showEstimatedTooltip = estimatedRequests > 0;

  // 图表配置
  const chartConfig = {
    input_tokens: {
      label: t("dashboard_v2.chart.token_usage.input_tokens"),
      color: "hsl(217, 91%, 60%)", // 蓝色
    },
    output_tokens: {
      label: t("dashboard_v2.chart.token_usage.output_tokens"),
      color: "hsl(142, 76%, 36%)", // 绿色
    },
    total_tokens: {
      label: t("dashboard_v2.chart.token_usage.total_tokens"),
      color: "hsl(280, 65%, 60%)", // 紫色 - 总量趋势线
    },
  };

  return (
    <AdaptiveCard
      title={t("dashboard_v2.chart.token_usage.title")}
      description={t("dashboard_v2.chart.token_usage.subtitle")}
      headerAction={
        showEstimatedTooltip ? (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-1 text-xs text-muted-foreground cursor-help">
                  <Info className="h-4 w-4" />
                </div>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-xs">
                <p className="text-xs">
                  {t("dashboard_v2.chart.token_usage.estimated_tooltip", {
                    count: estimatedRequests,
                  })}
                </p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : undefined
      }
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
          <ChartContainer config={chartConfig} className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
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
                  minTickGap={bucket === "hour" ? 60 : 30}
                />

                {/* Y轴 */}
                <YAxis
                  tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={{ stroke: "hsl(var(--border))" }}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                  width={80}
                  allowDecimals={false}
                  tickFormatter={formatTokenCount}
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
                  cursor={{ fill: "hsl(var(--muted))", opacity: 0.2 }}
                />

                {/* 图例 */}
                <Legend
                  wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }}
                  iconType="rect"
                />

                {/* 堆叠柱状图 - Input Tokens */}
                <Bar
                  dataKey="input_tokens"
                  name={chartConfig.input_tokens.label}
                  fill="var(--color-input_tokens)"
                  stackId="tokens"
                  radius={[0, 0, 0, 0]}
                  isAnimationActive={false}
                />

                {/* 堆叠柱状图 - Output Tokens */}
                <Bar
                  dataKey="output_tokens"
                  name={chartConfig.output_tokens.label}
                  fill="var(--color-output_tokens)"
                  stackId="tokens"
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />

                {/* 折线图 - Total Tokens 趋势 */}
                <Line
                  type="monotone"
                  dataKey="total_tokens"
                  name={chartConfig.total_tokens.label}
                  stroke="var(--color-total_tokens)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </ChartContainer>
        )}
      </CardContent>
    </AdaptiveCard>
  );
}
