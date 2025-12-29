/**
 * Workflows Layout
 * 工作流自动化独立布局（类似 Chat）
 */
import React from "react";

import { WorkflowNavRail } from "./components/workflow-nav-rail";
import { WorkflowLayoutRootClient } from "./components/workflow-layout-root-client";
import { WorkflowMobileHeader } from "./components/workflow-mobile-header";

export default function WorkflowsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-gradient-to-br from-[var(--background)] via-[var(--background)] to-[var(--muted)]">
      {/* 桌面端导航栏 - 在移动端隐藏 */}
      <div className="hidden md:block h-full">
        <WorkflowNavRail />
      </div>
      <div className="flex-1 h-full overflow-hidden flex flex-col">
        {/* 移动端顶部导航 */}
        <WorkflowMobileHeader />

        <div className="flex-1 overflow-hidden">
          <WorkflowLayoutRootClient>{children}</WorkflowLayoutRootClient>
        </div>
      </div>
    </div>
  );
}
