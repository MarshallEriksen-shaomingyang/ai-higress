/**
 * Workflow Layout Root Client
 * 工作流页面根布局客户端组件
 */
"use client";

import { TooltipProvider } from "@/components/ui/tooltip";

export function WorkflowLayoutRootClient({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <TooltipProvider delayDuration={0}>
      {children}
    </TooltipProvider>
  );
}
