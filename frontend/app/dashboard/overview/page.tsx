import { PageHeader } from "./components/page-header";
import { OverviewClient } from "./components/overview-client";

/**
 * Dashboard Overview 页面（服务端组件）
 * 
 * 职责：
 * - 定义页面布局结构
 * - 将交互逻辑委托给客户端组件
 * 
 * 优化：
 * - 使用服务端组件架构
 * - 页面结构在服务端渲染
 * - 交互逻辑和数据获取封装在客户端组件中
 * 
 * 架构：
 * - PageHeader: 客户端组件，处理 i18n 标题
 * - OverviewClient: 客户端组件，处理所有数据获取和交互
 */
export default function OverviewPage() {
  return (
    <div className="space-y-6 max-w-7xl">
      {/* 页面头部 - 客户端组件（用于 i18n） */}
      <PageHeader />

      {/* 动态内容 - 客户端组件 */}
      <OverviewClient />
    </div>
  );
}
