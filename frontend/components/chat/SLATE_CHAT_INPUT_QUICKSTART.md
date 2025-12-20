# SlateChatInput 快速开始

## 5 分钟上手

### 1. 基础使用

```tsx
import { SlateChatInput } from "@/components/chat";

function MyChat() {
  return (
    <SlateChatInput
      conversationId="conv-123"
      onSend={async (content, images, params) => {
        console.log("发送:", content);
        console.log("图片:", images);
        console.log("参数:", params);
      }}
    />
  );
}
```

### 2. 完整功能

```tsx
import { SlateChatInput } from "@/components/chat";

function FullFeaturedChat() {
  return (
    <SlateChatInput
      conversationId="conv-123"
      assistantId="asst-456"
      
      // 发送消息
      onSend={async (content, images, params) => {
        await fetch("/api/messages", {
          method: "POST",
          body: JSON.stringify({ content, images, params }),
        });
      }}
      
      // 清空历史
      onClearHistory={async () => {
        await fetch("/api/conversations/conv-123/clear", {
          method: "POST",
        });
      }}
      
      // MCP 工具
      onMcpAction={() => {
        console.log("打开 MCP 面板");
      }}
      
      // 默认参数
      defaultParameters={{
        temperature: 0.7,
        top_p: 0.9,
      }}
    />
  );
}
```

### 3. 与现有聊天页面集成

```tsx
// 在 frontend/app/chat/[assistant_id]/[conversation_id]/page.tsx 中使用

import { SlateChatInput } from "@/components/chat";
import { useSendMessage } from "@/lib/swr/use-messages";

export default function ChatPage({ params }) {
  const sendMessage = useSendMessage(
    params.conversation_id,
    params.assistant_id
  );

  return (
    <div className="flex flex-col h-screen">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto">
        {/* ... */}
      </div>
      
      {/* 输入框 */}
      <SlateChatInput
        conversationId={params.conversation_id}
        assistantId={params.assistant_id}
        onSend={async (content, images, params) => {
          await sendMessage({ content });
        }}
      />
    </div>
  );
}
```

## 功能说明

### 📝 富文本编辑
- 基于 Slate.js
- 支持撤销/重做
- 自动高度调整

### 🖼️ 图片上传
- 点击图片图标上传
- 支持多图
- 实时预览
- Base64 编码

### ⚙️ 模型参数
- temperature（创意活跃度）
- top_p（思维开放度）
- frequency_penalty（词汇丰富度）
- presence_penalty（表达发散度）

### 🗑️ 清空历史
- 一键清空会话记录
- 需要提供 `onClearHistory` 回调

### ⚡ MCP 工具
- 集成 MCP 工具按钮
- 需要提供 `onMcpAction` 回调

### ⌨️ 快捷键
- `Ctrl+Enter` / `Cmd+Enter`：发送消息

## 样式定制

```tsx
<SlateChatInput
  className="border-t-2 bg-gray-50 dark:bg-gray-900"
  // ...
/>
```

## 国际化

组件自动支持中英文切换，跟随系统语言设置。

## 注意事项

1. **图片大小**：建议压缩后再上传
2. **后端支持**：需要后端 API 支持接收图片和参数
3. **性能**：大量图片可能影响性能

## 下一步

- 查看完整文档：`SLATE_CHAT_INPUT_README.md`
- 查看示例代码：`slate-chat-input-example.tsx`
- 运行测试：`bun test slate-chat-input.test.tsx`
