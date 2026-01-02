# 路由页面重构计划

## 概述

本文档描述了路由页面的重构计划，主要目标是：
1. 接入真实的路由API接口
2. 使用封装好的SWR进行数据请求
3. 进行组件拆分和优化
4. 保持page为服务器组件
5. 添加完整的中英文国际化支持

## 当前状态分析

### 现有实现
- **页面**: `frontend/app/dashboard/routing/page.tsx` - 客户端组件，使用硬编码数据
- **组件**:
  - `RoutingForm` - 简单的表单对话框，无实际功能
  - `RoutingTable` - 展示硬编码的路由规则列表
- **API**: `frontend/http/routing.ts` - 已定义路由服务接口
- **国际化**: 缺少路由页面相关的翻译

### API接口（来自文档）

根据 `docs/backend/API_Documentation.md`，路由相关的API包括：

1. **路由决策** - `POST /routing/decide`
   - 计算逻辑模型请求的路由决策
   - 支持多种策略：latency_first, cost_first, reliability_first, balanced
   - 返回选中的上游、决策时间、推理过程、候选列表等

2. **会话管理**:
   - `GET /routing/sessions/{conversation_id}` - 获取会话信息
   - `DELETE /routing/sessions/{conversation_id}` - 删除会话

## 重构方案

### 1. 架构设计

```
frontend/app/dashboard/routing/
├── page.tsx (服务器组件 - 布局和数据预取)
└── components/
    ├── routing-client.tsx (客户端容器组件)
    ├── routing-decision.tsx (路由决策组件)
    ├── session-management.tsx (会话管理组件)
    ├── routing-form.tsx (重构后的表单)
    └── routing-table.tsx (重构后的表格)
```

### 2. SWR Hooks封装

创建 `frontend/lib/swr/use-routing.ts`，封装路由相关的数据请求：

```typescript
// 路由决策Hook
export const useRoutingDecision = () => {
  const { trigger, data, error, submitting } = useApiPost<
    RoutingDecisionResponse,
    RoutingDecisionRequest
  >('/routing/decide');
  
  return {
    makeDecision: trigger,
    decision: data,
    error,
    loading: submitting,
  };
};

// 会话信息Hook
export const useSession = (conversationId: string | null) => {
  const { data, error, loading, refresh } = useApiGet<SessionInfo>(
    conversationId ? `/routing/sessions/${conversationId}` : null
  );
  
  return {
    session: data,
    error,
    loading,
    refresh,
  };
};

// 删除会话Hook
export const useDeleteSession = () => {
  const { trigger, submitting } = useApiDelete('/routing/sessions');
  
  return {
    deleteSession: (conversationId: string) => 
      trigger(`/routing/sessions/${conversationId}`),
    deleting: submitting,
  };
};
```

### 3. 组件拆分

#### 3.1 路由决策组件 (RoutingDecision)

**功能**:
- 提供表单输入路由决策参数
- 调用路由决策API
- 展示决策结果（选中的上游、推理过程、候选列表）
- 支持多种路由策略选择

**状态管理**:
- 使用 `useRoutingDecision` Hook
- 表单状态使用 React Hook Form

**UI设计**:
- 使用Card布局
- 表单区域：逻辑模型选择、策略选择、可选参数
- 结果区域：决策详情、候选上游对比表格

#### 3.2 会话管理组件 (SessionManagement)

**功能**:
- 查询会话信息
- 展示会话详情（会话ID、逻辑模型、提供商、模型、时间戳）
- 删除会话（取消粘性）

**状态管理**:
- 使用 `useSession` 和 `useDeleteSession` Hooks
- 输入会话ID进行查询

**UI设计**:
- 使用Card布局
- 搜索框输入会话ID
- 会话详情展示区
- 删除按钮

#### 3.3 重构路由表单 (RoutingForm)

**改进**:
- 集成到路由决策组件中
- 使用真实的API调用
- 添加表单验证
- 支持所有API参数

#### 3.4 重构路由表格 (RoutingTable)

**改进**:
- 展示路由决策的候选列表
- 显示评分、指标等详细信息
- 支持排序和筛选

### 4. 页面结构

#### 4.1 服务器组件 (page.tsx)

```typescript
// 服务器组件 - 只负责布局
export default function RoutingPage() {
  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-3xl font-bold mb-2">
          {/* 使用服务器端翻译或客户端组件 */}
        </h1>
        <p className="text-muted-foreground">
          {/* 描述文本 */}
        </p>
      </div>
      
      <RoutingClient />
    </div>
  );
}
```

#### 4.2 客户端容器 (routing-client.tsx)

```typescript
"use client";

export function RoutingClient() {
  const { t } = useI18n();
  
  return (
    <Tabs defaultValue="decision">
      <TabsList>
        <TabsTrigger value="decision">{t('routing.tab_decision')}</TabsTrigger>
        <TabsTrigger value="sessions">{t('routing.tab_sessions')}</TabsTrigger>
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

### 5. 国际化支持

在 `frontend/lib/i18n-context.tsx` 中添加路由相关的翻译：

```typescript
// 英文
"routing.title": "Routing Management",
"routing.subtitle": "Configure intelligent request routing strategies",
"routing.tab_decision": "Routing Decision",
"routing.tab_sessions": "Session Management",
"routing.decision.title": "Make Routing Decision",
"routing.decision.logical_model": "Logical Model",
"routing.decision.strategy": "Strategy",
"routing.decision.strategy_latency": "Latency First",
"routing.decision.strategy_cost": "Cost First",
"routing.decision.strategy_reliability": "Reliability First",
"routing.decision.strategy_balanced": "Balanced",
"routing.decision.conversation_id": "Conversation ID (Optional)",
"routing.decision.preferred_region": "Preferred Region (Optional)",
"routing.decision.exclude_providers": "Exclude Providers (Optional)",
"routing.decision.btn_decide": "Make Decision",
"routing.decision.result_title": "Decision Result",
"routing.decision.selected_upstream": "Selected Upstream",
"routing.decision.decision_time": "Decision Time",
"routing.decision.reasoning": "Reasoning",
"routing.decision.candidates": "All Candidates",
"routing.session.title": "Session Management",
"routing.session.search_placeholder": "Enter conversation ID",
"routing.session.btn_search": "Search",
"routing.session.btn_delete": "Delete Session",
"routing.session.info_title": "Session Information",
"routing.session.conversation_id": "Conversation ID",
"routing.session.logical_model": "Logical Model",
"routing.session.provider": "Provider",
"routing.session.model": "Model",
"routing.session.created_at": "Created At",
"routing.session.last_used_at": "Last Used At",

// 中文
"routing.title": "路由管理",
"routing.subtitle": "配置智能请求路由策略",
"routing.tab_decision": "路由决策",
"routing.tab_sessions": "会话管理",
"routing.decision.title": "执行路由决策",
"routing.decision.logical_model": "逻辑模型",
"routing.decision.strategy": "路由策略",
"routing.decision.strategy_latency": "延迟优先",
"routing.decision.strategy_cost": "成本优先",
"routing.decision.strategy_reliability": "可靠性优先",
"routing.decision.strategy_balanced": "均衡",
"routing.decision.conversation_id": "会话ID（可选）",
"routing.decision.preferred_region": "首选区域（可选）",
"routing.decision.exclude_providers": "排除提供商（可选）",
"routing.decision.btn_decide": "执行决策",
"routing.decision.result_title": "决策结果",
"routing.decision.selected_upstream": "选中的上游",
"routing.decision.decision_time": "决策耗时",
"routing.decision.reasoning": "决策理由",
"routing.decision.candidates": "所有候选",
"routing.session.title": "会话管理",
"routing.session.search_placeholder": "输入会话ID",
"routing.session.btn_search": "搜索",
"routing.session.btn_delete": "删除会话",
"routing.session.info_title": "会话信息",
"routing.session.conversation_id": "会话ID",
"routing.session.logical_model": "逻辑模型",
"routing.session.provider": "提供商",
"routing.session.model": "模型",
"routing.session.created_at": "创建时间",
"routing.session.last_used_at": "最后使用时间",
```

## 实施步骤

### 阶段1: 基础设施 (1-2小时)
1. ✅ 查看API文档
2. ✅ 分析现有代码
3. ⏳ 创建SWR Hooks (`use-routing.ts`)
4. ⏳ 添加国际化翻译

### 阶段2: 组件开发 (3-4小时)
5. ⏳ 创建路由决策组件
6. ⏳ 创建会话管理组件
7. ⏳ 重构路由表格组件
8. ⏳ 重构路由表单组件

### 阶段3: 集成和优化 (2-3小时)
9. ⏳ 创建客户端容器组件
10. ⏳ 更新页面主组件
11. ⏳ 测试所有功能
12. ⏳ 优化用户体验和错误处理

## 技术要点

### 1. 服务器组件 vs 客户端组件
- **page.tsx**: 服务器组件，负责布局和SEO
- **routing-client.tsx**: 客户端组件，包含所有交互逻辑
- 使用 `"use client"` 指令标记客户端组件

### 2. SWR最佳实践
- 使用封装好的Hooks而不是直接调用API
- 合理设置缓存策略（路由决策不需要缓存）
- 处理加载、错误状态
- 使用乐观更新提升用户体验

### 3. 组件设计原则
- 单一职责：每个组件只负责一个功能
- 可复用：提取通用逻辑到Hooks
- 类型安全：使用TypeScript定义所有接口
- 用户友好：提供清晰的加载和错误提示

### 4. 国际化实现
- 所有文本通过 `useI18n()` Hook获取
- 支持中英文切换
- 保持翻译的一致性和准确性

## 预期成果

### 功能完整性
- ✅ 路由决策功能完全可用
- ✅ 会话管理功能完全可用
- ✅ 支持所有API参数
- ✅ 完整的错误处理

### 用户体验
- ✅ 清晰的界面布局
- ✅ 流畅的交互体验
- ✅ 实时的加载状态
- ✅ 友好的错误提示
- ✅ 完整的中英文支持

### 代码质量
- ✅ 组件职责清晰
- ✅ 代码可维护性高
- ✅ 类型安全
- ✅ 遵循项目规范

## 注意事项

1. **API认证**: 确保所有请求都包含正确的认证信息
2. **错误处理**: 妥善处理网络错误、API错误等异常情况
3. **性能优化**: 避免不必要的重新渲染和API调用
4. **用户反馈**: 提供清晰的操作反馈（成功、失败、加载中）
5. **数据验证**: 在前端进行基本的数据验证
6. **响应式设计**: 确保在不同屏幕尺寸下都能正常使用

## 后续优化

1. 添加路由决策历史记录
2. 支持批量会话管理
3. 添加路由策略对比功能
4. 集成实时监控数据
5. 支持自定义路由规则配置

## 参考资料

- API文档: `docs/backend/API_Documentation.md`
- SWR文档: `frontend/lib/swr/README.md`
- 国际化实现: `frontend/lib/i18n-context.tsx`
- 现有组件示例: `frontend/app/dashboard/providers/page.tsx`