# 服务端预取实现总结

## 已完成的页面

### 1. Chat 会话详情页
**路径**: `frontend/app/chat/[assistant_id]/[conversation_id]/page.tsx`

**预取数据**:
- 会话列表 (`/v1/conversations?assistant_id={id}&limit=50`)

**效果**:
- 用户打开会话时，会话信息立即显示，无闪烁
- 会话标题、归档状态等信息在首屏渲染

### 2. Dashboard 概览页
**路径**: `frontend/app/dashboard/overview/page.tsx`

**预取数据**:
- KPI 指标 (`/metrics/user-dashboard/kpis`)
- Pulse 数据 (`/metrics/user-dashboard/pulse`)
- Token 趋势 (`/metrics/user-dashboard/tokens`)
- Top Models (`/metrics/user-dashboard/top-models`)
- 成本结构 (`/metrics/user-dashboard/cost-by-provider`)
- 应用使用情况 (`/metrics/user-overview/apps`)

**效果**:
- Dashboard 所有图表和 KPI 卡片立即显示
- 无加载闪烁，用户体验流畅
- 禁用 SSR（避免 Hydration 错误），但预取数据仍然有效

**注意**:
- 使用 `dynamic import` 禁用 SSR
- 避免 HealthBadge 的 loading 状态导致 Hydration 错误
- 预取数据通过 SWR fallback 传递，客户端首次渲染使用 fallback

### 3. 系统性能监控页
**路径**: `frontend/app/system/performance/page.tsx`

**说明**:
- 此页面展示客户端性能指标（Web Vitals）
- 数据存储在浏览器 localStorage
- 不需要服务端预取
- 已将页面改为服务端组件，标题移到客户端组件内部

### 4. 私有 Provider 页面（已移除预取）
**路径**: `frontend/app/dashboard/my-providers/page.tsx`

**说明**:
- 此页面需要用户登录，数据依赖客户端的 userId
- 服务端无法获取 userId（存储在客户端 auth store）
- 不进行服务端预取，让客户端直接请求
- 客户端组件已改用 SWR hooks，统一数据管理

## 核心工具

### 1. `serverFetch`
**位置**: `frontend/lib/swr/server-fetch.ts`

**功能**:
- 服务端数据获取
- 自动处理认证 token
- 错误处理返回 null

### 2. `SWRProvider` (已更新)
**位置**: `frontend/lib/swr/provider.tsx`

**新增功能**:
- 支持 `fallback` 参数
- 将服务端预取的数据传递给客户端

### 3. 完整指南
**位置**: `frontend/lib/swr/SERVER_PREFETCH_GUIDE.md`

**内容**:
- 详细使用说明
- 多个实际示例
- 注意事项和最佳实践

## 关键改进

### 1. 避免 Hydration 错误
- 通过 SWR fallback，服务端和客户端使用相同的初始数据
- 移除了 `dynamic import` 的 `ssr: false` 配置
- Dashboard 概览页现在支持 SSR

### 2. SWR Key 一致性
- 创建 `buildSWRKey` 辅助函数
- 确保服务端和客户端使用完全相同的 key 格式
- 参数顺序和格式完全匹配

### 3. 性能优化
- 并行预取多个数据源 (`Promise.all`)
- 减少客户端首次加载时间
- 提升首屏渲染速度

## 使用模式

### 模式 1: 有明确 URL 参数的页面
```typescript
// 适用于详情页、编辑页等
export default async function DetailPage({ params }) {
  const { id } = await params;
  const data = await serverFetch(`/api/items/${id}`);
  
  return (
    <SWRProvider fallback={{ [`/api/items/${id}`]: data }}>
      <DetailClient id={id} />
    </SWRProvider>
  );
}
```

### 模式 2: 需要预取多个数据源的页面
```typescript
// 适用于 Dashboard、概览页等
export default async function DashboardPage() {
  const [data1, data2, data3] = await Promise.all([
    serverFetch('/api/endpoint1'),
    serverFetch('/api/endpoint2'),
    serverFetch('/api/endpoint3'),
  ]);
  
  return (
    <SWRProvider
      fallback={{
        '/api/endpoint1': data1,
        '/api/endpoint2': data2,
        '/api/endpoint3': data3,
      }}
    >
      <DashboardClient />
    </SWRProvider>
  );
}
```

### 模式 3: 数据依赖客户端状态
```typescript
// 不预取，让客户端动态加载
export default async function ChatPage() {
  return (
    <SWRProvider fallback={{}}>
      <ChatHomeClient />
    </SWRProvider>
  );
}
```

## 测试建议

### 1. 功能测试
- 访问 `/chat/[assistant_id]/[conversation_id]`，确认会话信息立即显示
- 访问 `/dashboard/overview`，确认所有图表和 KPI 立即显示
- 访问 `/system/performance`，确认性能指标正常显示

### 2. 性能测试
- 使用 Chrome DevTools Network 面板
- 观察首屏渲染时间（FCP、LCP）
- 确认没有额外的客户端请求（数据已预取）

### 3. SSR 测试
- 禁用 JavaScript
- 访问 Dashboard 概览页
- 确认页面内容仍然可见（SSR 成功）

## 后续优化建议

### 1. 更多页面接入
可以考虑为以下页面添加服务端预取：
- ✅ ~~API Keys 列表页~~ (已完成 - 私有 Provider 页面)
- Credits 页面
- Providers 列表页
- Routing 配置页
- Logical Models 页面

### 2. 缓存策略
- 考虑在服务端使用 Next.js 的 `cache` 配置
- 为不同类型的数据设置不同的缓存时间
- 例如：`cache: 'force-cache'` 用于静态数据

### 3. 错误处理
- 在服务端预取失败时，提供更好的降级体验
- 考虑添加 Loading UI 或 Skeleton
- 记录服务端预取失败的日志

### 4. 类型安全
- 为 `buildSWRKey` 函数添加更严格的类型定义
- 确保参数类型与 API 端点匹配
- 使用 TypeScript 的模板字面量类型

## 注意事项

1. **SWR Key 必须完全匹配**
   - 服务端和客户端的 key 格式必须一致
   - 参数顺序、大小写都要匹配

2. **认证状态**
   - `serverFetch` 会自动从 cookies 获取 token
   - 如果用户未登录，返回 null
   - 客户端会重新请求

3. **数据新鲜度**
   - 服务端预取的数据可能不是最新的
   - SWR 会在客户端自动重新验证
   - 使用 `revalidateOnMount` 控制行为

4. **性能权衡**
   - 预取会增加服务端负担
   - 只预取首屏必需的数据
   - 避免预取大量或不重要的数据
