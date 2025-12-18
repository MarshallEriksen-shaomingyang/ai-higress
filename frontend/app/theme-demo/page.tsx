import { AdaptiveCard } from "@/components/ui/adaptive-card";
import { StatCard, MetricCard, IntensityCard } from "@/components/cards";
import { ArrowLeft } from "lucide-react";
import { ThemeSwitcher } from "@/components/theme-switcher";
import Link from "next/link";

export default function ThemeDemoPage() {
  return (
    <div
      className="min-h-screen relative"
      style={{
        backgroundImage: "url(/theme/chrismas/background.svg)",
        backgroundSize: "cover",
        backgroundPosition: "center",
        backgroundAttachment: "fixed",
        backgroundRepeat: "no-repeat",
      }}
    >
      {/* 背景遮罩层 - 让背景变亮（上下均匀） */}
      <div 
        className="fixed inset-0 pointer-events-none"
        style={{
          background: "linear-gradient(180deg, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0.12) 50%, rgba(255, 255, 255, 0.18) 100%)",
          zIndex: 0,
        }}
      />

      {/* 固定顶部 Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/80 backdrop-blur-sm">
        <div className="container flex h-16 items-center justify-between px-4">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              返回首页
            </Link>
            <div className="h-6 w-px bg-border" />
            <h1 className="text-lg font-semibold">霓虹灯玻璃拟态卡片演示</h1>
          </div>
          <ThemeSwitcher />
        </div>
      </header>

      {/* 主内容区 */}
      <div className="container px-4 py-8 relative">
        <div className="max-w-7xl mx-auto space-y-8 relative">
          {/* 页面说明 */}
          <div className="space-y-2 text-center">
            <h2 className="text-3xl font-bold">圣诞主题玻璃拟态卡片</h2>
            <p className="text-muted-foreground">
              透明背景 + 背景模糊 + 霓虹灯边框 + 圣诞装饰
            </p>
          </div>

          {/* 霓虹灯卡片展示 - 类似截图效果 */}
          <section className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <AdaptiveCard neonColor="red" neonIntensity={3}>
                <StatCard 
                  label="当前请求数量" 
                  value="249" 
                  subtitle="较昨日 +12%" 
                  size="lg"
                />
              </AdaptiveCard>

              <AdaptiveCard neonColor="green" neonIntensity={3}>
                <StatCard 
                  label="即时处理请求" 
                  value="8" 
                  subtitle="实时处理中" 
                  size="lg"
                />
              </AdaptiveCard>

              <AdaptiveCard neonColor="cyan" neonIntensity={3}>
                <StatCard 
                  label="成功的实率" 
                  value="87.1%" 
                  subtitle="过去 24 小时" 
                  size="lg"
                />
              </AdaptiveCard>
            </div>
          </section>

          {/* 更多示例 */}
          <section className="space-y-4">
            <h3 className="text-2xl font-semibold text-center">不同颜色霓虹灯</h3>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <AdaptiveCard neonColor="red">
                <MetricCard label="API 调用" value="17,065" />
              </AdaptiveCard>

              <AdaptiveCard neonColor="blue">
                <MetricCard label="响应时间" value="1,729ms" />
              </AdaptiveCard>

              <AdaptiveCard neonColor="green">
                <MetricCard label="成本统计" value="$73,509" />
              </AdaptiveCard>

              <AdaptiveCard neonColor="purple">
                <MetricCard label="活跃用户" value="2,350" />
              </AdaptiveCard>
            </div>
          </section>

          {/* 霓虹灯强度对比 */}
          <section className="space-y-4">
            <h3 className="text-2xl font-semibold text-center">霓虹灯强度对比</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <AdaptiveCard neonColor="orange" neonIntensity={1}>
                <IntensityCard level={1} />
              </AdaptiveCard>

              <AdaptiveCard neonColor="orange" neonIntensity={2}>
                <IntensityCard level={2} />
              </AdaptiveCard>

              <AdaptiveCard neonColor="orange" neonIntensity={3}>
                <IntensityCard level={3} />
              </AdaptiveCard>
            </div>
          </section>

          {/* 提示信息 */}
          <div className="mt-12 p-6 rounded-lg border border-dashed border-white/30 bg-black/20 backdrop-blur-sm">
            <h3 className="text-lg font-semibold mb-2 text-white">💡 效果说明</h3>
            <ul className="space-y-1 text-sm text-white/80">
              <li>• 背景：圣诞雪景图片（7MB SVG）</li>
              <li>• 卡片：玻璃拟态效果（半透明 + 背景模糊）</li>
              <li>• 边框：上下霓虹灯发光效果</li>
              <li>• 装饰：右上角圣诞彩灯和雪花</li>
              <li>• 颜色：支持 red, green, blue, purple, orange, cyan</li>
              <li>• 强度：支持 1-3 档调节</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
