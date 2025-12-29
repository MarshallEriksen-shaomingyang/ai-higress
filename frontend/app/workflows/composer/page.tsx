/**
 * Workflow Composer Page
 * 工作流编排器页面
 */

import { WorkflowComposer } from '@/components/workflow/workflow-composer';
import type { BridgeAgent } from '@/lib/workflow/types';

// 模拟数据 - 实际应该从 API 获取
const mockAgents: BridgeAgent[] = [
  {
    id: 'bridge-1',
    name: 'Code Assistant',
    description: '代码辅助工具集',
    tools: [
      {
        name: 'code_review',
        description: '代码审查',
        parameters: {
          type: 'object',
          properties: {
            file_path: {
              type: 'string',
              description: '文件路径',
              required: true,
            },
          },
          required: ['file_path'],
        },
        risk_level: 'safe',
      },
      {
        name: 'code_generate',
        description: '代码生成',
        parameters: {
          type: 'object',
          properties: {
            prompt: {
              type: 'string',
              description: '生成提示',
              required: true,
            },
          },
          required: ['prompt'],
        },
        risk_level: 'safe',
      },
    ],
  },
  {
    id: 'bridge-2',
    name: 'System Tools',
    description: '系统操作工具',
    tools: [
      {
        name: 'execute_command',
        description: '执行系统命令',
        parameters: {
          type: 'object',
          properties: {
            command: {
              type: 'string',
              description: '命令',
              required: true,
            },
          },
          required: ['command'],
        },
        risk_level: 'dangerous',
      },
      {
        name: 'read_file',
        description: '读取文件',
        parameters: {
          type: 'object',
          properties: {
            path: {
              type: 'string',
              description: '文件路径',
              required: true,
            },
          },
          required: ['path'],
        },
        risk_level: 'safe',
      },
    ],
  },
];

export default function WorkflowComposerPage() {
  return <WorkflowComposer agents={mockAgents} />;
}
