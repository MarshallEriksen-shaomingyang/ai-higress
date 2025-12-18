# PermissionGuard 使用示例

## 完整示例：系统仪表盘页面

### 1. 页面组件（服务端组件）

```tsx
// frontend/app/dashboard/system/page.tsx
import { PermissionGuard } from "@/components/auth/permission-guard";
import { SystemDashboardClient } from "./_components/system-dashboard-client";

/**
 * 系统仪表盘页面（服务端组件）
 * 使用 PermissionGuard 保护页面，只允许管理员访问
 */
export default function SystemDashboardPage() {
  return (
    <PermissionGuard requiredPermission="superuser">
      <SystemDashboardClient />
    </PermissionGuard>
  );
}
```

### 2. 客户端组件

```tsx
// frontend/app/dashboard/system/_components/system-dashboard-client.tsx
"use client";

import { useState } from "react";
import { FilterBar } from "@/components/dashboard/filter-bar";
import { KPICardsGrid } from "@/components/dashboard/kpi-cards-grid";
import { useSystemDashboardKPIs } from "@/lib/swr/use-dashboard-v2";

export function SystemDashboardClient() {
  const [timeRange, setTimeRange] = useState("7d");
  const [transport, setTransport] = useState("all");
  const [isStream, setIsStream] = useState("all");

  const { data: kpiData, isLoading, error } = useSystemDashboardKPIs({
    time_range: timeRange,
    transport,
    is_stream: isStream,
  });

  return (
    <div className="space-y-6">
      <FilterBar
        timeRange={timeRange}
        onTimeRangeChange={setTimeRange}
        transport={transport}
        onTransportChange={setTransport}
        isStream={isStream}
        onIsStreamChange={setIsStream}
      />
      
      <KPICardsGrid data={kpiData} isLoading={isLoading} error={error} />
      
      {/* 其他组件... */}
    </div>
  );
}
```

## 测试场景

### 场景 1：管理员访问
- ✅ 用户登录且 `is_superuser = true`
- ✅ 显示完整的系统仪表盘内容
- ✅ 可以查看所有 KPI 和 Provider 状态

### 场景 2：普通用户访问
- ❌ 用户登录但 `is_superuser = false`
- ❌ 显示 403 错误页面
- ℹ️ 提示需要管理员权限
- 🔙 提供返回按钮

### 场景 3：未登录用户访问
- ❌ 用户未登录（`user = null`）
- ❌ 显示 403 错误页面
- 🔐 需要先登录并拥有管理员权限

## 权限检查流程

```
用户访问系统页面
    ↓
PermissionGuard 检查
    ↓
┌─────────────────┐
│ 用户信息加载中？ │
└────┬────────────┘
     │
     ├─ 是 → 显示加载状态
     │
     └─ 否 → 检查权限
            ↓
     ┌──────────────┐
     │ 是管理员？    │
     └──┬───────────┘
        │
        ├─ 是 → 渲染子组件（系统仪表盘）
        │
        └─ 否 → 显示 403 错误页面
```

## 多层权限防护

为了确保安全性，建议实现三层权限检查：

### 1. 客户端检查（PermissionGuard）
```tsx
<PermissionGuard requiredPermission="superuser">
  <SystemDashboard />
</PermissionGuard>
```

### 2. 服务端检查（可选，在 page.tsx 中）
```tsx
import { authService } from "@/http/auth";
import { redirect } from "next/navigation";

export default async function SystemDashboardPage() {
  // 服务端获取用户信息
  const user = await authService.getCurrentUser().catch(() => null);
  
  // 如果不是管理员，重定向到首页
  if (!user || !user.is_superuser) {
    redirect("/");
  }

  return (
    <PermissionGuard requiredPermission="superuser">
      <SystemDashboardClient />
    </PermissionGuard>
  );
}
```

### 3. API 层检查（后端）
```python
# backend/app/api/system_routes.py
from app.deps import get_current_superuser

@router.get("/metrics/v2/system-dashboard/kpis")
async def get_system_kpis(
    current_user: User = Depends(get_current_superuser)
):
    # 只有管理员可以访问
    ...
```

## 注意事项

1. **客户端组件**: `PermissionGuard` 必须在客户端使用（已标记 `"use client"`）
2. **认证状态**: 确保在根布局中已初始化认证状态
3. **错误处理**: 组件会自动处理加载和错误状态
4. **国际化**: 所有文案都支持中英文切换
5. **用户体验**: 提供友好的错误提示和返回操作

## 相关文档

- [认证组件 README](./README.md)
- [系统仪表盘设计文档](../../../.kiro/specs/system-dashboard-refactor/design.md)
- [系统仪表盘需求文档](../../../.kiro/specs/system-dashboard-refactor/requirements.md)
