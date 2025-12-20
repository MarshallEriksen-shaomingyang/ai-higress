"use client";

import dynamic from "next/dynamic";

/**
 * Overview 包装组件
 * 
 * 职责：
 * - 作为客户端组件边界
 * - 使用 dynamic 导入禁用 SSR，避免 hydration 错误
 * 
 * 注意：虽然服务端已通过 SWR fallback 预取数据，
 * 但由于 OverviewClient 中的 loading 状态在服务端和客户端不一致，
 * 仍需禁用 SSR 以避免 hydration 错误。
 * 
 * 预取的数据仍然有效：客户端首次渲染时会使用 fallback 数据，
 * 避免额外的网络请求和加载闪烁。
 */
const OverviewClient = dynamic(
  () => import("./overview-client").then((mod) => ({ default: mod.OverviewClient })),
  { ssr: false }
);

export function OverviewWrapper() {
  return <OverviewClient />;
}
