"use client";

import dynamic from "next/dynamic";

// 使用 dynamic 导入，禁用 SSR，避免 hydration 错误
// 因为 OverviewClient 使用了 SWR hooks，其初始状态在服务端和客户端不一致
const OverviewClient = dynamic(
  () => import("./overview-client").then((mod) => ({ default: mod.OverviewClient })),
  { ssr: false }
);

/**
 * Overview 包装组件
 * 
 * 职责：
 * - 作为客户端组件边界
 * - 使用 dynamic 导入 OverviewClient，禁用 SSR
 * - 避免 hydration 错误
 */
export function OverviewWrapper() {
  return <OverviewClient />;
}
