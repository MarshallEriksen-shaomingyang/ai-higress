/**
 * StepCard - 步骤卡片组件
 * 根据状态自动调整显示形态（编辑态/运行态）
 */
'use client';

import { useState } from 'react';
import { workflowStyles } from '@/lib/workflow/styles';
import type { WorkflowStep, StepState } from '@/lib/workflow/types';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Trash2, ChevronDown, ChevronUp, CheckCircle2, XCircle, Clock } from 'lucide-react';
import { LogTerminal } from './log-terminal';

interface StepCardEditProps {
  step: WorkflowStep;
  index: number;
  onDelete: () => void;
  onUpdate: (step: WorkflowStep) => void;
}

interface StepCardRunProps {
  step: WorkflowStep;
  state: StepState;
  index: number;
  isCurrent: boolean;
}

// 编辑态卡片
export function StepCardEdit({ step, index, onDelete, onUpdate }: StepCardEditProps) {
  return (
    <div
      className={cn(
        workflowStyles.card.base,
        workflowStyles.card.baseDark,
        'p-4 transition-all duration-300'
      )}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl font-mono text-slate-400 dark:text-slate-600">
            {String(index + 1).padStart(2, '0')}
          </span>
          <div>
            <h3 className={cn(workflowStyles.ink.title, 'font-semibold')}>
              {step.tool_name}
            </h3>
            <p className={cn(workflowStyles.ink.body, 'text-xs mt-0.5')}>
              Agent: {step.agent_id}
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onDelete}
          className="text-slate-400 hover:text-red-500"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Body - 参数预览 */}
      <div className="mb-3">
        <pre className="text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-900/50 p-2 rounded overflow-x-auto">
          {JSON.stringify(step.tool_arguments, null, 2)}
        </pre>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-slate-100 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <Switch
            id={`approval-${index}`}
            checked={step.require_approval || false}
            onCheckedChange={(checked) =>
              onUpdate({ ...step, require_approval: checked })
            }
          />
          <Label htmlFor={`approval-${index}`} className="text-xs text-slate-600 dark:text-slate-400">
            运行前需人工确认
          </Label>
        </div>

        {/* 可选：显示风险等级 */}
        {/* <Badge variant="outline" className={riskColors.safe}>Safe</Badge> */}
      </div>
    </div>
  );
}

// 运行态卡片
export function StepCardRun({ step, state, index, isCurrent }: StepCardRunProps) {
  const [expanded, setExpanded] = useState(isCurrent);

  const statusIcons = {
    pending: <Clock className="h-4 w-4 text-slate-400" />,
    running: <div className="h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />,
    completed: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
    failed: <XCircle className="h-4 w-4 text-red-500" />,
    paused: <Clock className="h-4 w-4 text-orange-500" />,
  };

  const logs = state.log_preview ? state.log_preview.split('\n') : [];

  return (
    <div
      className={cn(
        'transition-all duration-500 ease-in-out',
        isCurrent ? 'scale-100 opacity-100' : 'scale-95 opacity-60',
        state.status === 'running' && workflowStyles.status.running.ring,
        state.status === 'paused' && workflowStyles.status.paused.ring
      )}
    >
      <div
        className={cn(
          workflowStyles.card.base,
          workflowStyles.card.baseDark,
          'p-4 cursor-pointer',
          !expanded && 'hover:shadow-md'
        )}
        onClick={() => setExpanded(!expanded)}
      >
        {/* Compact Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1">
            <span className="text-lg font-mono text-slate-400 dark:text-slate-600">
              {String(index + 1).padStart(2, '0')}
            </span>
            {statusIcons[state.status]}
            <div className="flex-1">
              <h3 className={cn(workflowStyles.ink.title, 'font-semibold text-sm')}>
                {step.tool_name}
              </h3>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {state.status === 'completed' && (
              <span className="text-xs text-slate-400">
                {state.completed_at ? `${Math.round((new Date(state.completed_at).getTime() - new Date(state.started_at!).getTime()) / 1000)}s` : ''}
              </span>
            )}
            <Badge variant="outline" className="text-xs">
              {state.status}
            </Badge>
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </div>
        </div>

        {/* Expanded Content */}
        {expanded && (
          <div className="mt-4 space-y-3" onClick={(e) => e.stopPropagation()}>
            {/* 错误信息 */}
            {state.error_message && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-3">
                <p className="text-sm text-red-600 dark:text-red-400 font-medium">Error:</p>
                <p className="text-xs text-red-500 dark:text-red-400 mt-1">{state.error_message}</p>
              </div>
            )}

            {/* 日志终端 */}
            {state.status === 'running' && logs.length > 0 && (
              <LogTerminal logs={logs} />
            )}

            {/* 历史日志（已完成） */}
            {state.status === 'completed' && logs.length > 0 && (
              <LogTerminal logs={logs} autoScroll={false} />
            )}

            {/* 重试次数 */}
            {state.attempts > 1 && (
              <p className="text-xs text-slate-500">
                Attempts: {state.attempts}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
