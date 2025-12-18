"use client";

import { useState } from "react";
import { CostByProviderChart } from "./cost-by-provider-chart";
import type { DashboardV2ProviderCostItem } from "@/lib/api-types";
import { Button } from "@/components/ui/button";

/**
 * 模拟数据生成器
 */
function generateMockData(): DashboardV2ProviderCostItem[] {
  const providers = [
    "OpenAI",
    "Anthropic",
    "Google",
    "Azure",
    "AWS Bedrock",
    "Cohere",
    "Mistral",
  ];

  return providers.map((provider) => ({
    provider_id: provider,
    credits_spent: Math.random() * 1000 + 100,
    transactions: Math.floor(Math.random() * 500) + 50,
  }));
}

export function CostByProviderChartDemo() {
  const [data, setData] = useState<DashboardV2ProviderCostItem[]>(generateMockData());
  const [isLoading, setIsLoading] = useState(false);
  const [showError, setShowError] = useState(false);
  const [showEmpty, setShowEmpty] = useState(false);

  const handleRefresh = () => {
    setIsLoading(true);
    setShowError(false);
    setShowEmpty(false);
    setTimeout(() => {
      setData(generateMockData());
      setIsLoading(false);
    }, 1000);
  };

  const handleToggleError = () => {
    setShowError(!showError);
    setShowEmpty(false);
  };

  const handleToggleEmpty = () => {
    setShowEmpty(!showEmpty);
    setShowError(false);
  };

  const displayData = showEmpty ? [] : data;
  const error = showError ? new Error("Failed to fetch cost data") : undefined;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Button onClick={handleRefresh} variant="outline" size="sm">
          刷新数据
        </Button>
        <Button onClick={handleToggleError} variant="outline" size="sm">
          {showError ? "隐藏错误" : "显示错误"}
        </Button>
        <Button onClick={handleToggleEmpty} variant="outline" size="sm">
          {showEmpty ? "显示数据" : "显示空态"}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CostByProviderChart
          data={displayData}
          isLoading={isLoading}
          error={error}
        />
      </div>

      <div className="mt-8 p-4 bg-muted rounded-lg">
        <h3 className="text-sm font-medium mb-2">当前数据（按 credits_spent 降序）：</h3>
        <pre className="text-xs overflow-auto">
          {JSON.stringify(
            [...displayData].sort((a, b) => b.credits_spent - a.credits_spent),
            null,
            2
          )}
        </pre>
      </div>
    </div>
  );
}
