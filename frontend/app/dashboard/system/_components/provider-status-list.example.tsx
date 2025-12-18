/**
 * ProviderStatusList 组件使用示例
 * 
 * 此文件展示如何在系统页中使用 ProviderStatusList 组件
 */

"use client";

import { ProviderStatusList } from "./provider-status-list";
import { useSystemDashboardProviders } from "@/lib/swr/use-dashboard-v2";

/**
 * 示例 1: 基本使用
 * 
 * 从 SWR Hook 获取数据并传递给 ProviderStatusList
 */
export function BasicExample() {
  const { items, loading, error, refresh } = useSystemDashboardProviders();

  return (
    <ProviderStatusList
      data={items}
      isLoading={loading}
      error={error}
      onRetry={refresh}
    />
  );
}

/**
 * 示例 2: 在系统页容器中使用
 * 
 * 作为系统页的一部分，与其他组件一起使用
 */
export function SystemDashboardExample() {
  const { items, loading, error, refresh } = useSystemDashboardProviders();

  return (
    <div className="space-y-6">
      {/* 其他组件... */}
      
      {/* Provider 状态列表 */}
      <ProviderStatusList
        data={items}
        isLoading={loading}
        error={error}
        onRetry={refresh}
      />
    </div>
  );
}

/**
 * 示例 3: 模拟数据测试
 * 
 * 用于开发和测试时的数据模拟
 */
export function MockDataExample() {
  const mockData = [
    {
      provider_id: "openai-provider-1",
      operation_status: "active" as const,
      status: "healthy" as const,
      audit_status: "approved" as const,
      last_check: new Date().toISOString(),
    },
    {
      provider_id: "anthropic-provider-1",
      operation_status: "active" as const,
      status: "degraded" as const,
      audit_status: "approved" as const,
      last_check: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
    },
    {
      provider_id: "azure-provider-1",
      operation_status: "maintenance" as const,
      status: "healthy" as const,
      audit_status: "approved" as const,
      last_check: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
    },
    {
      provider_id: "test-provider-1",
      operation_status: "inactive" as const,
      status: "unhealthy" as const,
      audit_status: "pending" as const,
      last_check: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
    },
  ];

  return (
    <ProviderStatusList
      data={mockData}
      isLoading={false}
      error={undefined}
      onRetry={() => console.log("Retry clicked")}
    />
  );
}

/**
 * 示例 4: 加载状态
 */
export function LoadingExample() {
  return (
    <ProviderStatusList
      data={[]}
      isLoading={true}
      error={undefined}
    />
  );
}

/**
 * 示例 5: 错误状态
 */
export function ErrorExample() {
  return (
    <ProviderStatusList
      data={[]}
      isLoading={false}
      error={new Error("Failed to fetch provider status")}
      onRetry={() => console.log("Retry clicked")}
    />
  );
}

/**
 * 示例 6: 空数据状态
 */
export function EmptyExample() {
  return (
    <ProviderStatusList
      data={[]}
      isLoading={false}
      error={undefined}
    />
  );
}
