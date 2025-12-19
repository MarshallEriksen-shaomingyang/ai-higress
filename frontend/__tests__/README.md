# 聊天助手系统 E2E 测试

## 概述

本目录包含聊天助手系统的端到端（E2E）集成测试，覆盖了系统的关键用户流程。

## 测试覆盖

### 1. 创建助手 → 创建会话 → 发送消息 → 查看回复流程

测试完整的聊天流程：
- 创建新助手
- 在助手下创建会话
- 发送用户消息
- 接收并显示助手回复
- 验证 baseline run 的执行
- 验证乐观更新机制

**验证的需求**: 1.1, 1.2, 2.1, 3.1, 3.2, 3.3, 3.5, 4.1, 4.2, 8.1, 8.2, 8.3

### 2. 触发评测 → 查看 challengers → 提交评分流程

测试推荐评测功能：
- 基于 baseline run 创建评测
- 显示 challenger 占位（running 状态）
- 轮询更新 challenger 状态
- 所有 challengers 完成后显示结果
- 提交评分反馈
- 支持重复提交评分
- 处理 challenger 执行失败

**验证的需求**: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.5, 8.4, 8.5, 8.6

### 3. 归档会话 → 验证无法发送消息流程

测试会话归档功能：
- 归档会话
- 验证归档后仍可读取历史消息
- 验证归档后无法发送新消息（返回 404）
- 验证归档会话从列表中隐藏

**验证的需求**: 2.3, 2.4, 2.5, 10.5, 10.6

### 4. 删除助手 → 验证级联删除流程

测试级联删除功能：
- 删除助手
- 验证助手删除后无法获取
- 验证助手下的会话被级联删除
- 删除会话
- 验证会话删除后无法获取消息

**验证的需求**: 1.4, 2.6, 10.1, 10.2, 10.3, 10.4

### 5. 错误处理和边缘情况

测试各种错误场景：
- 网络错误
- 认证错误（401）
- 评测频率限制（429）
- 评测未启用（403）
- 空列表处理
- 分页加载

**验证的需求**: 5.7, 5.8, 8.8, 9.1

## 运行测试

### 运行所有 E2E 测试

```bash
cd frontend
npm test -- __tests__/e2e
```

### 运行特定测试文件

```bash
cd frontend
npm test -- __tests__/e2e/chat-assistant-flow.test.tsx
```

### 运行测试并查看覆盖率

```bash
cd frontend
npm run test:coverage -- __tests__/e2e
```

### 监视模式（开发时使用）

```bash
cd frontend
npm run test:watch -- __tests__/e2e
```

## 测试架构

### 技术栈

- **测试框架**: Vitest
- **测试工具**: @testing-library/react, @testing-library/user-event
- **Mock 工具**: Vitest 内置 mock 功能

### Mock 策略

所有 HTTP 服务都被 mock：
- `assistantService`: 助手管理 API
- `conversationService`: 会话管理 API
- `messageService`: 消息和 run API
- `evalService`: 评测 API

### 测试隔离

每个测试套件都有独立的：
- `beforeEach`: 清除所有 mock
- `afterEach`: 清理测试环境
- SWR 缓存隔离（通过 TestWrapper）

## 添加新测试

### 1. 创建新测试文件

在 `__tests__/e2e/` 目录下创建新的测试文件：

```typescript
// __tests__/e2e/new-feature.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

describe('E2E: 新功能测试', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('应该完成新功能流程', async () => {
    // 测试代码
  });
});
```

### 2. Mock HTTP 服务

```typescript
vi.mock('@/http/service-name', () => ({
  serviceName: {
    method1: vi.fn(),
    method2: vi.fn(),
  },
}));
```

### 3. 编写测试用例

遵循 AAA 模式（Arrange-Act-Assert）：

```typescript
it('应该完成某个操作', async () => {
  // Arrange: 设置 mock 和初始状态
  vi.mocked(service.method).mockResolvedValue(mockData);

  // Act: 执行操作
  const result = await service.method(params);

  // Assert: 验证结果
  expect(result).toEqual(expectedResult);
  expect(service.method).toHaveBeenCalledWith(params);
});
```

## 最佳实践

### 1. 测试命名

使用清晰的中文描述测试意图：
- ✅ `应该完成完整的创建助手到查看回复流程`
- ❌ `test1`

### 2. Mock 数据

创建可复用的 mock 数据对象：

```typescript
const mockAssistant = {
  assistant_id: 'asst-1',
  project_id: 'proj-1',
  name: '测试助手',
  // ...
};
```

### 3. 异步测试

使用 `async/await` 和 `waitFor`：

```typescript
it('应该等待异步操作完成', async () => {
  const result = await service.method();
  expect(result).toBeDefined();
});
```

### 4. 错误测试

验证错误处理逻辑：

```typescript
it('应该处理错误', async () => {
  vi.mocked(service.method).mockRejectedValue(new Error('错误'));
  
  await expect(service.method()).rejects.toThrow('错误');
});
```

### 5. 测试隔离

确保每个测试独立运行：

```typescript
beforeEach(() => {
  vi.clearAllMocks();
});
```

## 调试测试

### 查看测试输出

```bash
npm test -- __tests__/e2e --reporter=verbose
```

### 调试单个测试

在测试中添加 `.only`：

```typescript
it.only('应该调试这个测试', async () => {
  // 测试代码
});
```

### 查看 Mock 调用

```typescript
console.log(vi.mocked(service.method).mock.calls);
```

## 持续集成

这些测试应该在 CI/CD 流程中运行：

```yaml
# .github/workflows/test.yml
- name: Run E2E Tests
  run: |
    cd frontend
    npm test -- __tests__/e2e
```

## 相关文档

- [Vitest 文档](https://vitest.dev/)
- [Testing Library 文档](https://testing-library.com/)
- [设计文档](../../.kiro/specs/chat-assistant-system/design.md)
- [需求文档](../../.kiro/specs/chat-assistant-system/requirements.md)
