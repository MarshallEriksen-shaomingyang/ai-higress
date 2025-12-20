# SlateChatInput 组件使用指南

## 概述

`SlateChatInput` 是一个基于 Slate.js 的富文本聊天输入框组件，专为 AI Higress 聊天系统设计。它提供了以下功能：

- ✅ 富文本编辑（基于 Slate.js）
- ✅ 图片上传和预览
- ✅ 模型参数调节（temperature、top_p、frequency_penalty、presence_penalty）
- ✅ 清空历史记录
- ✅ MCP 工具集成
- ✅ 国际化支持（中英文）
- ✅ 键盘快捷键（Ctrl+Enter 发送）
- ✅ 极简墨水风格设计

## 安装依赖

组件依赖以下包（已安装）：

```bash
bun add slate slate-react slate-history
```

## 基本使用

```tsx
import { SlateChatInput } from "@/components/chat";

function ChatPage() {
  const handleSend = async (
    content: string,
    images: string[],
    parameters: ModelParameters
  ) => {
    // 发送消息到后端
    console.log("Content:", content);
    console.log("Images:", images);
    console.log("Parameters:", parameters);
  };

  return (
    <SlateChatInput
      conversationId="conv-123"
      assistantId="asst-456"
      onSend={handleSend}
    />
  );
}
```

## Props 说明

### 必需参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `conversationId` | `string` | 会话 ID |

### 可选参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `assistantId` | `string` | - | 助手 ID |
| `disabled` | `boolean` | `false` | 是否禁用输入框 |
| `onSend` | `(content, images, parameters) => Promise<void>` | - | 发送消息回调 |
| `onClearHistory` | `() => Promise<void>` | - | 清空历史记录回调 |
| `onMcpAction` | `() => void` | - | MCP 工具按钮点击回调 |
| `className` | `string` | - | 自定义样式类名 |
| `defaultParameters` | `Partial<ModelParameters>` | 见下方 | 默认模型参数 |

### ModelParameters 类型

```typescript
interface ModelParameters {
  temperature: number;          // 创意活跃度 (0-2)
  top_p: number;               // 思维开放度 (0-1)
  frequency_penalty: number;   // 词汇丰富度 (0-2)
  presence_penalty: number;    // 表达发散度 (0-2)
  max_tokens?: number;         // 最大 token 数（可选）
}
```

默认参数值：
```typescript
{
  temperature: 1.0,
  top_p: 1.0,
  frequency_penalty: 0.0,
  presence_penalty: 0.0,
}
```

## 完整示例

```tsx
"use client";

import { SlateChatInput, type ModelParameters } from "@/components/chat";
import { useSendMessage } from "@/lib/swr/use-messages";
import { toast } from "sonner";

export function ChatInputWrapper({ conversationId, assistantId }: Props) {
  const sendMessage = useSendMessage(conversationId, assistantId);

  const handleSend = async (
    content: string,
    images: string[],
    parameters: ModelParameters
  ) => {
    try {
      // 发送消息（根据后端 API 调整）
      await sendMessage({
        content,
        // 如果后端支持图片和参数：
        // images,
        // parameters,
      });
    } catch (error) {
      console.error("Failed to send:", error);
      throw error; // 让组件显示错误提示
    }
  };

  const handleClearHistory = async () => {
    // 调用清空历史的 API
    try {
      await fetch(`/api/conversations/${conversationId}/clear`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Failed to clear:", error);
      throw error;
    }
  };

  const handleMcpAction = () => {
    // 打开 MCP 工具面板
    toast.info("MCP 工具面板");
  };

  return (
    <SlateChatInput
      conversationId={conversationId}
      assistantId={assistantId}
      onSend={handleSend}
      onClearHistory={handleClearHistory}
      onMcpAction={handleMcpAction}
      defaultParameters={{
        temperature: 0.7,
        top_p: 0.9,
      }}
    />
  );
}
```

## 功能说明

### 1. 富文本编辑

基于 Slate.js 实现，支持：
- 多行文本输入
- 自动高度调整（最大 200px）
- 历史记录（撤销/重做）

### 2. 图片上传

- 点击图片图标上传
- 支持多图上传
- 实时预览
- 悬停显示删除按钮
- 图片转为 Base64 格式

### 3. 模型参数调节

点击设置图标打开参数面板，可调节：

- **创意活跃度 (temperature)**：控制输出的随机性
  - 0.0：确定性输出
  - 1.0：平衡
  - 2.0：高度创造性

- **思维开放度 (top_p)**：控制词汇选择范围
  - 0.0：只选最可能的词
  - 1.0：考虑所有可能的词

- **词汇丰富度 (frequency_penalty)**：减少重复词汇
  - 0.0：不惩罚
  - 2.0：强烈惩罚重复

- **表达发散度 (presence_penalty)**：鼓励新话题
  - 0.0：不惩罚
  - 2.0：强烈鼓励新话题

### 4. 清空历史记录

- 点击垃圾桶图标
- 调用 `onClearHistory` 回调
- 显示成功/失败提示

### 5. MCP 工具

- 点击闪电图标
- 调用 `onMcpAction` 回调
- 可用于打开 MCP 工具面板

### 6. 键盘快捷键

- `Ctrl+Enter` 或 `Cmd+Enter`：发送消息

## 国际化

组件使用 `useI18n()` Hook，支持中英文切换。相关文案在 `frontend/lib/i18n/chat.ts` 中定义。

新增的文案 key：
- `chat.message.upload_image`
- `chat.message.model_parameters`
- `chat.message.mcp_tools`
- `chat.message.clear_history`
- `chat.message.parameter_temperature`
- `chat.message.parameter_top_p`
- `chat.message.parameter_frequency_penalty`
- `chat.message.parameter_presence_penalty`
- `chat.message.reset_parameters`
- 等等...

## 样式定制

组件遵循 AI Higress 的极简墨水风格设计：

- 细边框
- 微妙的阴影
- 简洁的图标
- 流畅的过渡动画

可通过 `className` prop 添加自定义样式：

```tsx
<SlateChatInput
  className="border-t-2 bg-gray-50"
  // ...
/>
```

## 注意事项

1. **图片格式**：目前只支持图片文件（通过 `file.type.startsWith("image/")` 检查）
2. **图片大小**：建议在上传前进行压缩，避免 Base64 过大
3. **后端集成**：需要后端 API 支持接收图片和参数数据
4. **性能**：大量图片可能影响性能，建议限制上传数量

## 与原 MessageInput 的对比

| 特性 | MessageInput | SlateChatInput |
|------|--------------|----------------|
| 编辑器 | Textarea | Slate.js 富文本 |
| 图片上传 | ❌ | ✅ |
| 模型参数 | ❌ | ✅ |
| 清空历史 | ❌ | ✅ |
| MCP 工具 | ❌ | ✅ |
| 历史记录 | ❌ | ✅（撤销/重做）|

## 后续扩展

可以考虑添加：

- [ ] 文件上传（PDF、文档等）
- [ ] @提及功能
- [ ] Markdown 快捷输入
- [ ] 表情符号选择器
- [ ] 语音输入
- [ ] 草稿自动保存
- [ ] 图片压缩和优化

## 相关文件

- 组件源码：`frontend/components/chat/slate-chat-input.tsx`
- 使用示例：`frontend/components/chat/slate-chat-input-example.tsx`
- 国际化文案：`frontend/lib/i18n/chat.ts`
- 导出索引：`frontend/components/chat/index.ts`
