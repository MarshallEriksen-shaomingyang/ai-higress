/**
 * Provider 状态卡片组件使用示例
 * 
 * 此文件展示如何使用 ProviderStatusCard 组件
 */

import { ProviderStatusCard } from "./provider-status-card";

export function ProviderStatusCardExample() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
      {/* 示例 1: 健康的 Provider */}
      <ProviderStatusCard
        providerId="openai-gpt4"
        operationStatus="active"
        healthStatus="healthy"
        auditStatus="approved"
        lastCheck={new Date(Date.now() - 5 * 60 * 1000).toISOString()}
      />

      {/* 示例 2: 降级的 Provider */}
      <ProviderStatusCard
        providerId="anthropic-claude"
        operationStatus="active"
        healthStatus="degraded"
        auditStatus="approved"
        lastCheck={new Date(Date.now() - 30 * 60 * 1000).toISOString()}
      />

      {/* 示例 3: 维护中的 Provider */}
      <ProviderStatusCard
        providerId="google-gemini"
        operationStatus="maintenance"
        healthStatus="healthy"
        auditStatus="approved"
        lastCheck={new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()}
      />

      {/* 示例 4: 不健康的 Provider */}
      <ProviderStatusCard
        providerId="azure-openai"
        operationStatus="active"
        healthStatus="unhealthy"
        auditStatus="approved"
        lastCheck={new Date(Date.now() - 10 * 60 * 1000).toISOString()}
      />

      {/* 示例 5: 待审核的 Provider */}
      <ProviderStatusCard
        providerId="custom-provider"
        operationStatus="inactive"
        healthStatus="healthy"
        auditStatus="pending"
        lastCheck={new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()}
      />

      {/* 示例 6: 已拒绝的 Provider */}
      <ProviderStatusCard
        providerId="rejected-provider"
        operationStatus="inactive"
        healthStatus="unhealthy"
        auditStatus="rejected"
        lastCheck={new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()}
      />
    </div>
  );
}
