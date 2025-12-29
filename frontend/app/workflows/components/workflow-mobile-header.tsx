/**
 * Workflow Mobile Header
 * 工作流移动端顶部导航
 */
"use client";

import Link from "next/link";
import { ArrowLeft, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WorkflowNavRail } from "./workflow-nav-rail";
import { usePathname } from "next/navigation";

export function WorkflowMobileHeader() {
  const pathname = usePathname();

  // 判断是否显示返回按钮
  const showBackButton = pathname !== "/workflows";

  return (
    <header className="md:hidden sticky top-0 z-50 w-full border-b bg-card/80 backdrop-blur-sm">
      <div className="flex h-14 items-center justify-between px-4">
        <div className="flex items-center gap-2">
          {showBackButton ? (
            <Button variant="ghost" size="icon" asChild>
              <Link href="/workflows">
                <ArrowLeft className="h-5 w-5" />
              </Link>
            </Button>
          ) : (
            <Button variant="ghost" size="icon" asChild>
              <Link href="/dashboard">
                <Menu className="h-5 w-5" />
              </Link>
            </Button>
          )}
          <h1 className="text-lg font-semibold">工作流自动化</h1>
        </div>

        <WorkflowNavRail variant="mobile" />
      </div>
    </header>
  );
}
