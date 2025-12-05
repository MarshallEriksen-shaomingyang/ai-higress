# AI Higress 错误页面测试指南

## 测试概述

本文档提供了详细的测试步骤，用于验证 404 和 500 错误页面的功能和显示效果。

## 前置条件

1. 确保开发服务器正在运行：
```bash
cd frontend
npm run dev
# 或
bun dev
```

2. 浏览器已打开开发者工具（F12）

## 测试清单

### 一、404 页面测试

#### 1.1 基本显示测试

**测试步骤：**
1. 访问不存在的页面：`http://localhost:3000/non-existent-page`
2. 验证页面显示

**预期结果：**
- ✅ 显示大号 "404" 数字（带渐变效果）
- ✅ 显示 "页面未找到" 标题（中文）或 "Page Not Found"（英文）
- ✅ 显示友好的错误描述文案
- ✅ 显示两个操作按钮："返回首页" 和 "返回上一页"
- ✅ 显示 4 个快捷链接卡片（仪表盘、提供商、文档、支持）
- ✅ 页面有淡入动画效果

#### 1.2 按钮功能测试

**测试步骤：**
1. 点击 "返回首页" 按钮
2. 验证跳转到首页（`/`）
3. 再次访问 404 页面
4. 点击 "返回上一页" 按钮
5. 验证返回到上一个页面

**预期结果：**
- ✅ "返回首页" 按钮正确跳转到首页
- ✅ "返回上一页" 按钮正确返回上一页
- ✅ 按钮有悬停效果

#### 1.3 快捷链接测试

**测试步骤：**
1. 悬停在每个快捷链接卡片上
2. 点击 "仪表盘" 卡片
3. 验证跳转到 `/dashboard/overview`
4. 返回 404 页面，测试其他链接

**预期结果：**
- ✅ 卡片悬停时有抬升效果和阴影变化
- ✅ 每个链接都能正确跳转到对应页面
- ✅ 卡片显示图标、标题和描述

#### 1.4 响应式布局测试

**测试步骤：**
1. 调整浏览器窗口大小到不同尺寸
2. 验证布局变化

**预期结果：**
- ✅ **桌面（≥1024px）**：
  - 404 数字：text-9xl
  - 快捷链接：4 列网格
  - 按钮：水平排列
  
- ✅ **平板（768-1023px）**：
  - 404 数字：text-8xl
  - 快捷链接：2 列网格
  - 按钮：水平排列
  
- ✅ **移动（<768px）**：
  - 404 数字：text-7xl
  - 快捷链接：1 列布局
  - 按钮：垂直堆叠

#### 1.5 国际化测试

**测试步骤：**
1. 在页面上切换语言（如果有语言切换器）
2. 或修改浏览器语言设置
3. 验证文案变化

**预期结果：**
- ✅ 中文模式：所有文案显示为中文
- ✅ 英文模式：所有文案显示为英文
- ✅ 语言切换后文案立即更新

#### 1.6 主题测试

**测试步骤：**
1. 切换到亮色主题
2. 验证页面显示
3. 切换到暗色主题
4. 验证页面显示

**预期结果：**
- ✅ 亮色主题：背景浅色，文字深色，对比度良好
- ✅ 暗色主题：背景深色，文字浅色，对比度良好
- ✅ 渐变色和卡片样式在两种主题下都显示正常

### 二、500 错误页面测试

#### 2.1 基本显示测试

**测试步骤：**
1. 访问测试错误页面：`http://localhost:3000/test-error`
2. 验证页面显示

**预期结果：**
- ✅ 显示红色警告图标（AlertTriangle）
- ✅ 图标有脉动动画效果
- ✅ 显示 "服务器错误" 标题（中文）或 "Server Error"（英文）
- ✅ 显示友好的错误描述文案
- ✅ 显示错误 ID 卡片（包含错误 ID 和时间戳）
- ✅ 显示两个操作按钮："刷新页面" 和 "返回首页"
- ✅ 显示支持信息文案
- ✅ 页面有淡入动画效果

#### 2.2 错误 ID 功能测试

**测试步骤：**
1. 查看错误 ID 卡片
2. 验证错误 ID 格式（如：ERR-1733368800000-ABC123）
3. 验证时间戳显示
4. 点击复制按钮
5. 粘贴到文本编辑器验证

**预期结果：**
- ✅ 错误 ID 格式正确（ERR-时间戳-随机字符串）
- ✅ 时间戳显示当前时间
- ✅ 点击复制按钮后显示成功 Toast 提示
- ✅ 错误 ID 成功复制到剪贴板
- ✅ 复制按钮有悬停效果

#### 2.3 按钮功能测试

**测试步骤：**
1. 点击 "刷新页面" 按钮
2. 验证页面重新加载（错误 ID 会变化）
3. 点击 "返回首页" 按钮
4. 验证跳转到首页

**预期结果：**
- ✅ "刷新页面" 按钮触发页面重新加载
- ✅ 重新加载后生成新的错误 ID
- ✅ "返回首页" 按钮正确跳转到首页
- ✅ 按钮有悬停效果

#### 2.4 响应式布局测试

**测试步骤：**
1. 调整浏览器窗口大小到不同尺寸
2. 验证布局变化

**预期结果：**
- ✅ **桌面（≥1024px）**：
  - 警告图标：size-32
  - 按钮：水平排列
  - 错误 ID 卡片：居中，最大宽度 576px
  
- ✅ **平板（768-1023px）**：
  - 警告图标：size-24
  - 按钮：水平排列
  - 错误 ID 卡片：全宽带边距
  
- ✅ **移动（<768px）**：
  - 警告图标：size-20
  - 按钮：垂直堆叠
  - 错误 ID 卡片：全宽

#### 2.5 国际化测试

**测试步骤：**
1. 切换语言
2. 验证文案变化

**预期结果：**
- ✅ 中文模式：所有文案显示为中文
- ✅ 英文模式：所有文案显示为英文
- ✅ 复制成功提示也会根据语言变化

#### 2.6 主题测试

**测试步骤：**
1. 切换主题
2. 验证页面显示

**预期结果：**
- ✅ 亮色主题：显示正常
- ✅ 暗色主题：显示正常
- ✅ 警告图标颜色在两种主题下都清晰可见

### 三、可访问性测试

#### 3.1 键盘导航测试

**测试步骤：**
1. 使用 Tab 键在页面元素间导航
2. 使用 Enter 或 Space 键激活按钮
3. 验证焦点指示器

**预期结果：**
- ✅ Tab 键可以在所有可交互元素间导航
- ✅ 焦点顺序合理（从上到下，从左到右）
- ✅ 焦点指示器清晰可见
- ✅ Enter/Space 键可以激活按钮和链接

#### 3.2 屏幕阅读器测试

**测试步骤：**
1. 启用屏幕阅读器（如 NVDA、JAWS 或 VoiceOver）
2. 浏览页面内容
3. 验证内容可读性

**预期结果：**
- ✅ 所有文本内容可以被正确读取
- ✅ 图标有适当的 aria-label
- ✅ 按钮有清晰的标签
- ✅ 错误信息有适当的语义标记

#### 3.3 颜色对比度测试

**测试步骤：**
1. 使用 Chrome DevTools 的 Lighthouse
2. 运行可访问性审计
3. 检查颜色对比度报告

**预期结果：**
- ✅ 所有文本对比度 ≥ 4.5:1
- ✅ 大文本对比度 ≥ 3:1
- ✅ 没有颜色对比度警告

### 四、性能测试

#### 4.1 加载性能测试

**测试步骤：**
1. 打开 Chrome DevTools Network 面板
2. 访问 404 页面
3. 查看加载时间和资源大小

**预期结果：**
- ✅ 页面加载时间 < 1 秒
- ✅ 没有不必要的网络请求
- ✅ 资源大小合理

#### 4.2 动画性能测试

**测试步骤：**
1. 打开 Chrome DevTools Performance 面板
2. 录制页面加载和交互
3. 查看 FPS 和性能指标

**预期结果：**
- ✅ 动画流畅，FPS ≥ 60
- ✅ 没有明显的卡顿
- ✅ CPU 使用率合理

### 五、浏览器兼容性测试

**测试浏览器：**
- ✅ Chrome（最新版本）
- ✅ Firefox（最新版本）
- ✅ Safari（最新版本）
- ✅ Edge（最新版本）

**测试内容：**
- ✅ 页面显示正常
- ✅ 所有功能正常工作
- ✅ 动画效果正常
- ✅ 复制功能正常

### 六、边缘情况测试

#### 6.1 长错误 ID 测试

**测试步骤：**
1. 修改错误 ID 生成逻辑，生成超长 ID
2. 验证显示效果

**预期结果：**
- ✅ 长 ID 正确换行显示
- ✅ 不会破坏布局
- ✅ 仍然可以复制

#### 6.2 网络离线测试

**测试步骤：**
1. 在 DevTools 中启用离线模式
2. 访问错误页面
3. 验证功能

**预期结果：**
- ✅ 页面仍然可以显示（因为是静态页面）
- ✅ 按钮功能正常
- ✅ 复制功能正常

#### 6.3 快速切换测试

**测试步骤：**
1. 快速在 404 和正常页面间切换
2. 快速触发多次错误
3. 验证页面稳定性

**预期结果：**
- ✅ 页面切换流畅
- ✅ 没有内存泄漏
- ✅ 没有错误堆栈

## 测试报告模板

### 测试环境
- 操作系统：
- 浏览器：
- 屏幕分辨率：
- 测试日期：

### 测试结果

#### 404 页面
- [ ] 基本显示
- [ ] 按钮功能
- [ ] 快捷链接
- [ ] 响应式布局
- [ ] 国际化
- [ ] 主题切换

#### 500 页面
- [ ] 基本显示
- [ ] 错误 ID 功能
- [ ] 按钮功能
- [ ] 响应式布局
- [ ] 国际化
- [ ] 主题切换

#### 可访问性
- [ ] 键盘导航
- [ ] 屏幕阅读器
- [ ] 颜色对比度

#### 性能
- [ ] 加载性能
- [ ] 动画性能

### 发现的问题
1. 
2. 
3. 

### 建议改进
1. 
2. 
3. 

## 自动化测试（可选）

如果需要编写自动化测试，可以参考以下示例：

```typescript
// frontend/__tests__/error-pages.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NotFoundContent } from "@/components/error/not-found-content";
import { ErrorContent } from "@/components/error/error-content";

describe("Error Pages", () => {
  describe("404 Page", () => {
    it("renders 404 heading", () => {
      render(<NotFoundContent />);
      expect(screen.getByText("404")).toBeInTheDocument();
    });

    it("renders navigation buttons", () => {
      render(<NotFoundContent />);
      expect(screen.getByText(/返回首页|Back to Home/i)).toBeInTheDocument();
      expect(screen.getByText(/返回上一页|Go Back/i)).toBeInTheDocument();
    });

    it("renders quick links", () => {
      render(<NotFoundContent />);
      expect(screen.getByText(/仪表盘|Dashboard/i)).toBeInTheDocument();
      expect(screen.getByText(/提供商|Providers/i)).toBeInTheDocument();
    });
  });

  describe("500 Page", () => {
    const mockError = new Error("Test error");
    const mockReset = jest.fn();

    it("renders error heading", () => {
      render(<ErrorContent error={mockError} reset={mockReset} />);
      expect(screen.getByText(/服务器错误|Server Error/i)).toBeInTheDocument();
    });

    it("generates and displays error ID", () => {
      render(<ErrorContent error={mockError} reset={mockReset} />);
      const errorIdElement = screen.getByText(/ERR-/);
      expect(errorIdElement).toBeInTheDocument();
    });

    it("calls reset when refresh button clicked", () => {
      render(<ErrorContent error={mockError} reset={mockReset} />);
      const refreshButton = screen.getByText(/刷新页面|Refresh/i);
      fireEvent.click(refreshButton);
      expect(mockReset).toHaveBeenCalled();
    });

    it("copies error ID to clipboard", async () => {
      // Mock clipboard API
      Object.assign(navigator, {
        clipboard: {
          writeText: jest.fn(),
        },
      });

      render(<ErrorContent error={mockError} reset={mockReset} />);
      const copyButton = screen.getByLabelText(/复制|Copy/i);
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled();
      });
    });
  });
});
```

## 测试完成标准

所有测试项目都通过后，错误页面即可认为已准备好部署到生产环境。

## 问题反馈

如果在测试过程中发现任何问题，请：
1. 记录问题详情（包括截图）
2. 记录复现步骤
3. 记录测试环境信息
4. 提交到项目的 Issue 跟踪系统