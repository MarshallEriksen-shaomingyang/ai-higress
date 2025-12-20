/**
 * SlateChatInput 使用示例
 * 
 * 这个文件展示了如何在聊天页面中使用 SlateChatInput 组件
 */

"use client";

import { SlateChatInput, type ModelParameters } from "./slate-chat-input";
import { useSendMessage } from "@/lib/swr/use-messages";
import { toast } from "sonner";

interface ExampleUsageProps {
  conversationId: string;
  assistantId: string;
}

export function SlateChatInputExample({ conversationId, assistantId }: ExampleUsageProps) {
  const sendMessage = useSendMessage(conversationId, assistantId);

  // 发送消息处理函数
  const handleSend = async (
    content: string,
    images: string[],
    parameters: ModelParameters
  ) => {
    try {
      // 这里可以将图片和参数一起发送到后端
      // 实际实现需要根据后端 API 调整
      await sendMessage({
        content,
        // 如果后端支持，可以添加：
        // images,
        // parameters,
      });
    } catch (error) {
      console.error("Failed to send message:", error);
      throw error;
    }
  };

  // 清空历史记录处理函数
  const handleClearHistory = async () => {
    // 实现清空历史记录的逻辑
    // 例如调用后端 API 删除会话消息
    console.log("Clear history for conversation:", conversationId);
  };

  // MCP 工具处理函数
  const handleMcpAction = () => {
    // 实现 MCP 工具面板的打开逻辑
    console.log("Open MCP tools panel");
    toast.info("MCP 工具面板功能待实现");
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
        frequency_penalty: 0.0,
        presence_penalty: 0.0,
      }}
    />
  );
}
