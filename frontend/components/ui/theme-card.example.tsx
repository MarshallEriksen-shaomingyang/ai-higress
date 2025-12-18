/**
 * ThemeCard 使用示例
 * 
 * 这个文件展示了如何使用 ThemeCard 组件
 */

import {
  ThemeCard,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "./theme-card";
import { Button } from "./button";

// ============================================
// 示例 1: 自动主题感知（推荐）
// ============================================
export function AutoThemeCardExample() {
  return (
    <ThemeCard>
      <CardHeader>
        <CardTitle>自动主题卡片</CardTitle>
        <CardDescription>
          在 light/dark 主题下显示默认样式，
          在 christmas/ocean/spring 主题下自动切换为玻璃拟态效果
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p>这是卡片内容</p>
      </CardContent>
    </ThemeCard>
  );
}

// ============================================
// 示例 2: 强制使用玻璃拟态效果
// ============================================
export function GlassCardExample() {
  return (
    <ThemeCard variant="glass">
      <CardHeader>
        <CardTitle>玻璃拟态卡片</CardTitle>
        <CardDescription>
          无论什么主题，始终使用玻璃拟态效果
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p>适合需要特殊视觉效果的场景</p>
      </CardContent>
    </ThemeCard>
  );
}

// ============================================
// 示例 3: 禁用主题感知
// ============================================
export function StaticCardExample() {
  return (
    <ThemeCard themeAware={false}>
      <CardHeader>
        <CardTitle>静态卡片</CardTitle>
        <CardDescription>
          始终使用默认样式，不随主题变化
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p>适合需要保持一致外观的场景</p>
      </CardContent>
    </ThemeCard>
  );
}

// ============================================
// 示例 4: 仪表盘统计卡片（类似截图中的样式）
// ============================================
export function DashboardStatCard() {
  return (
    <ThemeCard className="relative overflow-hidden">
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">
          当前请求数量
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-4xl font-bold">249</div>
        <p className="text-xs text-muted-foreground mt-2">
          较昨日 +12.5%
        </p>
      </CardContent>
      
      {/* 装饰性渐变背景 */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-primary/10 to-transparent rounded-full blur-2xl -z-10" />
    </ThemeCard>
  );
}

// ============================================
// 示例 5: 带操作按钮的卡片
// ============================================
export function CardWithActionsExample() {
  return (
    <ThemeCard>
      <CardHeader>
        <CardTitle>API 密钥管理</CardTitle>
        <CardDescription>
          管理您的 API 访问密钥
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm">密钥 1</span>
            <span className="text-xs text-muted-foreground">已激活</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">密钥 2</span>
            <span className="text-xs text-muted-foreground">已禁用</span>
          </div>
        </div>
      </CardContent>
      <CardFooter className="justify-end gap-2">
        <Button variant="outline" size="sm">取消</Button>
        <Button size="sm">保存</Button>
      </CardFooter>
    </ThemeCard>
  );
}

// ============================================
// 示例 6: 网格布局的仪表盘
// ============================================
export function DashboardGridExample() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ThemeCard>
        <CardHeader>
          <CardTitle className="text-sm text-muted-foreground">
            总请求数
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-3xl font-bold">12,345</div>
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
  );
}
