/**
 * Workflows Index Page
 * 工作流列表页面 - 独立全屏布局
 */

'use client';

import Link from 'next/link';
import { workflowStyles } from '@/lib/workflow/styles';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, FileText } from 'lucide-react';

export default function WorkflowsIndexPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-6xl mx-auto p-8">
        {/* 页面标题 */}
        <div className="mb-8">
          <h1 className={cn(workflowStyles.ink.title, 'text-3xl font-serif font-bold')}>
            工作流自动化
          </h1>
          <p className={cn(workflowStyles.ink.body, 'mt-2')}>
            使用 Bridge Agent 编排自动化工作流程
          </p>
        </div>

        {/* 快速开始卡片 */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* 创建新工作流 */}
          <Card
            className={cn(
              workflowStyles.card.base,
              workflowStyles.card.baseDark,
              workflowStyles.card.hover
            )}
          >
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20">
                  <Plus className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <CardTitle className={workflowStyles.ink.title}>创建工作流</CardTitle>
                  <CardDescription className={workflowStyles.ink.body}>
                    从零开始编排新的自动化流程
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Link href="/workflows/composer">
                <Button className={cn(workflowStyles.button.primary, 'w-full')}>
                  <Plus className="h-4 w-4 mr-2" />
                  开始编排
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* 查看文档 */}
          <Card
            className={cn(
              workflowStyles.card.base,
              workflowStyles.card.baseDark,
              workflowStyles.card.hover
            )}
          >
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-900/20">
                  <FileText className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                </div>
                <div>
                  <CardTitle className={workflowStyles.ink.title}>使用文档</CardTitle>
                  <CardDescription className={workflowStyles.ink.body}>
                    了解工作流自动化功能
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => window.open('/docs/backend/workflow-automation-production-plan.md', '_blank')}
              >
                <FileText className="h-4 w-4 mr-2" />
                查看文档
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* 功能介绍 */}
        <div className="mt-12">
          <h2 className={cn(workflowStyles.ink.title, 'text-xl font-semibold mb-6')}>
            功能特性
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div
              className={cn(
                workflowStyles.card.base,
                workflowStyles.card.baseDark,
                'p-4'
              )}
            >
              <div className="text-2xl mb-3">🎨</div>
              <h3 className={cn(workflowStyles.ink.title, 'font-semibold mb-2')}>
                可视化编排
              </h3>
              <p className={cn(workflowStyles.ink.body, 'text-sm')}>
                拖拽式工具库，轻松组装复杂流程
              </p>
            </div>

            <div
              className={cn(
                workflowStyles.card.base,
                workflowStyles.card.baseDark,
                'p-4'
              )}
            >
              <div className="text-2xl mb-3">🔄</div>
              <h3 className={cn(workflowStyles.ink.title, 'font-semibold mb-2')}>
                实时监控
              </h3>
              <p className={cn(workflowStyles.ink.body, 'text-sm')}>
                SSE 推送日志，透明可控的执行过程
              </p>
            </div>

            <div
              className={cn(
                workflowStyles.card.base,
                workflowStyles.card.baseDark,
                'p-4'
              )}
            >
              <div className="text-2xl mb-3">✅</div>
              <h3 className={cn(workflowStyles.ink.title, 'font-semibold mb-2')}>
                人工审批
              </h3>
              <p className={cn(workflowStyles.ink.body, 'text-sm')}>
                敏感操作需确认，安全可靠
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
