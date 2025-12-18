# NeonCard 组件使用指南

## 概述

`NeonCard` 是一个带有霓虹灯效果的玻璃拟态卡片组件，专为圣诞等节日主题设计。它具有以下特性：

- **冰霜纹理** - 雪花/冰晶质感，而非纯粹的模糊
- **边缘流光** - 顶部和底部的霓虹灯发光线条（中间亮两边淡）
- **精致字体** - 香槟金色、细字重、金属质感
- **圣诞装饰** - 可选的右上角透明装饰图案
- **主题自适应** - 根据主题自动选择霓虹灯颜色

## 基本用法

### 1. 自动主题色霓虹灯（推荐）

```tsx
import {
  NeonCard,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/neon-card";

export function MyComponent() {
  return (
    <NeonCard>
      <CardHeader>
        <CardTitle className="text-sm text-white/70">
          当前请求数量
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* 使用香槟金色的精致数字 */}
        <div className="neon-card-number text-6xl">249</div>
        <p className="text-xs text-white/60 mt-2">
          较昨日 +12.5%
        </p>
      </CardContent>
    </NeonCard>
  );
}
```

### 2. 指定霓虹灯颜色

```tsx
// 红色霓虹灯（圣诞主题）
<NeonCard neonColor="red">
  <CardContent>红色流光</CardContent>
</NeonCard>

// 绿色霓虹灯
<NeonCard neonColor="green">
  <CardContent>绿色流光</CardContent>
</NeonCard>

// 蓝色霓虹灯
<NeonCard neonColor="blue">
  <CardContent>蓝色流光</CardContent>
</NeonCard>
```

### 3. 带圣诞装饰的卡片（参考图风格）

```tsx
<NeonCard 
  neonColor="red" 
  neonIntensity={2}
  showChristmasDecor={true}
>
  <CardHeader>
    <CardTitle className="text-sm text-white/70">
      当前请求数量
    </CardTitle>
  </CardHeader>
  <CardContent>
    <div className="neon-card-number text-6xl">249</div>
    <p className="text-xs text-white/60 mt-2">较昨日 +12.5%</p>
  </CardContent>
</NeonCard>
```

## 精致字体样式

### 1. 香槟金色数字（推荐）

```tsx
<div className="neon-card-number text-6xl">249</div>
```

- 字重：300（细体）
- 颜色：#e0c38c（香槟金）
- 效果：淡淡的发光阴影

### 2. 超细字体变体

```tsx
<div className="neon-card-number-thin text-7xl">8</div>
```

- 字重：200（超细）
- 颜色：香槟金
- 效果：更强的发光，更精致

### 3. 金属质感文字

```tsx
<div className="neon-card-metallic text-6xl">87.1%</div>
```

- 渐变效果：从浅金到深金
- 使用 `background-clip: text` 实现金属质感
- 适合百分比、重要数据

## API 参考

### NeonCard Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `neonColor` | `"red" \| "green" \| "blue" \| "purple" \| "orange" \| "cyan" \| "auto"` | `"auto"` | 霓虹灯颜色，`auto` 根据主题自动选择 |
| `enableNeon` | `boolean` | `true` | 是否启用霓虹灯效果 |
| `neonIntensity` | `1 \| 2 \| 3` | `2` | 霓虹灯强度（1=低，2=中，3=高） |
| `showChristmasDecor` | `boolean` | `false` | 是否显示右上角圣诞装饰 |
| `className` | `string` | - | 自定义 CSS 类名 |
| ...其他 | - | - | 继承自标准 `<div>` 的所有属性 |

### 主题自动颜色映射

| 主题 | 自动霓虹灯颜色 |
|------|---------------|
| `christmas` | `red` |
| `ocean` | `cyan` |
| `spring` | `green` |
| `dark` | `purple` |
| 其他 | `blue` |

## 实际应用场景

### 仪表盘网格布局（参考图风格）

```tsx
<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
  {/* 卡片 1 - 红色霓虹 + 圣诞装饰 */}
  <NeonCard 
    neonColor="red" 
    neonIntensity={2}
    showChristmasDecor={true}
  >
    <CardHeader>
      <CardTitle className="text-sm text-white/70">
        当前请求数量
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="neon-card-number text-6xl">249</div>
      <p className="text-xs text-white/60 mt-2">较昨日 +12.5%</p>
    </CardContent>
  </NeonCard>

  {/* 卡片 2 - 绿色霓虹 + 圣诞装饰 */}
  <NeonCard 
    neonColor="green" 
    neonIntensity={2}
    showChristmasDecor={true}
  >
    <CardHeader>
      <CardTitle className="text-sm text-white/70">
        网关活跃模型
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="neon-card-number-thin text-7xl">8</div>
      <p className="text-xs text-white/60 mt-2">当前可用</p>
    </CardContent>
  </NeonCard>

  {/* 卡片 3 - 蓝色霓虹 + 圣诞装饰 */}
  <NeonCard 
    neonColor="cyan" 
    neonIntensity={2}
    showChristmasDecor={true}
  >
    <CardHeader>
      <CardTitle className="text-sm text-white/70">
        网关成功率
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="neon-card-metallic text-6xl">87.1%</div>
      <p className="text-xs text-white/60 mt-2">过去 24 小时</p>
    </CardContent>
  </NeonCard>
</div>
```

### 不同强度对比

```tsx
<div className="grid grid-cols-3 gap-6">
  <NeonCard neonColor="purple" neonIntensity={1}>
    <CardContent className="pt-6">
      <div className="neon-card-number text-4xl">低强度</div>
    </CardContent>
  </NeonCard>

  <NeonCard neonColor="purple" neonIntensity={2}>
    <CardContent className="pt-6">
      <div className="neon-card-number text-4xl">中强度</div>
    </CardContent>
  </NeonCard>

  <NeonCard neonColor="purple" neonIntensity={3}>
    <CardContent className="pt-6">
      <div className="neon-card-number text-4xl">高强度</div>
    </CardContent>
  </NeonCard>
</div>
```

## 设计细节说明

### 1. 冰霜纹理

卡片背景不是纯粹的模糊，而是叠加了多层雪花/冰晶纹理：

- 使用 `radial-gradient` 创建多个小圆点模拟雪花
- 四个角落有额外的冰霜纹理增强
- `mix-blend-mode: overlay` 让纹理与背景融合

### 2. 边缘流光

顶部和底部的霓虹灯线条：

- 宽度只占卡片的 60%（中间亮两边淡）
- 使用 `filter: blur()` 创造发光效果
- `box-shadow` 叠加多层阴影增强光晕

### 3. 精致字体

三种字体样式类：

- `.neon-card-number` - 标准香槟金（font-weight: 300）
- `.neon-card-number-thin` - 超细香槟金（font-weight: 200）
- `.neon-card-metallic` - 金属渐变质感

### 4. 圣诞装饰

右上角的装饰图案：

- 使用透明背景 PNG（`/theme/chrismas/card.svg`）
- 轻微虚化（`blur(0.3px)`）模拟景深
- 阴影效果让装饰"浮"在卡片前面

## 自定义样式

### 调整玻璃拟态强度

```tsx
<NeonCard 
  style={{
    backdropFilter: "blur(20px) saturate(180%)",
    background: "rgba(255, 255, 255, 0.15)",
  }}
>
  <CardContent>更强的模糊和饱和度</CardContent>
</NeonCard>
```

### 自定义霓虹灯颜色

虽然组件提供了预设颜色，但你可以通过 CSS 变量覆盖：

```tsx
<NeonCard 
  className="[--neon-color:rgb(255,100,200)]"
  style={{
    boxShadow: "0 8px 32px 0 var(--neon-color)",
  }}
>
  <CardContent>自定义粉色霓虹</CardContent>
</NeonCard>
```

## 性能考虑

- `backdrop-filter` 在现代浏览器中性能良好
- 多层纹理使用 CSS 渐变，无需额外图片资源
- 霓虹灯效果使用 CSS `filter` 和 `box-shadow`，GPU 加速
- 圣诞装饰图片使用 `loading="lazy"` 延迟加载

## 浏览器兼容性

- `backdrop-filter` 需要现代浏览器支持
- Safari 需要 `-webkit-backdrop-filter` 前缀（已包含）
- 不支持的浏览器会降级为半透明背景
- 建议在 Chrome 88+, Safari 14+, Firefox 103+ 中使用

## 与 ThemeCard 的区别

| 特性 | ThemeCard | NeonCard |
|------|-----------|----------|
| 用途 | 通用主题感知卡片 | 节日/特殊场景卡片 |
| 霓虹灯效果 | ❌ | ✅ |
| 冰霜纹理 | ❌ | ✅ |
| 精致字体样式 | ❌ | ✅ |
| 圣诞装饰 | ❌ | ✅ |
| 主题自适应 | ✅ | ✅ |
| 性能开销 | 低 | 中 |

**建议**：
- 日常页面使用 `ThemeCard`
- 节日主题、营销页面、特殊仪表盘使用 `NeonCard`

## 最佳实践

1. **数字展示**：使用 `.neon-card-number` 或 `.neon-card-number-thin` 类
2. **百分比/重要数据**：使用 `.neon-card-metallic` 增加视觉重量
3. **圣诞主题**：启用 `showChristmasDecor={true}` 并使用红色/绿色霓虹灯
4. **强度选择**：
   - 小卡片（< 200px）：`neonIntensity={1}`
   - 中等卡片（200-400px）：`neonIntensity={2}`
   - 大卡片（> 400px）：`neonIntensity={3}`
5. **文字颜色**：使用 `text-white/70` 作为标题，`text-white/60` 作为描述

## 相关文件

- 组件实现：`frontend/components/ui/neon-card.tsx`
- 使用示例：`frontend/components/ui/neon-card.example.tsx`
- 字体样式：`frontend/app/globals.css`（`.neon-card-*` 类）
- 主题配置：`frontend/app/globals.css`（主题变量）
- 圣诞装饰图：`public/theme/chrismas/card.svg`

## 故障排除

### 圣诞装饰不显示

1. 确保图片路径正确：`/theme/chrismas/card.svg`
2. 确保图片是透明背景 PNG 或 SVG
3. 检查浏览器控制台是否有加载错误

### 霓虹灯效果不明显

1. 增加 `neonIntensity` 到 3
2. 确保背景足够暗（深色背景效果更好）
3. 检查浏览器是否支持 `backdrop-filter`

### 字体样式不生效

1. 确保导入了 `globals.css`
2. 检查是否有其他样式覆盖了 `.neon-card-*` 类
3. 使用浏览器开发者工具检查样式是否正确应用

## 示例代码

完整示例请参考：`frontend/components/ui/neon-card.example.tsx`
