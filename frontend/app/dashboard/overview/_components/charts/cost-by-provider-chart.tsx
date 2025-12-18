"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import type { DashboardV2ProviderCostItem } from "@/lib/api-types";
import {
  PieChart,
  Pie,
  Cell,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ChartContainer, ChartTooltip } from "@/components/ui/chart";

interface CostByProviderChartProps {
  data: DashboardV2ProviderCostItem[];
  isLoading: boolean;
  error?: Error;
}

/**
 * 格式化 Credits 数量（添加千位分隔符）
 */
function formatCredits(credits: number): string {
  return credits.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * 格式化百分比
 */
function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
}

/**
 * 图表颜色配置（循环使用）
 */
const CHART_COLORS = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
];

export function CostByProviderChart({
  data,
  isLoading,
  error,
}: CostByProviderChartProps) {
  const { t } = useI18n();

  const chartData = useMemo(() => {
    if (!data || data.length === 0) {
      return [];
    }

    // 按 credits_spent 降序排序
    const sortedData = [...data].sort((a, b) => b.credits_spent - a.credits_spent);

    // 计算总 credits
    const totalCredits = sortedData.reduce((sum, item) => sum + item.credits_spent, 0);

    // 转换为图表数据格式，添加占比
    return sortedData.map((item, index) => ({
      provider_id: item.provider_id,
      credits_spent: item.credits_spent,
      percentage: totalCredits > 0 ? (item.credits_spent / totalCredits) * 100 : 0,
      color: CHART_COLORS[index % CHART_COLORS.length],
    }));
  }, [data]);

  const hasData = chartData.length > 0;

  // 图表配置
  const chartConfig = useMemo(() => {
    const config: Record<string, { label: string; color?: string }> = {};
    chartData.forEach((item) => {
      config[item.provider_id] = {
        label: item.provider_id,
        color: item.color,
      };
    });
    return config;
  }, [chartData]);

  // 自定义图例渲染
  const renderLegend = (props: any) => {
    const { payload } = props;
    return (
      <div className="flex flex-col gap-2 mt-4">
        {payload.map((entry: any, index: number) => {
          const item = chartData[index];
          if (!item) return null;
          return (
            <div key={`legend-${index}`} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-sm"
                  style={{ backgroundColor: entry.color }}
                />
                <span className="text-muted-foreground">{entry.value}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-medium">{formatCredits(item.credits_spent)}</span>
                <span className="text-muted-foreground">
                  ({formatPercentage(item.percentage)})
                </span>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  // 自定义 Tooltip
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || payload.length === 0) {
      return null;
    }

    const data = payload[0].payload;
    return (
      <div className="rounded-lg border bg-background p-3 shadow-md">
        <div className="flex flex-col gap-1">
          <p className="text-sm font-medium">{data.provider_id}</p>
          <p className="text-xs text-muted-foreground">
            {t("dashboard_v2.chart.cost.credits_label")}: {formatCredits(data.credits_spent)}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatPercentage(data.percentage)}
          </p>
        </div>
      </div>
    );
  };

  return (
    <Card className="border-none shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-medium">
          {t("dashboard_v2.chart.cost.title")}
        </CardTitle>
        <CardDescription>{t("dashboard_v2.chart.cost.subtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && !hasData ? (
          <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">
            {t("dashboard_v2.loading")}
          </div>
        ) : error ? (
          <div className="h-80 flex flex-col items-center justify-center gap-2">
            <p className="text-sm text-destructive">{t("dashboard_v2.error")}</p>
            <p className="text-xs text-muted-foreground">{error.message}</p>
          </div>
        ) : !hasData ? (
          <div className="h-80 flex items-center justify-center text-sm text-muted-foreground">
            {t("dashboard_v2.empty")}
          </div>
        ) : (
          <ChartContainer config={chartConfig} className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="credits_spent"
                  nameKey="provider_id"
                  cx="50%"
                  cy="40%"
                  innerRadius="50%"
                  outerRadius="70%"
                  paddingAngle={2}
                  isAnimationActive={true}
                  animationDuration={800}
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <ChartTooltip content={<CustomTooltip />} />
                <Legend content={renderLegend} />
              </PieChart>
            </ResponsiveContainer>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  );
}
