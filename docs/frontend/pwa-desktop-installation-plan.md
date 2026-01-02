# AI Higress PWA 桌面安装功能实现计划

## 概述

本文档详细说明如何为 AI Higress 前端实现 Progressive Web App (PWA) 功能，使其能够像 LobeChat 一样支持"安装到桌面"的功能。

## 当前项目状态分析

基于对项目的分析，AI Higress 前端使用 Next.js 16 + TypeScript + Tailwind CSS 构建，具备实现 PWA 的基础条件。

## 已实现功能

✅ **基础 PWA 配置**
- `frontend/public/manifest.json` - Web App Manifest 配置（已添加 `start_url` 和正确的图标 purpose）
- `frontend/public/sw.js` - Service Worker 实现（网络优先策略 + 运行时缓存）
- `frontend/components/pwa-register.tsx` - Service Worker 注册组件
- `frontend/components/pwa-install-prompt.tsx` - 安装提示 UI 组件
- `frontend/app/layout.tsx` - 已集成 PWA 组件

## 桌面端安装要求

桌面浏览器（Chrome/Edge）显示"安装"按钮需要满足以下条件：

1. ✅ **HTTPS 协议** - 必须通过 HTTPS 访问（localhost 除外）
2. ✅ **有效的 manifest.json** - 包含 `name`, `short_name`, `start_url`, `display`, `icons`
3. ✅ **注册 Service Worker** - 必须成功注册并激活
4. ✅ **图标要求** - 至少一个 192x192 和一个 512x512 的图标，purpose 包含 `any`
5. ⚠️ **用户交互** - 用户需要与页面有一定交互（点击、滚动等）
6. ⚠️ **未安装** - 应用尚未安装到系统

## 桌面端安装位置

安装按钮会出现在：
- **Chrome**: 地址栏右侧的 ⊕ 图标
- **Edge**: 地址栏右侧的 ⊕ 图标或设置菜单中的"应用" → "将此站点作为应用安装"
- **自动提示**: `beforeinstallprompt` 事件触发时显示我们的自定义安装提示

## PWA 核心技术组件

### 1. Web App Manifest
**文件位置**: `frontend/public/manifest.json`

```json
{
  "name": "AI Higress",
  "short_name": "AI Higress",
  "description": "AI智能路由网关管理系统",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#0066cc",
  "orientation": "portrait-primary",
  "scope": "/",
  "icons": [
    {
      "src": "/icon-192x192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icon-512x512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ],
  "categories": ["productivity", "business"],
  "lang": "zh-CN",
  "dir": "ltr"
}
```

### 2. Service Worker
**文件位置**: `frontend/public/sw.js`

Service Worker 用于实现离线缓存、后台同步等功能。

### 3. PWA 依赖包
需要在 `frontend/package.json` 中添加：

```json
{
  "dependencies": {
    "next-pwa": "^5.6.0",
    "workbox-webpack-plugin": "^7.0.0"
  }
}
```

### 4. Next.js 配置更新
**文件**: `frontend/next.config.ts`

```typescript
import type { NextConfig } from "next";
import withPWA from "next-pwa";

const nextConfig: NextConfig = {
  // 现有配置...
};

export default withPWA({
  dest: "public",
  register: true,
  skipWaiting: true,
})(nextConfig);
```

## 实施步骤

### Phase 1: 基础 PWA 配置
1. 创建 Web App Manifest
2. 生成应用图标 (192x192, 512x512)
3. 配置 Next.js PWA 插件
4. 实现基础 Service Worker

### Phase 2: 离线功能增强
1. 配置离线缓存策略
2. 添加离线页面
3. 实现关键资源预缓存
4. 添加安装提示组件

### Phase 3: 高级功能
1. 实现推送通知 (可选)
2. 添加后台同步
3. 优化性能和加载时间

## Service Worker 实现

```javascript
// frontend/public/sw.js
const CACHE_NAME = 'ai-higress-v1';
const urlsToCache = [
  '/',
  '/dashboard',
  '/static/js/bundle.js',
  '/static/css/main.css',
  '/manifest.json'
];

// 安装事件
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(urlsToCache))
  );
});

// 激活事件
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// 网络请求拦截
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});
```

## 安装提示组件

创建 React 组件来引导用户安装 PWA：

```typescript
// frontend/components/pwa/install-prompt.tsx
'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [showPrompt, setShowPrompt] = useState(false);

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
      setShowPrompt(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    };
  }, []);

  const handleInstall = async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') {
        console.log('User accepted the install prompt');
      }
      setDeferredPrompt(null);
      setShowPrompt(false);
    }
  };

  if (!showPrompt) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 z-50 bg-white border rounded-lg shadow-lg p-4">
      <p className="text-sm text-gray-600 mb-2">安装 AI Higress 到桌面以获得更好的体验</p>
      <div className="flex gap-2">
        <Button onClick={handleInstall} size="sm">
          安装
        </Button>
        <Button
          onClick={() => setShowPrompt(false)}
          variant="outline"
          size="sm"
        >
          稍后
        </Button>
      </div>
    </div>
  );
}
```

## 应用图标设计要求

遵循墨水风格设计原则：
- 主色调: 深灰色 (#1a1a1a) 和纯白 (#ffffff)
- 强调色: 深蓝 (#0066cc)
- 设计元素: 简洁的路由/网关图标，避免复杂图形
- 格式: PNG, 支持透明背景

## 测试清单

### 功能测试
- [x] manifest.json 配置完整（包含 start_url）
- [x] Service Worker 注册和激活
- [x] 图标 purpose 设置为 "any maskable"
- [ ] 在 Chrome/Edge 中显示"安装"按钮（需要 HTTPS 环境）
- [ ] 安装后以独立窗口运行
- [ ] 离线时显示缓存内容
- [ ] 网络恢复后自动同步

### 桌面端测试步骤

1. **部署到 HTTPS 环境**
   ```bash
   # 生产环境部署
   IMAGE_TAG=latest docker compose -f docker-compose-deploy.yml --env-file .env up -d
   ```

2. **打开浏览器开发者工具**
   - Chrome DevTools → Application → Manifest（检查 manifest 是否正确加载）
   - Chrome DevTools → Application → Service Workers（确认 SW 已激活）

3. **检查安装条件**
   - 确保使用 HTTPS（或 localhost）
   - 与页面交互（点击、滚动）
   - 查看地址栏右侧是否出现 ⊕ 安装图标

4. **手动触发安装提示**
   - 在控制台运行：`window.dispatchEvent(new Event('beforeinstallprompt'))`
   - 检查自定义安装提示是否显示

### 兼容性测试
- [ ] Chrome Desktop (Windows/Mac/Linux) - 完全支持
- [ ] Edge Desktop - 完全支持
- [ ] Safari Desktop - 有限支持（需要手动添加到 Dock）
- [ ] Chrome Mobile (Android) - 完全支持
- [ ] Safari Mobile (iOS) - 需要"添加到主屏幕"

### Lighthouse PWA 测试
```bash
# 使用 Lighthouse CLI 测试
npx lighthouse https://your-domain.com --view --preset=desktop
```
- [ ] PWA 评分达到 90+
- [ ] 所有 PWA 指标通过
- [ ] 可安装性检查通过

## 部署注意事项

1. **HTTPS 要求**: PWA 必须在 HTTPS 环境下运行（这是桌面端显示安装按钮的关键）
   - 开发环境：localhost 自动支持
   - 生产环境：必须配置 SSL 证书

2. **缓存策略**: 当前使用网络优先策略
   - 优先从网络获取最新内容
   - 网络失败时回退到缓存
   - 避免过度缓存导致内容更新延迟

3. **版本控制**: Service Worker 更新机制
   - 修改 `sw.js` 中的 `CACHE_NAME` 版本号
   - 用户下次访问时自动更新
   - 可在控制台提示用户刷新页面

4. **监控**: 添加 PWA 安装率和使用情况监控
   - 监听 `appinstalled` 事件
   - 统计安装转化率
   - 追踪独立窗口使用情况

## 常见问题排查

### 桌面端不显示安装按钮

1. **检查 HTTPS**
   ```bash
   # 确保使用 HTTPS 访问
   curl -I https://your-domain.com
   ```

2. **检查 manifest.json**
   - 打开 Chrome DevTools → Application → Manifest
   - 确认所有必需字段都存在
   - 检查图标是否正确加载

3. **检查 Service Worker**
   - 打开 Chrome DevTools → Application → Service Workers
   - 确认状态为 "activated and is running"
   - 如果失败，查看错误信息

4. **清除缓存重试**
   ```javascript
   // 在控制台运行
   navigator.serviceWorker.getRegistrations().then(registrations => {
     registrations.forEach(r => r.unregister());
   });
   ```

5. **检查浏览器支持**
   - Chrome 版本 >= 73
   - Edge 版本 >= 79
   - 确保未禁用 PWA 功能

### 移动端正常但桌面端不行

- 桌面端对 PWA 的要求更严格
- 必须满足所有安装条件
- 需要用户与页面有交互
- 某些企业环境可能禁用了 PWA 功能

## 后续优化

1. **性能优化**: 优化首次加载时间和运行时性能
2. **推送通知**: 实现基于 Web Push 的通知功能
3. **数据同步**: 添加后台数据同步机制
4. **多语言支持**: 为不同地区用户提供本地化安装体验

## 参考资源

- [PWA 官方文档](https://web.dev/progressive-web-apps/)
- [Web App Manifest](https://developer.mozilla.org/en-US/docs/Web/Manifest)
- [Service Worker API](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [Next.js PWA 插件](https://github.com/shadowwalker/next-pwa)