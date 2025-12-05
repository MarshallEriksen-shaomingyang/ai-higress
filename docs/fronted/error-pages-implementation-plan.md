# AI Higress 错误页面实施计划

## 实施概述

本文档提供了 404 和 500 错误页面的详细实施步骤，包括文件创建、代码实现和测试验证。

## 前置条件

- ✅ Next.js 16.0 已安装
- ✅ shadcn/ui 组件库已配置
- ✅ Tailwind CSS 4.0 已配置
- ✅ 国际化系统已就绪

## 实施步骤

### 第一步：更新国际化文案

**文件**: `frontend/lib/i18n-context.tsx`

在 `translations` 对象中添加错误页面相关文案：

```typescript
// 在 translations.en 中添加
"error.404.title": "404",
"error.404.heading": "Page Not Found",
"error.404.description": "Sorry, we couldn't find the page you're looking for. The page may have been moved or deleted.",
"error.404.suggestion": "Here are some helpful links instead:",
"error.404.btn_home": "Back to Home",
"error.404.btn_back": "Go Back",
"error.404.link_dashboard": "Dashboard",
"error.404.link_dashboard_desc": "View your dashboard",
"error.404.link_providers": "Providers",
"error.404.link_providers_desc": "Manage AI providers",
"error.404.link_docs": "Documentation",
"error.404.link_docs_desc": "Read the docs",
"error.404.link_support": "Support",
"error.404.link_support_desc": "Get help",

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

// 在 translations.zh 中添加
"error.404.title": "404",
"error.404.heading": "页面未找到",
"error.404.description": "抱歉，我们找不到您要访问的页面。该页面可能已被移动或删除。",
"error.404.suggestion": "以下是一些有用的链接：",
"error.404.btn_home": "返回首页",
"error.404.btn_back": "返回上一页",
"error.404.link_dashboard": "仪表盘",
"error.404.link_dashboard_desc": "查看仪表盘",
"error.404.link_providers": "提供商",
"error.404.link_providers_desc": "管理 AI 提供商",
"error.404.link_docs": "文档",
"error.404.link_docs_desc": "阅读文档",
"error.404.link_support": "支持",
"error.404.link_support_desc": "获取帮助",

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
```

### 第二步：创建 404 页面组件

**文件**: `frontend/components/error/not-found-content.tsx`

```typescript
"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import {
  Home,
  ArrowLeft,
  LayoutDashboard,
  Plug,
  BookOpen,
  MessageCircle,
} from "lucide-react";
import Link from "next/link";

export function NotFoundContent() {
  const router = useRouter();
  const { t } = useI18n();

  const quickLinks = [
    {
      href: "/dashboard/overview",
      icon: LayoutDashboard,
      title: t("error.404.link_dashboard"),
      description: t("error.404.link_dashboard_desc"),
    },
    {
      href: "/dashboard/providers",
      icon: Plug,
      title: t("error.404.link_providers"),
      description: t("error.404.link_providers_desc"),
    },
    {
      href: "/docs",
      icon: BookOpen,
      title: t("error.404.link_docs"),
      description: t("error.404.link_docs_desc"),
    },
    {
      href: "/support",
      icon: MessageCircle,
      title: t("error.404.link_support"),
      description: t("error.404.link_support_desc"),
    },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center p-4 animate-in fade-in duration-500">
      <div className="max-w-2xl w-full text-center space-y-8">
        {/* 404 数字 */}
        <h1
          className="text-7xl md:text-8xl lg:text-9xl font-bold bg-gradient-to-r from-primary to-primary/50 bg-clip-text text-transparent animate-in zoom-in duration-700"
          aria-label={t("error.404.title")}
        >
          404
        </h1>

        {/* 标题和描述 */}
        <div className="space-y-4">
          <h2 className="text-2xl md:text-3xl font-semibold">
            {t("error.404.heading")}
          </h2>
          <p className="text-muted-foreground text-base md:text-lg max-w-md mx-auto">
            {t("error.404.description")}
          </p>
        </div>

        {/* 操作按钮 */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button onClick={() => router.push("/")} size="lg">
            <Home className="mr-2 h-4 w-4" />
            {t("error.404.btn_home")}
          </Button>
          <Button
            variant="outline"
            onClick={() => router.back()}
            size="lg"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t("error.404.btn_back")}
          </Button>
        </div>

        {/* 快捷链接 */}
        <div className="pt-8">
          <p className="text-sm text-muted-foreground mb-6">
            {t("error.404.suggestion")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {quickLinks.map((link) => (
              <Link key={link.href} href={link.href}>
                <Card className="hover:shadow-lg transition-all duration-300 hover:-translate-y-1 cursor-pointer h-full">
                  <CardContent className="p-6 flex flex-col items-center text-center space-y-2">
                    <link.icon className="h-8 w-8 text-primary" />
                    <h3 className="font-semibold">{link.title}</h3>
                    <p className="text-sm text-muted-foreground">
                      {link.description}
                    </p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
```

### 第三步：创建 404 页面

**文件**: `frontend/app/not-found.tsx`

```typescript
import { NotFoundContent } from "@/components/error/not-found-content";

export default function NotFound() {
  return <NotFoundContent />;
}
```

### 第四步：创建 500 错误页面组件

**文件**: `frontend/components/error/error-content.tsx`

```typescript
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useI18n } from "@/lib/i18n-context";
import { AlertTriangle, RefreshCw, Home, Copy } from "lucide-react";
import { toast } from "sonner";

interface ErrorContentProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export function ErrorContent({ error, reset }: ErrorContentProps) {
  const router = useRouter();
  const { t } = useI18n();
  const [errorId, setErrorId] = useState<string>("");
  const [timestamp, setTimestamp] = useState<string>("");

  useEffect(() => {
    // 生成错误 ID
    const id = error.digest || `ERR-${Date.now()}-${Math.random().toString(36).substr(2, 9).toUpperCase()}`;
    setErrorId(id);

    // 生成时间戳
    const now = new Date();
    setTimestamp(now.toLocaleString());

    // 可选：发送错误到监控服务
    console.error("Error:", error);
  }, [error]);

  const copyErrorId = async () => {
    try {
      await navigator.clipboard.writeText(errorId);
      toast.success(t("error.500.copied"));
    } catch (err) {
      toast.error("Failed to copy");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 animate-in fade-in duration-500">
      <div className="max-w-xl w-full text-center space-y-8">
        {/* 警告图标 */}
        <div className="flex justify-center">
          <AlertTriangle className="h-20 w-20 md:h-24 md:w-24 lg:h-32 lg:w-32 text-destructive animate-pulse" />
        </div>

        {/* 标题和描述 */}
        <div className="space-y-4">
          <h1 className="text-3xl md:text-4xl font-bold">
            {t("error.500.heading")}
          </h1>
          <p className="text-muted-foreground text-base md:text-lg max-w-md mx-auto">
            {t("error.500.description")}
          </p>
        </div>

        {/* 错误 ID 卡片 */}
        <Card>
          <CardContent className="p-6 space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">
                {t("error.500.error_id")}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={copyErrorId}
                aria-label={t("error.500.btn_copy")}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <code className="text-xs bg-muted p-3 rounded block font-mono break-all">
              {errorId}
            </code>
            <p className="text-xs text-muted-foreground">
              {t("error.500.timestamp")}: {timestamp}
            </p>
          </CardContent>
        </Card>

        {/* 操作按钮 */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button onClick={reset} size="lg">
            <RefreshCw className="mr-2 h-4 w-4" />
            {t("error.500.btn_refresh")}
          </Button>
          <Button
            variant="outline"
            onClick={() => router.push("/")}
            size="lg"
          >
            <Home className="mr-2 h-4 w-4" />
            {t("error.500.btn_home")}
          </Button>
        </div>

        {/* 支持信息 */}
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          {t("error.500.support_text")}
        </p>
      </div>
    </div>
  );
}
```

### 第五步：创建 500 错误页面

**文件**: `frontend/app/error.tsx`

```typescript
"use client";

import { ErrorContent } from "@/components/error/error-content";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <ErrorContent error={error} reset={reset} />;
}
```

### 第六步：创建全局错误页面（可选）

**文件**: `frontend/app/global-error.tsx`

```typescript
"use client";

import { ErrorContent } from "@/components/error/error-content";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html>
      <body>
        <ErrorContent error={error} reset={reset} />
      </body>
    </html>
  );
}
```

## 文件结构总览

```
frontend/
├── app/
│   ├── not-found.tsx              # 404 页面
│   ├── error.tsx                  # 错误边界页面
│   └── global-error.tsx           # 全局错误页面（可选）
├── components/
│   └── error/
│       ├── not-found-content.tsx  # 404 页面内容组件
│       └── error-content.tsx      # 错误页面内容组件
└── lib/
    └── i18n-context.tsx           # 更新国际化文案
```

## 测试计划

### 404 页面测试

#### 手动测试
1. **基本功能测试**
   ```bash
   # 启动开发服务器
   cd frontend
   npm run dev
   
   # 访问不存在的页面
   http://localhost:3000/non-existent-page
   ```

2. **按钮功能测试**
   - ✅ 点击"返回首页"按钮，应跳转到首页
   - ✅ 点击"返回上一页"按钮，应返回上一页
   - ✅ 点击快捷链接卡片，应跳转到对应页面

3. **响应式测试**
   - ✅ 桌面视图（≥1024px）：4 列网格布局
   - ✅ 平板视图（768-1023px）：2 列网格布局
   - ✅ 移动视图（<768px）：1 列布局，按钮垂直堆叠

4. **国际化测试**
   - ✅ 切换到英文，验证所有文案正确显示
   - ✅ 切换到中文，验证所有文案正确显示

5. **主题测试**
   - ✅ 亮色主题下显示正常
   - ✅ 暗色主题下显示正常

### 500 错误页面测试

#### 手动测试
1. **触发错误**
   创建测试页面 `frontend/app/test-error/page.tsx`：
   ```typescript
   "use client";
   
   export default function TestError() {
     throw new Error("Test error");
   }
   ```
   访问 `http://localhost:3000/test-error`

2. **功能测试**
   - ✅ 错误 ID 正确生成并显示
   - ✅ 时间戳正确显示
   - ✅ 点击复制按钮，错误 ID 复制到剪贴板
   - ✅ 显示成功 Toast 提示
   - ✅ 点击"刷新页面"按钮，页面重新加载
   - ✅ 点击"返回首页"按钮，跳转到首页

3. **响应式测试**
   - ✅ 桌面视图：图标大小 32px
   - ✅ 平板视图：图标大小 24px
   - ✅ 移动视图：图标大小 20px，按钮垂直堆叠

4. **国际化测试**
   - ✅ 切换语言，验证文案正确

5. **动画测试**
   - ✅ 警告图标脉动动画正常
   - ✅ 页面淡入动画正常

### 可访问性测试

1. **键盘导航**
   - ✅ Tab 键可以在所有可交互元素间导航
   - ✅ Enter/Space 键可以激活按钮
   - ✅ 焦点指示器清晰可见

2. **屏幕阅读器**
   - ✅ 使用 NVDA/JAWS 测试，所有内容可读
   - ✅ 图标有适当的 aria-label
   - ✅ 错误信息有 role="alert"

3. **颜色对比度**
   - ✅ 使用 Chrome DevTools 检查对比度
   - ✅ 所有文本对比度 ≥ 4.5:1

### 自动化测试（可选）

创建测试文件 `frontend/__tests__/error-pages.test.tsx`：

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { NotFoundContent } from "@/components/error/not-found-content";
import { ErrorContent } from "@/components/error/error-content";

describe("Error Pages", () => {
  describe("404 Page", () => {
    it("renders 404 heading", () => {
      render(<NotFoundContent />);
      expect(screen.getByText("404")).toBeInTheDocument();
    });

    it("renders quick links", () => {
      render(<NotFoundContent />);
      expect(screen.getByText(/Dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/Providers/i)).toBeInTheDocument();
    });
  });

  describe("500 Page", () => {
    const mockError = new Error("Test error");
    const mockReset = jest.fn();

    it("renders error heading", () => {
      render(<ErrorContent error={mockError} reset={mockReset} />);
      expect(screen.getByText(/Server Error/i)).toBeInTheDocument();
    });

    it("generates error ID", () => {
      render(<ErrorContent error={mockError} reset={mockReset} />);
      expect(screen.getByText(/ERR-/)).toBeInTheDocument();
    });

    it("calls reset when refresh button clicked", () => {
      render(<ErrorContent error={mockError} reset={mockReset} />);
      const refreshButton = screen.getByText(/Refresh/i);
      fireEvent.click(refreshButton);
      expect(mockReset).toHaveBeenCalled();
    });
  });
});
```

## 部署检查清单

### 部署前
- [ ] 所有文件已创建
- [ ] 国际化文案已添加
- [ ] 手动测试通过
- [ ] 响应式布局正常
- [ ] 主题切换正常
- [ ] 可访问性检查通过

### 部署后
- [ ] 生产环境 404 页面正常
- [ ] 生产环境错误处理正常
- [ ] 错误监控已配置（如 Sentry）
- [ ] 性能指标正常

## 性能优化

### 代码分割
错误页面组件会自动进行代码分割，无需额外配置。

### 图片优化
如果添加背景图或插图：
```typescript
import Image from "next/image";

<Image
  src="/error-illustration.svg"
  alt="Error illustration"
  width={400}
  height={300}
  priority
/>
```

### 字体优化
使用 Next.js 字体优化：
```typescript
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });
```

## 监控和分析

### 错误追踪
集成 Sentry（可选）：

```typescript
// frontend/app/error.tsx
"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";
import { ErrorContent } from "@/components/error/error-content";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // 发送错误到 Sentry
    Sentry.captureException(error);
  }, [error]);

  return <ErrorContent error={error} reset={reset} />;
}
```

### 分析统计
添加页面访问统计：

```typescript
// 在 ErrorContent 组件中
useEffect(() => {
  // 发送分析事件
  if (typeof window !== "undefined" && window.gtag) {
    window.gtag("event", "error_page_view", {
      error_id: errorId,
      error_message: error.message,
    });
  }
}, [errorId, error]);
```

## 常见问题

### Q1: 404 页面没有显示？
**A**: 确保文件名为 `not-found.tsx` 且位于 `app` 目录下。

### Q2: 错误页面样式不正确？
**A**: 检查 Tailwind CSS 配置，确保包含了所有必要的类。

### Q3: 国际化不工作？
**A**: 确保组件使用了 `"use client"` 指令，并正确导入 `useI18n`。

### Q4: 复制功能在某些浏览器不工作？
**A**: 添加降级方案：
```typescript
const copyErrorId = async () => {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(errorId);
    } else {
      // 降级方案
      const textArea = document.createElement("textarea");
      textArea.value = errorId;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand("copy");
      document.body.removeChild(textArea);
    }
    toast.success(t("error.500.copied"));
  } catch (err) {
    toast.error("Failed to copy");
  }
};
```

## 后续改进

1. **添加插图**：设计自定义的 404/500 插图
2. **动画增强**：添加更丰富的微交互动画
3. **个性化建议**：根据用户历史提供个性化的快捷链接
4. **错误报告**：添加用户反馈表单
5. **状态页面**：链接到系统状态页面

## 总结

按照本实施计划，您可以快速为 AI Higress 项目添加专业的错误页面。这些页面：

- ✅ 符合项目设计规范
- ✅ 提供良好的用户体验
- ✅ 支持国际化
- ✅ 响应式设计
- ✅ 可访问性友好
- ✅ 易于维护和扩展

如有任何问题，请参考设计文档或联系开发团队。