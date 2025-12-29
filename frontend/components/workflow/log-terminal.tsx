/**
 * LogTerminal - 日志终端组件
 * 用于实时显示步骤执行日志
 */
'use client';

import { useEffect, useRef } from 'react';
import { workflowStyles } from '@/lib/workflow/styles';
import { cn } from '@/lib/utils';

interface LogTerminalProps {
  logs: string[];
  autoScroll?: boolean;
  className?: string;
}

export function LogTerminal({ logs, autoScroll = true, className }: LogTerminalProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  return (
    <div
      ref={containerRef}
      className={cn(workflowStyles.terminal.container, className)}
    >
      {logs.length === 0 ? (
        <span className="text-slate-400 dark:text-slate-500 italic">
          Waiting for logs...
        </span>
      ) : (
        <div className="space-y-0">
          {logs.map((line, i) => (
            <div
              key={i}
              className={cn(
                workflowStyles.terminal.text,
                workflowStyles.terminal.line
              )}
            >
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
