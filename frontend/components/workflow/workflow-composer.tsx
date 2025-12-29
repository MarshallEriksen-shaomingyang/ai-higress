/**
 * Workflow Composer - 工作流编排器页面
 * 左侧工具库 + 右侧编排画布
 */
'use client';

import { useState, useCallback } from 'react';
import { workflowStyles } from '@/lib/workflow/styles';
import type { WorkflowStep, WorkflowSpec, BridgeAgent, BridgeTool } from '@/lib/workflow/types';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, Save, Play, Plus } from 'lucide-react';
import { StepCardEdit } from '@/components/workflow/step-card';
import { toast } from 'sonner';
import { createWorkflow, createWorkflowRun } from '@/lib/http/workflow';
import { useRouter } from 'next/navigation';

interface WorkflowComposerProps {
  agents?: BridgeAgent[];
}

export function WorkflowComposer({ agents = [] }: WorkflowComposerProps) {
  const router = useRouter();
  const [workflow, setWorkflow] = useState<Partial<WorkflowSpec>>({
    name: '',
    description: '',
    steps: [],
  });
  const [searchTerm, setSearchTerm] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // 搜索过滤
  const filteredAgents = agents.filter((agent) =>
    agent.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    agent.tools.some((tool) =>
      tool.name.toLowerCase().includes(searchTerm.toLowerCase())
    )
  );

  // 添加步骤到画布
  const handleAddStep = useCallback((agentId: string, tool: BridgeTool) => {
    const newStep: WorkflowStep = {
      agent_id: agentId,
      tool_name: tool.name,
      tool_arguments: {}, // 默认空参数，用户可编辑
      require_approval: tool.risk_level === 'dangerous', // 危险操作默认需要审批
      on_error: 'pause',
    };

    setWorkflow((prev) => ({
      ...prev,
      steps: [...(prev.steps || []), newStep],
    }));

    toast.success(`已添加工具: ${tool.name}`);
  }, []);

  // 删除步骤
  const handleDeleteStep = useCallback((index: number) => {
    setWorkflow((prev) => ({
      ...prev,
      steps: (prev.steps || []).filter((_, i) => i !== index),
    }));
  }, []);

  // 更新步骤
  const handleUpdateStep = useCallback((index: number, step: WorkflowStep) => {
    setWorkflow((prev) => ({
      ...prev,
      steps: (prev.steps || []).map((s, i) => (i === index ? step : s)),
    }));
  }, []);

  // 保存工作流
  const handleSave = async () => {
    if (!workflow.name || workflow.name.trim() === '') {
      toast.error('请输入工作流名称');
      return;
    }

    if (!workflow.steps || workflow.steps.length === 0) {
      toast.error('请至少添加一个步骤');
      return;
    }

    setIsSaving(true);
    try {
      const savedWorkflow = await createWorkflow(workflow as WorkflowSpec);
      toast.success('工作流已保存');
      console.log('Saved workflow:', savedWorkflow);
    } catch (error) {
      console.error('Failed to save workflow:', error);
      toast.error('保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  // 保存并运行
  const handleSaveAndRun = async () => {
    if (!workflow.name || workflow.name.trim() === '') {
      toast.error('请输入工作流名称');
      return;
    }

    if (!workflow.steps || workflow.steps.length === 0) {
      toast.error('请至少添加一个步骤');
      return;
    }

    setIsSaving(true);
    try {
      const savedWorkflow = await createWorkflow(workflow as WorkflowSpec);
      const run = await createWorkflowRun(savedWorkflow.id);
      toast.success('工作流已启动');
      router.push(`/workflows/monitor/${run.id}`);
    } catch (error) {
      console.error('Failed to create workflow run:', error);
      toast.error('启动失败');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="grid grid-cols-12 h-full gap-6 p-6">{/* 左侧：工具库 (3列) */}
      <div className="col-span-3">
        <div
          className={cn(
            workflowStyles.card.base,
            workflowStyles.card.baseDark,
            'h-full flex flex-col p-4'
          )}
        >
          {/* 搜索栏 */}
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <Input
              placeholder="搜索工具..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className={cn(workflowStyles.input.search, 'pl-9')}
            />
          </div>

          {/* 工具列表 */}
          <ScrollArea className="flex-1">
            <div className="space-y-4">
              {filteredAgents.length === 0 ? (
                <p className="text-sm text-slate-400 text-center py-8">
                  暂无可用工具
                </p>
              ) : (
                filteredAgents.map((agent) => (
                  <div key={agent.id}>
                    {/* Agent 分组标题 */}
                    <h3 className="text-xs font-serif text-slate-600 dark:text-slate-400 uppercase tracking-wider mb-2">
                      {agent.name}
                    </h3>

                    {/* Tool 列表 */}
                    <div className="space-y-2">
                      {agent.tools.map((tool) => (
                        <button
                          key={tool.name}
                          onClick={() => handleAddStep(agent.id, tool)}
                          className={cn(
                            'w-full text-left p-3 rounded-lg bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700',
                            'hover:-translate-y-1 hover:shadow-md transition-all duration-200',
                            'flex items-start gap-2'
                          )}
                        >
                          <Plus className="h-4 w-4 text-slate-400 mt-0.5 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-slate-800 dark:text-slate-100 truncate">
                              {tool.name}
                            </p>
                            <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 mt-0.5">
                              {tool.description}
                            </p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </div>
      </div>

      {/* 右侧：编排画布 (9列) */}
      <div className="col-span-9 flex flex-col">
        {/* 头部：Meta Info */}
        <div className="mb-6">
          <Input
            placeholder="在此输入工作流标题..."
            value={workflow.name || ''}
            onChange={(e) =>
              setWorkflow((prev) => ({ ...prev, name: e.target.value }))
            }
            className={workflowStyles.input.title}
          />

          <div className="flex items-center gap-3 mt-4">
            <Button
              onClick={handleSave}
              disabled={isSaving}
              variant="outline"
              className={workflowStyles.button.secondary}
            >
              <Save className="h-4 w-4 mr-2" />
              保存
            </Button>
            <Button
              onClick={handleSaveAndRun}
              disabled={isSaving}
              className={workflowStyles.button.primary}
            >
              <Play className="h-4 w-4 mr-2" />
              保存并运行
            </Button>
          </div>
        </div>

        {/* 步骤列表 (Timeline) */}
        <ScrollArea className="flex-1">
          {!workflow.steps || workflow.steps.length === 0 ? (
            <div className="h-full flex items-center justify-center">
              <p className={cn(workflowStyles.ink.body, 'text-center')}>
                从左侧点击工具，开始编排你的自动化流程。
              </p>
            </div>
          ) : (
            <div className="space-y-4 relative">
              {/* 虚线连接线 */}
              <div className="absolute left-8 top-0 bottom-0 w-px border-l border-dashed border-slate-300 dark:border-slate-700" />

              {workflow.steps.map((step, index) => (
                <div key={index} className="relative pl-16">
                  <StepCardEdit
                    step={step}
                    index={index}
                    onDelete={() => handleDeleteStep(index)}
                    onUpdate={(updatedStep) => handleUpdateStep(index, updatedStep)}
                  />
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
