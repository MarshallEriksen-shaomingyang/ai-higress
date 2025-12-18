"use client";

import { TokenUsageChart } from "./token-usage-chart";
import type { DashboardV2TokenDataPoint } from "@/lib/api-types";

/**
 * 生成模拟的 Token 数据（小时粒度）
 */
function generateMockTokenDataHourly(): DashboardV2TokenDataPoint[] {
  const data: DashboardV2TokenDataPoint[] = [];
  const now = new Date();
  
  // 生成过去 24 小时的数据，每小时一个数据点
  for (let i = 24; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 60 * 60 * 1000);
    
    // 模拟数据：白天 Token 使用多，夜间少
    const hour = time.getHours();
    const isBusinessHours = hour >= 9 && hour <= 18;
    const baseTokens = isBusinessHours ? 50000 : 15000;
    
    // 添加随机波动
    const randomFactor = 0.7 + Math.random() * 0.6;
    const inputTokens = Math.floor(baseTokens * randomFactor);
    const outputTokens = Math.floor(inputTokens * (0.3 + Math.random() * 0.4)); // 输出约为输入的 30-70%
    
    // 估算请求数（约 5-10% 的请求是估算的）
    const estimatedRequests = Math.random() > 0.9 ? Math.floor(Math.random() * 10) : 0;
    
    data.push({
      window_start: time.toISOString(),
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      total_tokens: inputTokens + outputTokens,
      estimated_requests: estimatedRequests,
    });
  }
  
  return data;
}

/**
 * 生成模拟的 Token 数据（天粒度）
 */
function generateMockTokenDataDaily(): DashboardV2TokenDataPoint[] {
  const data: DashboardV2TokenDataPoint[] = [];
  const now = new Date();
  
  // 生成过去 30 天的数据
  for (let i = 30; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 24 * 60 * 60 * 1000);
    
    // 模拟数据：工作日 Token 使用多，周末少
    const dayOfWeek = time.getDay();
    const isWeekday = dayOfWeek >= 1 && dayOfWeek <= 5;
    const baseTokens = isWeekday ? 800000 : 300000;
    
    // 添加随机波动
    const randomFactor = 0.8 + Math.random() * 0.4;
    const inputTokens = Math.floor(baseTokens * randomFactor);
    const outputTokens = Math.floor(inputTokens * (0.35 + Math.random() * 0.3));
    
    // 估算请求数
    const estimatedRequests = Math.random() > 0.8 ? Math.floor(Math.random() * 50) : 0;
    
    data.push({
      window_start: time.toISOString(),
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      total_tokens: inputTokens + outputTokens,
      estimated_requests: estimatedRequests,
    });
  }
  
  return data;
}

/**
 * 生成有估算请求的数据
 */
function generateDataWithEstimation(): DashboardV2TokenDataPoint[] {
  const data = generateMockTokenDataHourly();
  
  // 确保有一些估算请求
  return data.map((point, index) => ({
    ...point,
    estimated_requests: index % 3 === 0 ? Math.floor(Math.random() * 20) + 5 : 0,
  }));
}

export function TokenUsageChartDemo() {
  const hourlyData = generateMockTokenDataHourly();
  const dailyData = generateMockTokenDataDaily();
  const dataWithEstimation = generateDataWithEstimation();
  
  // 计算总估算请求数
  const totalEstimatedRequests = dataWithEstimation.reduce(
    (sum, point) => sum + point.estimated_requests,
    0
  );

  return (
    <div className="space-y-8 p-8">
      <div>
        <h2 className="text-2xl font-bold mb-4">Token 使用趋势图表 Demo</h2>
        <p className="text-muted-foreground mb-6">
          展示 Token 输入和输出的使用趋势，使用堆叠柱状图。支持小时和天两种粒度。
        </p>
      </div>

      {/* 小时粒度 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">1. 小时粒度（过去 24 小时）</h3>
        <TokenUsageChart
          data={hourlyData}
          bucket="hour"
          isLoading={false}
          estimatedRequests={0}
        />
      </div>

      {/* 天粒度 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">2. 天粒度（过去 30 天）</h3>
        <TokenUsageChart
          data={dailyData}
          bucket="day"
          isLoading={false}
          estimatedRequests={0}
        />
      </div>

      {/* 带估算请求提示 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">3. 带估算请求提示</h3>
        <p className="text-sm text-muted-foreground mb-2">
          当有估算请求时，右上角会显示 ⓘ 图标，鼠标悬停可查看详情。
        </p>
        <TokenUsageChart
          data={dataWithEstimation}
          bucket="hour"
          isLoading={false}
          estimatedRequests={totalEstimatedRequests}
        />
      </div>

      {/* 加载状态 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">4. 加载状态</h3>
        <TokenUsageChart
          data={[]}
          bucket="hour"
          isLoading={true}
          estimatedRequests={0}
        />
      </div>

      {/* 错误状态 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">5. 错误状态</h3>
        <TokenUsageChart
          data={[]}
          bucket="hour"
          isLoading={false}
          error={new Error("Failed to fetch token data")}
          estimatedRequests={0}
        />
      </div>

      {/* 空数据 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">6. 空数据</h3>
        <TokenUsageChart
          data={[]}
          bucket="hour"
          isLoading={false}
          estimatedRequests={0}
        />
      </div>

      {/* 高输出比例场景 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">7. 高输出比例场景</h3>
        <p className="text-sm text-muted-foreground mb-2">
          模拟输出 Token 远多于输入 Token 的情况（如代码生成场景）。
        </p>
        <TokenUsageChart
          data={hourlyData.map((point) => ({
            ...point,
            output_tokens: point.input_tokens * 2, // 输出是输入的 2 倍
            total_tokens: point.input_tokens + point.input_tokens * 2,
          }))}
          bucket="hour"
          isLoading={false}
          estimatedRequests={0}
        />
      </div>

      {/* 低使用量场景 */}
      <div>
        <h3 className="text-lg font-semibold mb-2">8. 低使用量场景</h3>
        <p className="text-sm text-muted-foreground mb-2">
          模拟系统使用量较低的情况。
        </p>
        <TokenUsageChart
          data={hourlyData.map((point) => ({
            ...point,
            input_tokens: Math.floor(point.input_tokens * 0.1),
            output_tokens: Math.floor(point.output_tokens * 0.1),
            total_tokens: Math.floor(point.total_tokens * 0.1),
          }))}
          bucket="hour"
          isLoading={false}
          estimatedRequests={0}
        />
      </div>
    </div>
  );
}
