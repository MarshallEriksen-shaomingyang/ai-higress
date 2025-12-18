import { OverviewWrapper } from "./_components/overview-wrapper";
import type { Metadata } from "next";

/**
 * 页面元数据
 */
export const metadata: Metadata = {
  title: "Dashboard - 概览",
  description: "查看系统健康状况、Token 使用情况和成本花费",
};

/**
 * Dashboard 用户页 - 概览页面（服务端组件）
 * 
 * 职责：
 * - 提供页面布局和容器
 * - 渲染客户端容器组件（仅客户端渲染，避免 hydration 错误）
 * - 设置页面元数据
 * 
 * 验证需求：1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1
 */
export default function DashboardOverviewPage() {
  return (
    <div className="container mx-auto p-6">
      <OverviewWrapper />
    </div>
  );
}
