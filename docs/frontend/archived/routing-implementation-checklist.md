# 路由页面重构实施检查清单

## 📋 总览

本检查清单提供了路由页面重构的详细步骤，每个步骤都包含具体的任务和验收标准。

---

## 阶段 1: 基础设施准备 ✅

### 1.1 创建 SWR Hooks 封装

**文件**: `frontend/lib/swr/use-routing.ts`

**任务**:
- [ ] 创建 `useRoutingDecision` Hook
  - [ ] 使用 `useApiPost` 封装 `/routing/decide` 接口
  - [ ] 返回 `makeDecision`, `decision`, `error`, `loading`
  - [ ] 添加 TypeScript 类型定义
  
- [ ] 创建 `useSession` Hook
  - [ ] 使用 `useApiGet` 封装 `/routing/sessions/:id` 接口
  - [ ] 支持条件请求（conversationId 为 null 时不请求）
  - [ ] 返回 `session`, `error`, `loading`, `refresh`
  
- [ ] 创建 `useDeleteSession` Hook
  - [ ] 使用 `useApiDelete` 封装删除会话接口
  - [ ] 返回 `deleteSession`, `deleting`
  
- [ ] 导出所有 Hooks 到 `frontend/lib/swr/index.ts`

**验收标准**:
```typescript
// 可以这样使用
const { makeDecision, decision, loading } = useRoutingDecision();
const { session, loading } = useSession(conversationId);
const { deleteSession, deleting } = useDeleteSession();
```

**预计时间**: 30-45分钟

---

### 1.2 添加国际化翻译

**文件**: `frontend/lib/i18n-context.tsx`

**任务**:
- [ ] 在 `translations.en` 中添加英文翻译
  - [ ] 页面标题和描述
  - [ ] Tab 标签
  - [ ] 路由决策相关文本（表单标签、按钮、结果展示）
  - [ ] 会话管理相关文本
  - [ ] 错误提示信息
  
- [ ] 在 `translations.zh` 中添加中文翻译
  - [ ] 对应所有英文翻译的中文版本
  
- [ ] 确保翻译键命名一致性
  - [ ] 使用 `routing.` 前缀
  - [ ] 遵循 `{section}.{element}` 命名规范

**翻译键列表**:
```typescript
// 页面级别
"routing.title"
"routing.subtitle"
"routing.tab_decision"
"routing.tab_sessions"

// 路由决策
"routing.decision.title"
"routing.decision.description"
"routing.decision.logical_model"
"routing.decision.strategy"
"routing.decision.strategy_latency"
"routing.decision.strategy_cost"
"routing.decision.strategy_reliability"
"routing.decision.strategy_balanced"
"routing.decision.conversation_id"
"routing.decision.preferred_region"
"routing.decision.exclude_providers"
"routing.decision.btn_decide"
"routing.decision.deciding"
"routing.decision.result_title"
"routing.decision.selected_upstream"
"routing.decision.decision_time"
"routing.decision.reasoning"
"routing.decision.candidates_title"
"routing.decision.no_result"

// 会话管理
"routing.session.title"
"routing.session.description"
"routing.session.search_placeholder"
"routing.session.btn_search"
"routing.session.btn_delete"
"routing.session.deleting"
"routing.session.info_title"
"routing.session.conversation_id"
"routing.session.logical_model"
"routing.session.provider"
"routing.session.model"
"routing.session.created_at"
"routing.session.last_used_at"
"routing.session.not_found"

// 表格
"routing.table.provider"
"routing.table.model"
"routing.table.region"
"routing.table.score"
"routing.table.success_rate"
"routing.table.latency"
"routing.table.cost"

// 错误提示
"routing.error.decision_failed"
"routing.error.session_not_found"
"routing.error.delete_failed"
"routing.error.invalid_input"
```

**验收标准**:
- [ ] 所有文本都有中英文翻译
- [ ] 翻译准确、自然
- [ ] 命名规范一致

**预计时间**: 30-45分钟

---

## 阶段 2: 组件开发 🔨

### 2.1 创建路由决策组件

**文件**: `frontend/app/dashboard/routing/components/routing-decision.tsx`

**任务**:
- [ ] 创建组件基础结构
  - [ ] 使用 `"use client"` 标记
  - [ ] 导入必要的依赖
  
- [ ] 实现表单部分
  - [ ] 逻辑模型选择器（使用 Select 组件）
  - [ ] 路由策略选择器（4种策略）
  - [ ] 可选参数输入（会话ID、首选区域、排除提供商）
  - [ ] 提交按钮
  
- [ ] 集成 SWR Hooks
  - [ ] 使用 `useRoutingDecision` 处理决策请求
  - [ ] 使用 `useApiGet` 获取逻辑模型列表
  - [ ] 处理加载和错误状态
  
- [ ] 实现结果展示部分
  - [ ] 选中的上游信息卡片
  - [ ] 决策时间和推理过程
  - [ ] 候选列表表格（使用 RoutingTable 组件）
  
- [ ] 添加国际化支持
  - [ ] 使用 `useI18n()` Hook
  - [ ] 所有文本使用 `t()` 函数

**组件结构**:
```typescript
"use client";

import { useState } from 'react';
import { useI18n } from '@/lib/i18n-context';
import { useRoutingDecision } from '@/lib/swr';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { RoutingTable } from './routing-table';

export function RoutingDecision() {
  const { t } = useI18n();
  const { makeDecision, decision, loading, error } = useRoutingDecision();
  
  // 表单状态
  const [formData, setFormData] = useState({...});
  
  // 提交处理
  const handleSubmit = async (e) => {...};
  
  return (
    <div className="space-y-6">
      {/* 表单卡片 */}
      <Card>
        <CardHeader>
          <CardTitle>{t('routing.decision.title')}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            {/* 表单字段 */}
          </form>
        </CardContent>
      </Card>
      
      {/* 结果卡片 */}
      {decision && (
        <Card>
          <CardHeader>
            <CardTitle>{t('routing.decision.result_title')}</CardTitle>
          </CardHeader>
          <CardContent>
            {/* 结果展示 */}
            <RoutingTable candidates={decision.all_candidates} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

**验收标准**:
- [ ] 表单可以正常提交
- [ ] 加载状态正确显示
- [ ] 错误信息友好提示
- [ ] 决策结果完整展示
- [ ] 支持中英文切换

**预计时间**: 1.5-2小时

---

### 2.2 创建会话管理组件

**文件**: `frontend/app/dashboard/routing/components/session-management.tsx`

**任务**:
- [ ] 创建组件基础结构
  - [ ] 使用 `"use client"` 标记
  - [ ] 导入必要的依赖
  
- [ ] 实现搜索部分
  - [ ] 会话ID输入框
  - [ ] 搜索按钮
  - [ ] 清除按钮
  
- [ ] 集成 SWR Hooks
  - [ ] 使用 `useSession` 获取会话信息
  - [ ] 使用 `useDeleteSession` 处理删除操作
  - [ ] 处理加载和错误状态
  
- [ ] 实现会话信息展示
  - [ ] 会话详情卡片
  - [ ] 格式化时间戳
  - [ ] 删除按钮
  
- [ ] 添加国际化支持
  - [ ] 使用 `useI18n()` Hook
  - [ ] 所有文本使用 `t()` 函数

**组件结构**:
```typescript
"use client";

import { useState } from 'react';
import { useI18n } from '@/lib/i18n-context';
import { useSession, useDeleteSession } from '@/lib/swr';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export function SessionManagement() {
  const { t } = useI18n();
  const [conversationId, setConversationId] = useState('');
  const [searchId, setSearchId] = useState<string | null>(null);
  
  const { session, loading, error } = useSession(searchId);
  const { deleteSession, deleting } = useDeleteSession();
  
  const handleSearch = () => {
    setSearchId(conversationId);
  };
  
  const handleDelete = async () => {
    if (searchId) {
      await deleteSession(searchId);
      setSearchId(null);
      setConversationId('');
    }
  };
  
  return (
    <div className="space-y-6">
      {/* 搜索卡片 */}
      <Card>
        <CardHeader>
          <CardTitle>{t('routing.session.title')}</CardTitle>
        </CardHeader>
        <CardContent>
          {/* 搜索表单 */}
        </CardContent>
      </Card>
      
      {/* 会话信息卡片 */}
      {session && (
        <Card>
          <CardHeader>
            <CardTitle>{t('routing.session.info_title')}</CardTitle>
          </CardHeader>
          <CardContent>
            {/* 会话详情 */}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

**验收标准**:
- [ ] 可以搜索会话
- [ ] 会话信息正确展示
- [ ] 可以删除会话
- [ ] 加载和错误状态正确处理
- [ ] 支持中英文切换

**预计时间**: 1-1.5小时

---

### 2.3 重构路由表格组件

**文件**: `frontend/app/dashboard/routing/components/routing-table.tsx`

**任务**:
- [ ] 更新组件接口
  - [ ] 接收 `candidates: CandidateInfo[]` 参数
  - [ ] 添加 TypeScript 类型定义
  
- [ ] 实现表格内容
  - [ ] 提供商列
  - [ ] 模型列
  - [ ] 区域列
  - [ ] 评分列
  - [ ] 成功率列
  - [ ] 延迟列（P95/P99）
  - [ ] 成本列
  
- [ ] 添加排序功能
  - [ ] 按评分排序
  - [ ] 按延迟排序
  - [ ] 按成功率排序
  
- [ ] 添加高亮显示
  - [ ] 选中的上游高亮显示
  - [ ] 使用不同颜色区分评分等级
  
- [ ] 添加国际化支持
  - [ ] 表头文本使用翻译

**组件结构**:
```typescript
"use client";

import { useI18n } from '@/lib/i18n-context';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import type { CandidateInfo } from '@/http/routing';

interface RoutingTableProps {
  candidates: CandidateInfo[];
  selectedUpstream?: string; // provider_id
}

export function RoutingTable({ candidates, selectedUpstream }: RoutingTableProps) {
  const { t } = useI18n();
  
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>{t('routing.table.provider')}</TableHead>
          <TableHead>{t('routing.table.model')}</TableHead>
          <TableHead>{t('routing.table.region')}</TableHead>
          <TableHead>{t('routing.table.score')}</TableHead>
          <TableHead>{t('routing.table.success_rate')}</TableHead>
          <TableHead>{t('routing.table.latency')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {candidates.map((candidate) => (
          <TableRow 
            key={`${candidate.upstream.provider_id}-${candidate.upstream.model_id}`}
            className={selectedUpstream === candidate.upstream.provider_id ? 'bg-accent' : ''}
          >
            {/* 表格单元格 */}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
```

**验收标准**:
- [ ] 表格正确展示所有候选信息
- [ ] 选中的上游有视觉区分
- [ ] 数据格式化正确（百分比、毫秒等）
- [ ] 支持中英文表头

**预计时间**: 1-1.5小时

---

### 2.4 创建客户端容器组件

**文件**: `frontend/app/dashboard/routing/components/routing-client.tsx`

**任务**:
- [ ] 创建客户端容器组件
  - [ ] 使用 `"use client"` 标记
  - [ ] 导入所有子组件
  
- [ ] 实现 Tabs 布局
  - [ ] 路由决策 Tab
  - [ ] 会话管理 Tab
  - [ ] Tab 切换状态管理
  
- [ ] 添加国际化支持
  - [ ] Tab 标签使用翻译

**组件结构**:
```typescript
"use client";

import { useI18n } from '@/lib/i18n-context';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { RoutingDecision } from './routing-decision';
import { SessionManagement } from './session-management';

export function RoutingClient() {
  const { t } = useI18n();
  
  return (
    <Tabs defaultValue="decision" className="space-y-6">
      <TabsList>
        <TabsTrigger value="decision">
          {t('routing.tab_decision')}
        </TabsTrigger>
        <TabsTrigger value="sessions">
          {t('routing.tab_sessions')}
        </TabsTrigger>
      </TabsList>
      
      <TabsContent value="decision">
        <RoutingDecision />
      </TabsContent>
      
      <TabsContent value="sessions">
        <SessionManagement />
      </TabsContent>
    </Tabs>
  );
}
```

**验收标准**:
- [ ] Tabs 可以正常切换
- [ ] 每个 Tab 内容正确显示
- [ ] 支持中英文标签

**预计时间**: 30分钟

---

## 阶段 3: 页面集成 🔗

### 3.1 更新页面主组件

**文件**: `frontend/app/dashboard/routing/page.tsx`

**任务**:
- [ ] 移除客户端标记
  - [ ] 删除 `"use client"`
  - [ ] 改为服务器组件
  
- [ ] 简化页面结构
  - [ ] 只保留布局和标题
  - [ ] 导入 RoutingClient 组件
  
- [ ] 移除硬编码数据
  - [ ] 删除 `routingRules` 数组
  - [ ] 删除相关类型定义
  
- [ ] 移除旧组件导入
  - [ ] 删除 RoutingForm 导入
  - [ ] 删除 RoutingTable 导入

**新的页面结构**:
```typescript
import { RoutingClient } from './components/routing-client';

export default function RoutingPage() {
  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-3xl font-bold mb-2">
          Routing Management
        </h1>
        <p className="text-muted-foreground">
          Configure intelligent request routing strategies
        </p>
      </div>
      
      <RoutingClient />
    </div>
  );
}
```

**验收标准**:
- [ ] 页面是服务器组件
- [ ] 页面正确渲染
- [ ] 所有功能正常工作

**预计时间**: 15-30分钟

---

### 3.2 清理旧文件

**任务**:
- [ ] 删除或重命名旧组件
  - [ ] `routing-form.tsx` (已被 routing-decision 替代)
  - [ ] 或者保留但标记为废弃
  
- [ ] 更新导出
  - [ ] 确保新组件正确导出
  - [ ] 移除旧组件的导出

**预计时间**: 15分钟

---

## 阶段 4: 测试和优化 ✨

### 4.1 功能测试

**测试清单**:
- [ ] 路由决策功能
  - [ ] 可以选择逻辑模型
  - [ ] 可以选择路由策略
  - [ ] 可以输入可选参数
  - [ ] 提交后正确显示结果
  - [ ] 错误情况正确处理
  
- [ ] 会话管理功能
  - [ ] 可以搜索会话
  - [ ] 会话信息正确展示
  - [ ] 可以删除会话
  - [ ] 错误情况正确处理
  
- [ ] 国际化功能
  - [ ] 可以切换中英文
  - [ ] 所有文本正确翻译
  - [ ] 切换后状态保持

**预计时间**: 1小时

---

### 4.2 用户体验优化

**优化清单**:
- [ ] 加载状态
  - [ ] 添加骨架屏或加载动画
  - [ ] 按钮显示加载状态
  
- [ ] 错误处理
  - [ ] 友好的错误提示
  - [ ] 提供重试选项
  
- [ ] 表单验证
  - [ ] 必填字段验证
  - [ ] 格式验证
  - [ ] 实时反馈
  
- [ ] 响应式设计
  - [ ] 移动端适配
  - [ ] 平板端适配

**预计时间**: 1-1.5小时

---

### 4.3 性能优化

**优化清单**:
- [ ] 组件优化
  - [ ] 使用 React.memo 包装纯组件
  - [ ] 使用 useCallback 缓存回调
  - [ ] 使用 useMemo 缓存计算结果
  
- [ ] 代码分割
  - [ ] 考虑使用动态导入
  - [ ] 减少初始包大小
  
- [ ] SWR 配置
  - [ ] 合理设置缓存策略
  - [ ] 避免不必要的请求

**预计时间**: 30-45分钟

---

## 总结

### 预计总时间
- 阶段 1: 1-1.5小时
- 阶段 2: 4-5.5小时
- 阶段 3: 0.5-0.75小时
- 阶段 4: 2.5-3.25小时

**总计**: 8-11小时

### 关键里程碑
1. ✅ SWR Hooks 和国际化准备完成
2. ✅ 所有组件开发完成
3. ✅ 页面集成完成
4. ✅ 测试和优化完成

### 成功标准
- [ ] 所有API接口正确集成
- [ ] 所有功能正常工作
- [ ] 完整的中英文支持
- [ ] 良好的用户体验
- [ ] 代码质量高，可维护性强

---

## 附录

### 相关文档
- [重构计划](./routing-page-refactor-plan.md)
- [技术架构](./routing-architecture.md)
- [API文档](../backend/API_Documentation.md)
- [SWR使用指南](../../frontend/lib/swr/README.md)

### 参考示例
- Providers页面: `frontend/app/dashboard/providers/page.tsx`
- API Keys页面: `frontend/app/dashboard/api-keys/page.tsx`

### 常见问题

**Q: 为什么page.tsx要改为服务器组件？**
A: 服务器组件可以提供更好的SEO和初始加载性能，同时保持客户端交互的灵活性。

**Q: 如何处理API错误？**
A: 使用SWR的error状态，结合toast提示用户，并提供重试选项。

**Q: 如何测试国际化？**
A: 在浏览器中切换语言，检查所有文本是否正确翻译。

**Q: 性能优化的重点是什么？**
A: 避免不必要的重新渲染，合理使用SWR缓存，代码分割减少初始加载。