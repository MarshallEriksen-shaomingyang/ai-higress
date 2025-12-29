/**
 * StatusBadge - 状态徽章组件
 * 用于显示工作流和步骤的状态
 */
'use client';

import { workflowStyles, type WorkflowStatus } from '@/lib/workflow/styles';
import type { PausedReason } from '@/lib/workflow/types';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: WorkflowStatus;
  reason?: PausedReason | null;
  className?: string;
}

const statusLabels: Record<WorkflowStatus, string> = {
  running: 'Running',
  paused: 'Paused',
  completed: 'Completed',
  failed: 'Failed',
  cancelled: 'Cancelled',
  pending: 'Pending',
};

const pausedReasonLabels: Record<PausedReason, string> = {
  awaiting_approval: 'Awaiting Approval',
  step_failed: 'Step Failed',
  engine_interrupted: 'Engine Interrupted',
};

export function StatusBadge({ status, reason, className }: StatusBadgeProps) {
  const styles = workflowStyles.status[status] || workflowStyles.status.pending;

  const displayText = status === 'paused' && reason
    ? pausedReasonLabels[reason]
    : statusLabels[status];

  return (
    <div
      className={cn(
        'flex items-center gap-2 px-3 py-1 rounded-full border text-sm font-medium uppercase tracking-wide',
        styles.badge,
        className
      )}
    >
      {/* 呼吸点 */}
      <span
        className={cn(
          'w-2 h-2 rounded-full',
          styles.bg,
          status === 'running' && 'animate-pulse'
        )}
      />
      <span>{displayText}</span>
    </div>
  );
}
