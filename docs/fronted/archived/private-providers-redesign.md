# 私有提供商管理页面重构设计方案

## 一、问题分析

### 当前架构问题

1. **视角混淆**：`/dashboard/providers` 同时承载用户视角和管理员视角
   - 用户关心：我能用哪些 Provider + 我创建的私有 Provider
   - 管理员关心：系统 Provider 池、审核、配额策略
   
2. **权限控制不清晰**：
   - 公共 Provider 不应该有编辑/删除入口
   - 私有 Provider 只有 owner 可以操作
   - 缺少明确的权限门控

3. **功能缺失**：
   - 没有配额展示（已创建数量/上限）
   - 没有健康状态统计
   - 没有独立的私有 Provider 管理中心

4. **API 调用不统一**：
   - 创建时使用 `/v1/private-providers`
   - 列表使用 `/users/{user_id}/providers`
   - 应该统一使用用户级别的 API

## 二、新架构设计

### 2.1 页面结构

```
/dashboard/providers          → 用户视角：Provider 目录（我能用什么）
/dashboard/my-providers       → 用户视角：私有 Provider 管理中心（我创建的）
/dashboard/providers/[id]     → Provider 详情页（通用）
/dashboard/providers/[id]/keys → Provider 密钥管理（权限控制）
```

### 2.2 页面职责划分

#### `/dashboard/providers` - Provider 目录页

**定位**：用户视角的 Provider 目录，展示"我能用的所有 Provider"

**功能**：
- 展示当前用户可用的全部 Provider（私有 + 公共）
- 顶部搜索 + visibility 筛选
- Tabs 切换：All Available / My Private / Public
- 操作权限：
  - 私有 Provider：查看详情、管理密钥、编辑、删除
  - 公共 Provider：仅查看详情
- CTA：Add Provider（创建私有 Provider）

**数据来源**：
- API: `GET /users/{user_id}/providers?visibility={all|private|public}`
- 返回：`{ private_providers: [], public_providers: [], total: number }`

#### `/dashboard/my-providers` - 私有 Provider 管理中心（新增）

**定位**：用户私有 Provider 的专属管理页面

**功能**：
1. **配额卡片**（顶部）
   - 显示：当前私有 Provider 数 / 上限
   - 进度条可视化
   - 数据来源：`GET /users/{user_id}/private-providers` + 后端配额 API

2. **健康状态概览**（顶部）
   - 统计：Healthy / Degraded / Down 数量
   - 小型图表展示
   - 数据来源：聚合 Provider 的 status 字段

3. **私有 Provider 列表**
   - 复用 `ProvidersTableEnhanced` 组件
   - 初始 visibilityFilter 固定为 'private'
   - 完整的 CRUD 操作

4. **快速操作**
   - 批量健康检查
   - 快速创建（预设模板）

**数据来源**：
- API: `GET /users/{user_id}/private-providers`
- 配额: `GET /users/{user_id}/quota` 或从 private-providers 响应中获取

#### `/dashboard/providers/[id]` - Provider 详情页（已存在）

**保持现状**，使用 `ProviderDetailClient` 组件

**Tabs**：
- Overview：基本信息、配置
- Models：模型列表
- Keys：密钥管理（权限控制）
- Metrics：性能指标

#### `/dashboard/providers/[id]/keys` - 密钥管理页（已存在）

**权限控制**：
- 前端：检查 `user.is_superuser` 或 `provider.owner_id === user.id`
- 后端：已有权限校验

### 2.3 组件复用策略

```typescript
// 核心组件复用
ProvidersTableEnhanced        // 表格组件（私有/公共/全部）
ProviderFormEnhanced          // 创建/编辑表单
ProviderDetailClient          // 详情页
ProviderKeysTable             // 密钥管理表格

// 新增组件
PrivateProviderQuotaCard      // 配额卡片
PrivateProviderHealthStats    // 健康状态统计
MyProvidersPageClient         // 私有管理页客户端组件
```

## 三、详细设计

### 3.1 `/dashboard/providers` 重构

#### 页面元数据
```typescript
// app/dashboard/providers/page.tsx
export const metadata = {
  title: "Provider 目录",
  description: "查看和管理您可用的 AI 模型提供商"
};
```

#### 功能调整
1. **明确文案**：
   - Title: "Provider 目录" / "Provider Directory"
   - Subtitle: "查看您可用的私有和公共提供商" / "View your available private and public providers"

2. **权限控制**：
   ```typescript
   const canModify = (provider: Provider) => {
     if (provider.visibility === 'private') {
       return provider.owner_id === currentUserId;
     }
     return false; // 公共 Provider 不允许普通用户修改
   };
   ```

3. **操作按钮**：
   - 私有 Provider：详情、模型、密钥、编辑、删除
   - 公共 Provider：仅详情、模型

### 3.2 `/dashboard/my-providers` 新页面

#### 文件结构
```
frontend/app/dashboard/my-providers/
├── page.tsx                          # 服务端页面
└── components/
    ├── my-providers-page-client.tsx  # 客户端组件
    ├── quota-card.tsx                # 配额卡片
    └── health-stats.tsx              # 健康统计
```

#### 配额卡片设计
```typescript
// components/quota-card.tsx
interface QuotaCardProps {
  current: number;
  limit: number;
  isLoading?: boolean;
}

export function QuotaCard({ current, limit, isLoading }: QuotaCardProps) {
  const percentage = (current / limit) * 100;
  const remaining = limit - current;
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>私有 Provider 配额</CardTitle>
        <CardDescription>
          您已创建 {current} 个，还可创建 {remaining} 个
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>已使用</span>
            <span className="font-medium">{current} / {limit}</span>
          </div>
          <Progress value={percentage} />
          {percentage >= 80 && (
            <Alert variant="warning">
              <AlertDescription>
                配额即将用完，请联系管理员提升限额
              </AlertDescription>
            </Alert>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
```

#### 健康状态统计设计
```typescript
// components/health-stats.tsx
interface HealthStatsProps {
  providers: Provider[];
}

export function HealthStats({ providers }: HealthStatsProps) {
  const stats = useMemo(() => {
    const healthy = providers.filter(p => p.status === 'healthy').length;
    const degraded = providers.filter(p => p.status === 'degraded').length;
    const down = providers.filter(p => p.status === 'down').length;
    
    return { healthy, degraded, down, total: providers.length };
  }, [providers]);
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>健康状态</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600">
              {stats.healthy}
            </div>
            <div className="text-sm text-muted-foreground">运行中</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-yellow-600">
              {stats.degraded}
            </div>
            <div className="text-sm text-muted-foreground">降级</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600">
              {stats.down}
            </div>
            <div className="text-sm text-muted-foreground">故障</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
```

#### 主页面组件
```typescript
// components/my-providers-page-client.tsx
export function MyProvidersPageClient({
  initialProviders,
  initialQuota,
  userId
}: MyProvidersPageClientProps) {
  const [providers, setProviders] = useState(initialProviders);
  const [quota, setQuota] = useState(initialQuota);
  
  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-3xl font-bold">我的私有 Provider</h1>
        <p className="text-muted-foreground">
          管理您的私有提供商与配额
        </p>
      </div>
      
      {/* 顶部统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <QuotaCard 
          current={providers.length} 
          limit={quota.limit} 
        />
        <HealthStats providers={providers} />
      </div>
      
      {/* 操作栏 */}
      <div className="flex justify-between items-center">
        <Input 
          placeholder="搜索私有 Provider..." 
          className="max-w-sm"
        />
        <Button onClick={handleCreate}>
          <Plus className="w-4 h-4 mr-2" />
          创建 Provider
        </Button>
      </div>
      
      {/* Provider 列表 */}
      <ProvidersTableEnhanced
        privateProviders={providers}
        publicProviders={[]}
        currentUserId={userId}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onViewDetails={handleViewDetails}
      />
    </div>
  );
}
```

### 3.3 API 调用统一

#### 统一使用用户级别 API

```typescript
// http/provider.ts 中已有的 API
providerService.getUserAvailableProviders(userId, visibility)
providerService.getUserPrivateProviders(userId)
providerService.createPrivateProvider(userId, data)
providerService.updatePrivateProvider(userId, providerId, data)
providerService.deletePrivateProvider(userId, providerId)
```

#### 修改 ProviderFormEnhanced

```typescript
// components/dashboard/providers/provider-form.tsx
// 修改创建逻辑
const handleFormSubmit = async (values: any) => {
  try {
    setIsSubmitting(true);
    
    // 从 auth store 获取当前用户 ID
    const userId = useAuthStore.getState().user?.id;
    if (!userId) {
      throw new Error("用户未登录");
    }
    
    const payload: CreatePrivateProviderRequest = {
      // ... 构建 payload
    };
    
    // 使用用户级别 API
    await providerService.createPrivateProvider(userId, payload);
    
    toast.success("Provider 创建成功");
    // ...
  } catch (error) {
    // ...
  }
};
```

### 3.4 导航结构调整

#### Sidebar 导航更新

```typescript
// components/layout/sidebar-nav.tsx
const navItems = [
  {
    titleKey: "nav.overview",
    href: "/dashboard/overview",
    icon: LayoutDashboard,
  },
  {
    titleKey: "nav.providers",
    href: "/dashboard/providers",
    icon: Server,
  },
  {
    titleKey: "nav.my_providers",  // 新增
    href: "/dashboard/my-providers",
    icon: Lock,
  },
  // ... 其他项
];
```

#### 国际化文案

```typescript
// lib/i18n/navigation.ts
export const navigationTranslations = {
  en: {
    "nav.providers": "Providers",
    "nav.my_providers": "My Providers",
  },
  zh: {
    "nav.providers": "Provider 目录",
    "nav.my_providers": "我的 Provider",
  }
};

// lib/i18n/providers.ts 新增
export const providersTranslations = {
  en: {
    // Provider 目录页
    "providers.directory_title": "Provider Directory",
    "providers.directory_subtitle": "View your available private and public providers",
    
    // 我的 Provider 页
    "my_providers.title": "My Private Providers",
    "my_providers.subtitle": "Manage your private providers and quota",
    "my_providers.quota_title": "Private Provider Quota",
    "my_providers.quota_description": "You have created {current} providers, {remaining} remaining",
    "my_providers.quota_warning": "Quota almost full, please contact admin to increase limit",
    "my_providers.health_title": "Health Status",
    "my_providers.health_healthy": "Healthy",
    "my_providers.health_degraded": "Degraded",
    "my_providers.health_down": "Down",
    "my_providers.action_manage_keys": "Manage Keys",
  },
  zh: {
    // Provider 目录页
    "providers.directory_title": "Provider 目录",
    "providers.directory_subtitle": "查看您可用的私有和公共提供商",
    
    // 我的 Provider 页
    "my_providers.title": "我的私有 Provider",
    "my_providers.subtitle": "管理您的私有提供商与配额",
    "my_providers.quota_title": "私有 Provider 配额",
    "my_providers.quota_description": "您已创建 {current} 个，还可创建 {remaining} 个",
    "my_providers.quota_warning": "配额即将用完，请联系管理员提升限额",
    "my_providers.health_title": "健康状态",
    "my_providers.health_healthy": "运行中",
    "my_providers.health_degraded": "降级",
    "my_providers.health_down": "故障",
    "my_providers.action_manage_keys": "管理密钥",
  }
};
```

## 四、实施步骤

### 阶段一：基础重构（最小改动）

1. **调整 `/dashboard/providers` 页面**
   - [ ] 更新页面文案（Title/Subtitle）
   - [ ] 强化权限控制逻辑
   - [ ] 移除公共 Provider 的编辑/删除入口
   - [ ] 添加顶部小统计（可选）

2. **统一 API 调用**
   - [ ] 修改 `ProviderFormEnhanced` 使用 `providerService.createPrivateProvider(userId, data)`
   - [ ] 确保所有 CRUD 操作使用用户级别 API

3. **更新国际化文案**
   - [ ] 添加新的翻译 key
   - [ ] 更新现有文案使其更明确

### 阶段二：新增私有管理页（推荐）

4. **创建 `/dashboard/my-providers` 页面**
   - [ ] 创建页面文件结构
   - [ ] 实现配额卡片组件
   - [ ] 实现健康状态统计组件
   - [ ] 实现主页面客户端组件
   - [ ] 复用 `ProvidersTableEnhanced`

5. **添加导航入口**
   - [ ] 更新 Sidebar 导航
   - [ ] 添加面包屑导航
   - [ ] 更新路由配置

6. **实现配额 API**
   - [ ] 后端：添加配额查询接口（如果没有）
   - [ ] 前端：集成配额数据获取

### 阶段三：完善功能

7. **增强交互体验**
   - [ ] 添加批量健康检查功能
   - [ ] 添加快速创建模板
   - [ ] 优化加载状态和错误处理

8. **权限门控**
   - [ ] 密钥管理页添加权限检查
   - [ ] 详情页根据权限显示/隐藏操作

9. **测试和优化**
   - [ ] 单元测试
   - [ ] 集成测试
   - [ ] 性能优化

## 五、技术要点

### 5.1 权限控制模式

```typescript
// 权限检查 Hook
function useProviderPermissions(provider: Provider) {
  const { user } = useAuthStore();
  
  const canEdit = useMemo(() => {
    if (!user) return false;
    if (provider.visibility === 'private') {
      return provider.owner_id === user.id;
    }
    return user.is_superuser;
  }, [user, provider]);
  
  const canDelete = canEdit;
  const canManageKeys = canEdit;
  const canView = true;
  
  return { canEdit, canDelete, canManageKeys, canView };
}
```

### 5.2 数据获取策略

```typescript
// 使用 SWR 进行数据缓存
function useMyPrivateProviders(userId: string) {
  const { data, error, mutate } = useSWR(
    userId ? `/users/${userId}/private-providers` : null,
    () => providerService.getUserPrivateProviders(userId),
    {
      revalidateOnFocus: true,
      dedupingInterval: 5000,
    }
  );
  
  return {
    providers: data || [],
    isLoading: !error && !data,
    isError: error,
    refresh: mutate,
  };
}
```

### 5.3 组件通信

```typescript
// 使用 Context 共享状态（可选）
const ProviderManagementContext = createContext<{
  refresh: () => Promise<void>;
  isRefreshing: boolean;
}>({
  refresh: async () => {},
  isRefreshing: false,
});
```

## 六、UI/UX 设计要点

### 6.1 视觉层次

1. **Provider 目录页**：
   - 强调"可用性"概念
   - 私有/公共 Provider 视觉区分（图标、颜色）
   - 操作按钮根据权限显示/禁用

2. **私有管理页**：
   - 顶部配额和健康状态突出显示
   - 使用进度条、图表增强可视化
   - 警告状态（配额不足、Provider 故障）醒目提示

### 6.2 交互流程

1. **创建流程**：
   - 两个入口：Provider 目录页 + 私有管理页
   - 统一使用 `ProviderFormEnhanced`
   - 创建成功后刷新列表

2. **编辑流程**：
   - 仅私有 Provider 可编辑
   - 表单预填充现有数据
   - 支持部分字段更新

3. **删除流程**：
   - 二次确认对话框
   - 显示 Provider ID
   - 删除后自动刷新

### 6.3 响应式设计

- 移动端：卡片布局，操作按钮收起到菜单
- 平板：2 列网格
- 桌面：完整表格视图

## 七、后续优化方向

1. **批量操作**：
   - 批量健康检查
   - 批量启用/禁用
   - 批量删除

2. **高级筛选**：
   - 按状态筛选
   - 按区域筛选
   - 按创建时间筛选

3. **导出功能**：
   - 导出 Provider 配置
   - 导出健康报告

4. **监控告警**：
   - Provider 故障通知
   - 配额预警通知

## 八、总结

### 核心改进

1. **明确视角分离**：
   - `/dashboard/providers`：用户视角的 Provider 目录
   - `/dashboard/my-providers`：用户私有 Provider 管理中心

2. **权限控制清晰**：
   - 公共 Provider 只读
   - 私有 Provider 仅 owner 可操作
   - 密钥管理有权限门控

3. **功能完善**：
   - 配额展示和管理
   - 健康状态统计
   - 统一的 API 调用

4. **组件复用**：
   - 最大化复用现有组件
   - 新增组件职责单一
   - 易于维护和扩展

### 实施建议

- **最小改动版**：先完成阶段一，快速上线
- **完整版**：逐步完成阶段二和三，提供完整体验
- **迭代优化**：根据用户反馈持续改进

---

**文档版本**: 1.0  
**创建日期**: 2025-12-05  
**作者**: AI Architect