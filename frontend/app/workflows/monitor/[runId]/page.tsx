/**
 * Workflow Run Monitor Page
 * 工作流运行监控页面
 */

import { WorkflowRunMonitor } from '@/components/workflow/workflow-run-monitor';

interface WorkflowRunMonitorPageProps {
  params: {
    runId: string;
  };
}

export default function WorkflowRunMonitorPage({
  params,
}: WorkflowRunMonitorPageProps) {
  const runId = parseInt(params.runId, 10);

  if (isNaN(runId)) {
    return (
      <div className="flex items-center justify-center h-screen">
        <p className="text-slate-400">无效的运行实例 ID</p>
      </div>
    );
  }

  return <WorkflowRunMonitor runId={runId} />;
}
