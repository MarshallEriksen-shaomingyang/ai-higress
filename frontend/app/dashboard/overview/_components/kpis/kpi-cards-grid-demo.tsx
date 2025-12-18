"use client";

import { useState } from "react";
import { KPICardsGrid } from "./kpi-cards-grid";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * KPI 卡片网格布局演示组件
 * 
 * 用于测试和展示响应式布局的不同状态：
 * - 正常数据显示
 * - 加载态
 * - 错误态
 */
export function KPICardsGridDemo() {
  const [state, setState] = useState<"normal" | "loading" | "error">("normal");

  // 模拟数据
  const mockData = {
    total_requests: 125430,
    credits_spent: 1234.56,
    latency_p95_ms: 856,
    error_rate: 0.0234, // 2.34%
    tokens: {
      input: 1234567,
      output: 987654,
      total: 2222221,
    },
  };

  return (
    <div className="space-y-6 p-6">
      <Card>
        <CardHeader>
          <CardTitle>KPI 卡片网格布局演示</CardTitle>
          <CardDescription>
            测试响应式布局和不同状态。调整浏览器窗口大小查看响应式效果。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button
              variant={state === "normal" ? "default" : "outline"}
              onClick={() => setState("normal")}
            >
              正常数据
            </Button>
            <Button
              variant={state === "loading" ? "default" : "outline"}
              onClick={() => setState("loading")}
            >
              加载中
            </Button>
            <Button
              variant={state === "error" ? "default" : "outline"}
              onClick={() => setState("error")}
            >
              错误状态
            </Button>
          </div>

          <div className="space-y-2 text-sm text-muted-foreground">
            <p><strong>响应式布局规则：</strong></p>
            <ul className="list-disc list-inside space-y-1">
              <li>桌面端（≥1024px）：四列布局</li>
              <li>平板端（768-1023px）：两列布局</li>
              <li>移动端（&lt;768px）：单列布局</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <KPICardsGrid
        data={state === "normal" ? mockData : undefined}
        isLoading={state === "loading"}
        error={state === "error" ? new Error("模拟错误") : undefined}
      />

      <Card>
        <CardHeader>
          <CardTitle>测试说明</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p><strong>如何测试响应式布局：</strong></p>
          <ol className="list-decimal list-inside space-y-1">
            <li>打开浏览器开发者工具（F12）</li>
            <li>切换到设备模拟模式（Ctrl+Shift+M 或 Cmd+Shift+M）</li>
            <li>选择不同的设备预设或手动调整窗口宽度</li>
            <li>观察卡片布局的变化：
              <ul className="list-disc list-inside ml-6 mt-1">
                <li>宽度 ≥1024px：应显示 4 列</li>
                <li>宽度 768-1023px：应显示 2 列</li>
                <li>宽度 &lt;768px：应显示 1 列</li>
              </ul>
            </li>
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
