# AI Higress 错误页面设计方案

## 设计概述

基于 AI Higress 项目的"水墨雅韵"设计理念，为 Next.js 应用设计 404 和 500 错误页面。设计遵循项目现有的 shadcn/ui + Tailwind CSS 技术栈，保持与整体风格的一致性。

## 设计原则

1. **简洁优雅**：采用极简设计，突出错误信息
2. **用户友好**：提供清晰的错误说明和解决方案
3. **品牌一致**：延续"水墨"美学风格
4. **响应式设计**：适配桌面、平板、移动设备
5. **国际化支持**：完整的中英文双语支持

## 技术栈

- **框架**: Next.js 16.0
- **UI 组件**: shadcn/ui (已有组件)
- **样式**: Tailwind CSS 4.0
- **图标**: Lucide React
- **国际化**: 项目内置 I18nContext

## 404 页面设计

### 视觉设计

#### 布局结构
```
┌─────────────────────────────────────┐
│                                     │
│         [大号 404 数字]              │
│                                     │
│      [页面未找到标题]                │
│                                     │
│    [友好的错误描述文案]              │
│                                     │
│  [返回首页按钮] [返回上一页按钮]     │
│                                     │
│      [常用页面快捷链接]              │
│                                     │
└─────────────────────────────────────┘
```

#### 设计元素

1. **404 数字显示**
   - 超大字号（text-9xl 或更大）
   - 使用渐变色或水墨风格的文字效果
   - 可选：添加微妙的动画效果（淡入或轻微浮动）

2. **错误标题**
   - 清晰的"页面未找到"文案
   - 中等字号（text-2xl 或 text-3xl）
   - 使用 muted-foreground 颜色

3. **描述文案**
   - 友好的提示信息
   - 小字号（text-base 或 text-lg）
   - 提供可能的原因和建议

4. **操作按钮**
   - 主按钮：返回首页（primary variant）
   - 次按钮：返回上一页（outline variant）
   - 使用 Button 组件，带图标

5. **快捷链接**
   - 卡片式布局展示常用页面
   - 使用 Card 组件
   - 包含图标和简短描述

### 交互设计

1. **页面加载**
   - 淡入动画（fade-in）
   - 404 数字可以有轻微的缩放效果

2. **按钮交互**
   - Hover 状态：颜色变化和轻微抬升
   - 点击反馈：涟漪效果

3. **快捷链接**
   - Hover 时卡片轻微抬升
   - 平滑的过渡动画

### 响应式设计

- **桌面 (≥1024px)**
  - 404 数字：text-9xl
  - 快捷链接：3 列网格布局
  - 按钮：并排显示

- **平板 (768px-1023px)**
  - 404 数字：text-8xl
  - 快捷链接：2 列网格布局
  - 按钮：并排显示

- **移动 (<768px)**
  - 404 数字：text-7xl
  - 快捷链接：1 列布局
  - 按钮：垂直堆叠

## 500 页面设计

### 视觉设计

#### 布局结构
```
┌─────────────────────────────────────┐
│                                     │
│         [警告图标]                   │
│                                     │
│      [服务器错误标题]                │
│                                     │
│    [错误描述和安抚文案]              │
│                                     │
│      [错误 ID 显示]                  │
│                                     │
│  [刷新页面按钮] [返回首页按钮]       │
│                                     │
│      [联系支持信息]                  │
│                                     │
└─────────────────────────────────────┘
```

#### 设计元素

1. **警告图标**
   - 使用 AlertTriangle 或 ServerCrash 图标
   - 大尺寸（size-24 或 size-32）
   - 使用 destructive 颜色或警告色

2. **错误标题**
   - "服务器错误"或"出错了"
   - 大字号（text-3xl 或 text-4xl）
   - 醒目但不过于刺眼

3. **描述文案**
   - 安抚用户的友好文案
   - 说明这是临时问题
   - 建议用户稍后重试

4. **错误 ID**
   - 使用 Card 组件展示
   - 包含时间戳和唯一标识
   - 可复制功能（用于技术支持）

5. **操作按钮**
   - 主按钮：刷新页面（带刷新图标）
   - 次按钮：返回首页
   - 可选：联系支持按钮

6. **支持信息**
   - 小字号的联系方式
   - 可选：显示系统状态页面链接

### 交互设计

1. **页面加载**
   - 淡入动画
   - 图标可以有轻微的脉动效果

2. **刷新按钮**
   - 点击时显示加载状态
   - 旋转动画

3. **错误 ID 复制**
   - 点击复制按钮
   - Toast 提示复制成功

### 响应式设计

- **桌面 (≥1024px)**
  - 图标：size-32
  - 按钮：并排显示
  - 错误 ID 卡片：居中，最大宽度 600px

- **平板 (768px-1023px)**
  - 图标：size-24
  - 按钮：并排显示
  - 错误 ID 卡片：全宽，带边距

- **移动 (<768px)**
  - 图标：size-20
  - 按钮：垂直堆叠
  - 错误 ID 卡片：全宽

## 国际化文案

### 404 页面文案

#### 英文 (en)
```typescript
{
  "error.404.title": "404",
  "error.404.heading": "Page Not Found",
  "error.404.description": "Sorry, we couldn't find the page you're looking for. The page may have been moved or deleted.",
  "error.404.suggestion": "Here are some helpful links instead:",
  "error.404.btn_home": "Back to Home",
  "error.404.btn_back": "Go Back",
  "error.404.link_dashboard": "Dashboard",
  "error.404.link_providers": "Providers",
  "error.404.link_docs": "Documentation",
  "error.404.link_support": "Support",
}
```

#### 中文 (zh)
```typescript
{
  "error.404.title": "404",
  "error.404.heading": "页面未找到",
  "error.404.description": "抱歉，我们找不到您要访问的页面。该页面可能已被移动或删除。",
  "error.404.suggestion": "以下是一些有用的链接：",
  "error.404.btn_home": "返回首页",
  "error.404.btn_back": "返回上一页",
  "error.404.link_dashboard": "仪表盘",
  "error.404.link_providers": "提供商",
  "error.404.link_docs": "文档",
  "error.404.link_support": "支持",
}
```

### 500 页面文案

#### 英文 (en)
```typescript
{
  "error.500.title": "500",
  "error.500.heading": "Server Error",
  "error.500.description": "Oops! Something went wrong on our end. We're working to fix the issue. Please try again later.",
  "error.500.error_id": "Error ID",
  "error.500.timestamp": "Timestamp",
  "error.500.btn_refresh": "Refresh Page",
  "error.500.btn_home": "Back to Home",
  "error.500.btn_copy": "Copy Error ID",
  "error.500.support_text": "If the problem persists, please contact support with the error ID above.",
  "error.500.copied": "Error ID copied to clipboard",
}
```

#### 中文 (zh)
```typescript
{
  "error.500.title": "500",
  "error.500.heading": "服务器错误",
  "error.500.description": "抱歉！服务器出现了问题。我们正在努力修复。请稍后再试。",
  "error.500.error_id": "错误 ID",
  "error.500.timestamp": "时间戳",
  "error.500.btn_refresh": "刷新页面",
  "error.500.btn_home": "返回首页",
  "error.500.btn_copy": "复制错误 ID",
  "error.500.support_text": "如果问题持续存在，请联系技术支持并提供上述错误 ID。",
  "error.500.copied": "错误 ID 已复制到剪贴板",
}
```

## 所需组件

### 现有 shadcn/ui 组件
- ✅ `Button` - 操作按钮
- ✅ `Card` - 快捷链接卡片、错误 ID 卡片
- ✅ `Badge` - 可选的状态标识
- ✅ Lucide React 图标 - 各种图标

### 需要安装的组件
无需额外安装，现有组件已足够。

## 文件结构

```
frontend/
├── app/
│   ├── not-found.tsx              # 404 页面（Next.js 约定）
│   └── error.tsx                  # 500 错误页面（Next.js 约定）
├── components/
│   └── error/
│       ├── not-found-content.tsx  # 404 页面内容组件
│       └── error-content.tsx      # 500 错误页面内容组件
└── lib/
    └── i18n-context.tsx           # 添加错误页面文案
```

## 实现要点

### 1. Next.js 错误处理约定

- `app/not-found.tsx` - 处理 404 错误
- `app/error.tsx` - 处理运行时错误（500 等）
- `app/global-error.tsx` - 处理全局错误（可选）

### 2. 错误边界

500 错误页面需要实现为 Error Boundary：
```typescript
'use client' // Error components must be Client Components
 
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  // 实现错误页面
}
```

### 3. 国际化集成

- 使用 `useI18n()` hook 获取翻译函数
- 在 `lib/i18n-context.tsx` 中添加错误页面文案
- 确保客户端组件正确使用 `'use client'` 指令

### 4. 样式一致性

- 使用项目现有的 Tailwind 配置
- 遵循 shadcn/ui 组件的设计规范
- 保持与其他页面的视觉一致性

### 5. 可访问性

- 使用语义化 HTML 标签
- 提供适当的 ARIA 标签
- 确保键盘导航可用
- 保持足够的颜色对比度

## 动画效果

### 推荐动画

1. **页面淡入**
```css
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
```

2. **404 数字动画**（可选）
```css
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}
```

3. **图标脉动**（500 页面）
```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

使用 Tailwind 的 `animate-` 类或自定义动画。

## 测试场景

### 404 页面测试
1. 访问不存在的路由（如 `/non-existent-page`）
2. 验证所有按钮功能
3. 测试快捷链接导航
4. 验证响应式布局
5. 测试中英文切换

### 500 页面测试
1. 模拟服务器错误
2. 验证刷新功能
3. 测试错误 ID 复制
4. 验证响应式布局
5. 测试中英文切换

## 性能考虑

1. **代码分割**：错误页面作为独立组件
2. **图片优化**：如使用背景图，采用 WebP 格式
3. **懒加载**：非关键组件延迟加载
4. **缓存策略**：静态资源长期缓存

## 设计示例

### 404 页面伪代码结构
```tsx
<div className="min-h-screen flex items-center justify-center p-4">
  <div className="max-w-2xl w-full text-center space-y-8">
    {/* 404 数字 */}
    <h1 className="text-9xl font-bold bg-gradient-to-r from-primary to-primary/50 bg-clip-text text-transparent">
      404
    </h1>
    
    {/* 标题和描述 */}
    <div className="space-y-4">
      <h2 className="text-3xl font-semibold">{t('error.404.heading')}</h2>
      <p className="text-muted-foreground">{t('error.404.description')}</p>
    </div>
    
    {/* 操作按钮 */}
    <div className="flex gap-4 justify-center">
      <Button onClick={() => router.push('/')}>
        <Home className="mr-2 h-4 w-4" />
        {t('error.404.btn_home')}
      </Button>
      <Button variant="outline" onClick={() => router.back()}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {t('error.404.btn_back')}
      </Button>
    </div>
    
    {/* 快捷链接 */}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 pt-8">
      {quickLinks.map(link => (
        <Card key={link.href} className="hover:shadow-lg transition-shadow">
          <CardContent className="p-6">
            <link.icon className="h-8 w-8 mb-2" />
            <h3 className="font-semibold">{link.title}</h3>
            <p className="text-sm text-muted-foreground">{link.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  </div>
</div>
```

### 500 页面伪代码结构
```tsx
<div className="min-h-screen flex items-center justify-center p-4">
  <div className="max-w-xl w-full text-center space-y-8">
    {/* 警告图标 */}
    <div className="flex justify-center">
      <AlertTriangle className="h-24 w-24 text-destructive animate-pulse" />
    </div>
    
    {/* 标题和描述 */}
    <div className="space-y-4">
      <h1 className="text-4xl font-bold">{t('error.500.heading')}</h1>
      <p className="text-muted-foreground">{t('error.500.description')}</p>
    </div>
    
    {/* 错误 ID 卡片 */}
    <Card>
      <CardContent className="p-6 space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm font-medium">{t('error.500.error_id')}</span>
          <Button variant="ghost" size="sm" onClick={copyErrorId}>
            <Copy className="h-4 w-4" />
          </Button>
        </div>
        <code className="text-xs bg-muted p-2 rounded block">
          {errorId}
        </code>
        <p className="text-xs text-muted-foreground">
          {t('error.500.timestamp')}: {timestamp}
        </p>
      </CardContent>
    </Card>
    
    {/* 操作按钮 */}
    <div className="flex gap-4 justify-center">
      <Button onClick={reset}>
        <RefreshCw className="mr-2 h-4 w-4" />
        {t('error.500.btn_refresh')}
      </Button>
      <Button variant="outline" onClick={() => router.push('/')}>
        <Home className="mr-2 h-4 w-4" />
        {t('error.500.btn_home')}
      </Button>
    </div>
    
    {/* 支持信息 */}
    <p className="text-sm text-muted-foreground">
      {t('error.500.support_text')}
    </p>
  </div>
</div>
```

## 后续优化建议

1. **错误追踪**：集成 Sentry 或类似服务
2. **用户反馈**：添加错误报告表单
3. **A/B 测试**：测试不同的文案和布局
4. **分析统计**：追踪错误页面访问情况
5. **个性化**：根据用户历史提供个性化建议

## 总结

本设计方案为 AI Higress 项目提供了完整的 404 和 500 错误页面设计，包括：

- ✅ 符合项目"水墨雅韵"设计理念
- ✅ 使用现有的 shadcn/ui 组件库
- ✅ 完整的中英文国际化支持
- ✅ 响应式设计，适配多种设备
- ✅ 用户友好的交互体验
- ✅ 清晰的实现指导

设计遵循 Next.js 最佳实践，易于实现和维护。