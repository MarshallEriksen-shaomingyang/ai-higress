# ThemeCard 组件使用指南

## 概述

`ThemeCard` 是实现 **“新中式数字水墨 (Digital Ink)”** 设计哲学的核心组件。它能够根据当前主题自动切换样式：

- **默认/水墨主题**：使用纯白背景 (`#FFFFFF`)，配合弥散阴影，营造悬浮感（见 `ui-prompt.md`）。
- **特殊主题** (christmas/ocean/spring)：自动应用琉璃/磨砂玻璃（glassmorphism）效果。

## 基本用法

### 1. 自动主题感知（推荐）

```tsx
import {
  ThemeCard,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/theme-card";

export function MyComponent() {
  return (
    <ThemeCard>
      <CardHeader>
        <CardTitle>标题</CardTitle>
      </CardHeader>
      <CardContent>
        <p>内容会根据主题自动调整样式</p>
      </CardContent>
    </ThemeCard>
  );
}
```

### 2. 强制使用特定变体

```tsx
// 始终使用玻璃拟态效果
<ThemeCard variant="glass">
  <CardContent>玻璃效果</CardContent>
</ThemeCard>

// 始终使用默认样式
<ThemeCard variant="default">
  <CardContent>默认样式</CardContent>
</ThemeCard>

// 始终使用实心样式
<ThemeCard variant="solid">
  <CardContent>实心样式</CardContent>
</ThemeCard>
```

### 3. 禁用主题感知

```tsx
// 不随主题变化，始终使用默认样式
<ThemeCard themeAware={false}>
  <CardContent>静态样式</CardContent>
</ThemeCard>
```

## API 参考

### ThemeCard Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `variant` | `"default" \| "glass" \| "solid"` | `undefined` | 卡片变体，不指定则自动根据主题选择 |
| `themeAware` | `boolean` | `true` | 是否启用主题自动切换 |
| `className` | `string` | - | 自定义 CSS 类名 |
| ...其他 | - | - | 继承自标准 `<div>` 的所有属性 |

### 子组件

`ThemeCard` 导出了所有标准 Card 子组件：

- `CardHeader` - 卡片头部
- `CardTitle` - 卡片标题
- `CardDescription` - 卡片描述
- `CardContent` - 卡片内容
- `CardFooter` - 卡片底部
- `CardAction` - 卡片操作区

用法与 shadcn/ui 的 Card 组件完全一致。

## 主题样式对照表

| 主题 | 自动变体 | 视觉效果 |
|------|----------|----------|
| `light` | `default` | 白色背景，细边框，轻阴影 |
| `dark` | `default` | 深色背景，细边框，轻阴影 |
| `christmas` | `glass` | 玻璃拟态，红色调阴影 |
| `ocean` | `glass` | 玻璃拟态，蓝色调阴影 |
| `spring` | `glass` | 玻璃拟态，绿色调阴影 |

## 实际应用场景

### 仪表盘统计卡片

```tsx
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
  <ThemeCard>
    <CardHeader>
      <CardTitle className="text-sm text-muted-foreground">
        总请求数
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-3xl font-bold">12,345</div>
      <p className="text-xs text-muted-foreground mt-1">
        较昨日 +12.5%
      </p>
    </CardContent>
  </ThemeCard>

  <ThemeCard>
    <CardHeader>
      <CardTitle className="text-sm text-muted-foreground">
        成功率
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-3xl font-bold">98.5%</div>
    </CardContent>
  </ThemeCard>

  <ThemeCard>
    <CardHeader>
      <CardTitle className="text-sm text-muted-foreground">
        平均延迟
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-3xl font-bold">245ms</div>
    </CardContent>
  </ThemeCard>
</div>
```

### 带背景装饰的卡片

```tsx
<ThemeCard className="relative overflow-hidden">
  <CardHeader>
    <CardTitle>API 使用统计</CardTitle>
  </CardHeader>
  <CardContent>
    {/* 内容 */}
  </CardContent>
  
  {/* 装饰性渐变 */}
  <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-primary/10 to-transparent rounded-full blur-2xl -z-10" />
</ThemeCard>
```

## 自定义样式

### 覆盖默认样式

```tsx
<ThemeCard className="border-2 border-primary shadow-xl">
  <CardContent>自定义边框和阴影</CardContent>
</ThemeCard>
```

### 添加动画效果

```tsx
<ThemeCard className="hover:scale-105 transition-transform duration-300">
  <CardContent>鼠标悬停时放大</CardContent>
</ThemeCard>
```

## 性能考虑

- `ThemeCard` 使用 `useTheme` hook，是客户端组件
- 首次渲染时会有短暂的 `mounted` 检查，避免 SSR 不匹配
- 主题切换时使用 CSS 变量，性能开销极小
- 玻璃拟态效果使用 `backdrop-filter`，在现代浏览器中性能良好

## 浏览器兼容性

- `backdrop-filter` 需要现代浏览器支持
- Safari 需要 `-webkit-backdrop-filter` 前缀（已包含）
- 不支持的浏览器会降级为半透明背景

## 迁移指南

### 从标准 Card 迁移

```tsx
// 之前
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

<Card>
  <CardHeader>
    <CardTitle>标题</CardTitle>
  </CardHeader>
  <CardContent>内容</CardContent>
</Card>

// 之后（只需改一个导入）
import { ThemeCard, CardHeader, CardTitle, CardContent } from "@/components/ui/theme-card";

<ThemeCard>
  <CardHeader>
    <CardTitle>标题</CardTitle>
  </CardHeader>
  <CardContent>内容</CardContent>
</ThemeCard>
```

## 最佳实践

1. **仪表盘页面**：使用 `ThemeCard` 让统计卡片在节日主题下更有氛围
2. **表单页面**：使用 `themeAware={false}` 保持表单的一致性
3. **营销页面**：使用 `variant="glass"` 创造视觉冲击力
4. **数据展示**：让 `ThemeCard` 自动适配，提升用户体验

## 相关文件

- 组件实现：`frontend/components/ui/theme-card.tsx`
- 使用示例：`frontend/components/ui/theme-card.example.tsx`
- 主题配置：`frontend/app/globals.css`
- 主题切换器：`frontend/components/theme-switcher.tsx`
