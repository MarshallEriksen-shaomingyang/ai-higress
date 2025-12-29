/**
 * Workflow Run Monitor - 工作流运行监控台
 * 实时监控工作流执行状态
 */
'use client';

import { useEffect, useState, useCallback } from 'react';
import { workflowStyles } from '@/lib/workflow/styles';
import type { WorkflowRun } from '@/lib/workflow/types';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { StatusBadge } from '@/components/workflow/status-badge';
import { StepCardRun } from '@/components/workflow/step-card';
import { toast } from 'sonner';
import {
  getWorkflowRun,
  resumeWorkflowRun,
  cancelWorkflowRun,
  subscribeWorkflowRunEvents,
} from '@/lib/http/workflow';
import { PlayCircle, XCircle, RefreshCw } from 'lucide-react';

interface WorkflowRunMonitorProps {
  runId: number;
}

export function WorkflowRunMonitor({ runId }: WorkflowRunMonitorProps) {
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  // 加载运行实例
  const loadRun = useCallback(async () => {
    try {
      const data = await getWorkflowRun(runId);
      setRun(data);
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to load workflow run:', error);
      toast.error('加载失败');
      setIsLoading(false);
    }
  }, [runId]);

  // 订阅 SSE 事件
  useEffect(() => {
    loadRun();

    const unsubscribe = subscribeWorkflowRunEvents(
      runId,
      (event) => {
        console.log('SSE Event:', event);
        setIsConnected(true);

        // 更新本地状态
        if (event.type === 'run.event') {
          loadRun(); // 重新加载完整状态
        }
      },
      (error) => {
        console.error('SSE Error:', error);
        setIsConnected(false);
        toast.error('连接中断，正在重试...');
      }
    );

    setIsConnected(true);

    return () => {
      unsubscribe();
      setIsConnected(false);
    };
  }, [runId, loadRun]);

  // 恢复/审批
  const handleResume = async () => {
    setActionLoading(true);
    try {
      await resumeWorkflowRun(runId);
      toast.success('已恢复运行');
      await loadRun();
    } catch (error) {
      console.error('Failed to resume workflow run:', error);
      toast.error('操作失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 取消
  const handleCancel = async () => {
    setActionLoading(true);
    try {
      await cancelWorkflowRun(runId);
      toast.success('已取消');
      await loadRun();
    } catch (error) {
      console.error('Failed to cancel workflow run:', error);
      toast.error('操作失败');
    } finally {
      setActionLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <RefreshCw className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-slate-400">工作流运行实例不存在</p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden flex flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-8 px-4">{/* 顶部状态栏 (Sticky Glass Header) */}
        <div className="sticky top-0 z-10 mb-8 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-xl p-4 border border-white/20 dark:border-slate-700/20 shadow-sm">
          <div className="flex items-center justify-between">
            {/* 左侧：标题 + Run ID */}
            <div>
              <h1 className={cn(workflowStyles.ink.title, 'text-xl font-semibold')}>
                {run.spec_snapshot.name}
              </h1>
              <p className={cn(workflowStyles.ink.body, 'text-sm mt-1 font-mono')}>
                #{run.id}
              </p>
            </div>

            {/* 右侧：状态 + 操作 */}
            <div className="flex items-center gap-3">
              <StatusBadge status={run.status} reason={run.paused_reason} />

              {/* 操作按钮组 */}
              <div className="flex gap-2">
                {run.status === 'paused' && (
                  <Button
                    onClick={handleResume}
                    disabled={actionLoading}
                    className={workflowStyles.button.primary}
                    size="sm"
                  >
                    <PlayCircle className="h-4 w-4 mr-2" />
                    {run.paused_reason === 'awaiting_approval'
                      ? '审批并继续'
                      : '重试'}
                  </Button>
                )}

                {(run.status === 'running' || run.status === 'paused') && (
                  <Button
                    onClick={handleCancel}
                    disabled={actionLoading}
                    variant="outline"
                    size="sm"
                    className="text-slate-600 dark:text-slate-400"
                  >
                    <XCircle className="h-4 w-4 mr-2" />
                    取消
                  </Button>
                )}
              </div>
            </div>
          </div>

          {/* 连接状态指示 */}
          <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-100 dark:border-slate-700">
            <div
              className={cn(
                'w-2 h-2 rounded-full',
                isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'
              )}
            />
            <span className="text-xs text-slate-500 dark:text-slate-400">
              {isConnected ? '实时连接' : '连接断开'}
            </span>
          </div>
        </div>

        {/* 垂直步骤流 (The Execution Stream) */}
        <ScrollArea className="h-[calc(100vh-280px)]">
          <div className="space-y-4">
            {run.steps_state.map((stepState, index) => {
              const step = run.spec_snapshot.steps[stepState.step_index];
              if (!step) return null;
              const isCurrent = index === run.current_step_index;

              return (
                <StepCardRun
                  key={stepState.step_index}
                  step={step}
                  state={stepState}
                  index={stepState.step_index}
                  isCurrent={isCurrent}
                />
              );
            })}
          </div>

          {/* 等待审批提示 */}
          {run.status === 'paused' && run.paused_reason === 'awaiting_approval' && (
            <div className="mt-8 p-6 rounded-xl bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
              <p className={cn(workflowStyles.ink.title, 'font-medium')}>
                Waiting for your signal...
              </p>
              <p className={cn(workflowStyles.ink.body, 'text-sm mt-1')}>
                该步骤需要您的确认才能继续执行。
              </p>
              <Button
                onClick={handleResume}
                disabled={actionLoading}
                className={cn(workflowStyles.button.primary, 'mt-4')}
              >
                <PlayCircle className="h-4 w-4 mr-2" />
                批准并继续
              </Button>
            </div>
          )}

          {/* 失败提示 */}
          {run.status === 'paused' && run.paused_reason === 'step_failed' && (
            <div className="mt-8 p-6 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
              <p className={cn(workflowStyles.ink.title, 'font-medium text-red-600 dark:text-red-400')}>
                Execution hit a snag.
              </p>
              <p className={cn(workflowStyles.ink.body, 'text-sm mt-1')}>
                执行过程中遇到错误，请检查日志后重试。
              </p>
              <Button
                onClick={handleResume}
                disabled={actionLoading}
                variant="outline"
                className="mt-4"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                重试步骤
              </Button>
            </div>
          )}
        </ScrollArea>
      </div>
    </div>
  </div>
  );
}
