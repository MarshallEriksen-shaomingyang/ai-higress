/**
 * NeonCard 使用示例
 * 
 * 展示如何使用 NeonCard 组件及其精致样式
 */

import {
  NeonCard,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "./neon-card";

// ============================================
// 示例 1: 基础霓虹卡片（自动主题色）
// ============================================
export function BasicNeonCardExample() {
  return (
    <NeonCard>
      <CardHeader>
        <CardTitle className="text-sm text-white/70">
          当前请求数量
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="neon-card-number text-5xl">249</div>
        <p className="text-xs text-white/60 mt-2">
          较昨日 +12.5%
        </p>
      </CardContent>
    </NeonCard>
  );
}

// ============================================
// 示例 2: 带圣诞装饰的卡片（参考图风格）
// ============================================
export function ChristmasNeonCardExample() {
  return (
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
        {/* 使用香槟金色的精致数字 */}
        <div className="neon-card-number text-6xl font-light">249</div>
        <p className="text-xs text-white/60 mt-2">
          较昨日 +12.5%
        </p>
      </CardContent>
    </NeonCard>
  );
}

// ============================================
// 示例 3: 金属质感数字
// ============================================
export function MetallicNeonCardExample() {
  return (
    <NeonCard neonColor="blue" neonIntensity={3}>
      <CardHeader>
        <CardTitle className="text-sm text-white/70">
          成功率
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* 金属渐变质感 */}
        <div className="neon-card-metallic text-6xl">87.1%</div>
        <p className="text-xs text-white/60 mt-2">
          过去 24 小时
        </p>
      </CardContent>
    </NeonCard>
  );
}

// ============================================
// 示例 4: 超细字体变体
// ============================================
export function ThinFontNeonCardExample() {
  return (
    <NeonCard neonColor="green" neonIntensity={2}>
      <CardHeader>
        <CardTitle className="text-sm text-white/70">
          活跃模型数
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* 超细字体，更精致 */}
        <div className="neon-card-number-thin text-7xl">8</div>
        <p className="text-xs text-white/60 mt-2">
          当前可用
        </p>
      </CardContent>
    </NeonCard>
  );
}

// ============================================
// 示例 5: 仪表盘网格布局（参考图风格）
// ============================================
export function DashboardNeonGridExample() {
  return (
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
          <p className="text-xs text-white/60 mt-2">
            较昨日 +12.5%
          </p>
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
          <p className="text-xs text-white/60 mt-2">
            当前可用
          </p>
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
          <p className="text-xs text-white/60 mt-2">
            过去 24 小时
          </p>
        </CardContent>
      </NeonCard>
    </div>
  );
}

// ============================================
// 示例 6: 不同强度对比
// ============================================
export function IntensityComparisonExample() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <NeonCard neonColor="purple" neonIntensity={1}>
        <CardContent className="pt-6">
          <div className="text-center">
            <div className="neon-card-number text-4xl">低强度</div>
            <p className="text-xs text-white/60 mt-2">intensity = 1</p>
          </div>
        </CardContent>
      </NeonCard>

      <NeonCard neonColor="purple" neonIntensity={2}>
        <CardContent className="pt-6">
          <div className="text-center">
            <div className="neon-card-number text-4xl">中强度</div>
            <p className="text-xs text-white/60 mt-2">intensity = 2</p>
          </div>
        </CardContent>
      </NeonCard>

      <NeonCard neonColor="purple" neonIntensity={3}>
        <CardContent className="pt-6">
          <div className="text-center">
            <div className="neon-card-number text-4xl">高强度</div>
            <p className="text-xs text-white/60 mt-2">intensity = 3</p>
          </div>
        </CardContent>
      </NeonCard>
    </div>
  );
}

// ============================================
// 示例 7: 禁用霓虹效果
// ============================================
export function DisabledNeonExample() {
  return (
    <NeonCard enableNeon={false}>
      <CardHeader>
        <CardTitle className="text-sm text-white/70">
          纯玻璃拟态
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="neon-card-number text-5xl">1,234</div>
        <p className="text-xs text-white/60 mt-2">
          无霓虹灯效果
        </p>
      </CardContent>
    </NeonCard>
  );
}
