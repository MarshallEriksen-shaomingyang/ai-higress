import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Suspense } from "react";
import { ThemeProvider } from "@/components/theme-provider";
import { I18nProvider } from "@/lib/i18n-context";
import { AuthProvider } from "@/components/providers/auth-provider";
import { AuthDialog } from "@/components/auth/auth-dialog";
import { SWRProvider } from "@/lib/swr";
import { Toaster } from "@/components/ui/sonner";
import { PWAInstallPrompt } from "@/components/pwa-install-prompt";
import { PWARegister } from "@/components/pwa-register";
import { PerformanceMonitor } from "@/components/performance-monitor";
import { generateJsonLd } from "@/lib/seo";
import { ThemeBackground } from "@/components/theme-background";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_BASE_URL || 'https://ai-higress.example.com'),
  title: {
    default: "AI Higress Gateway - 智能 AI 路由网关",
    template: "%s | AI Higress Gateway",
  },
  description: "AI Higress - 智能 AI 路由网关，统一管理多个 AI 提供商，提供高效的模型路由和 API 管理服务",
  keywords: ["AI Gateway", "AI 网关", "API Gateway", "智能路由", "OpenAI", "Claude", "Gemini"],
  authors: [{ name: "AI Higress Team" }],
  creator: "AI Higress",
  publisher: "AI Higress",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "AI HIGRESS GATEWAY",
  },
  openGraph: {
    type: "website",
    locale: "zh_CN",
    url: "/",
    title: "AI Higress Gateway - 智能 AI 路由网关",
    description: "统一管理多个 AI 提供商，提供高效的模型路由和 API 管理服务",
    siteName: "AI Higress Gateway",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "AI Higress Gateway",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Higress Gateway - 智能 AI 路由网关",
    description: "统一管理多个 AI 提供商，提供高效的模型路由和 API 管理服务",
    images: ["/og-image.png"],
    creator: "@ai_higress",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION,
    yandex: process.env.NEXT_PUBLIC_YANDEX_VERIFICATION,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // 生成结构化数据
  const organizationSchema = generateJsonLd('Organization', {});
  const websiteSchema = generateJsonLd('WebSite', {});

  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <meta name="apple-mobile-web-app-title" content="AI HIGRESS GATEWAY" />
        <link rel="icon" href="/favicon.ico" />
        <link rel="shortcut icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" sizes="180x180" href="/apple-icon.png" />
        <link rel="manifest" href="/manifest.json" />
        
        {/* 结构化数据 - 组织信息 */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }}
        />
        {/* 结构化数据 - 网站信息 */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }}
        />
      </head>
      <body className="antialiased">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          themes={['light', 'dark', 'christmas', 'ocean', 'spring']}
          disableTransitionOnChange
        >
          <ThemeBackground />
          <main className="relative z-10">
            <I18nProvider>
              <SWRProvider>
                <AuthProvider>
                  {children}
                  {/* 全局登录对话框 - 由 Zustand 状态控制显示 */}
                  <Suspense fallback={null}>
                    <AuthDialog />
                  </Suspense>
                  {/* PWA 注册 Service Worker */}
                  <PWARegister />
                  {/* PWA 安装提示 */}
                  <PWAInstallPrompt />
                  {/* 性能监控 */}
                  <PerformanceMonitor />
                </AuthProvider>
              </SWRProvider>
            </I18nProvider>
            <Toaster richColors closeButton />
          </main>
        </ThemeProvider>
      </body>
    </html>
  );
}
