"use client";

import { MessageSquare } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";

/**
 * 聊天主页
 * 
 * 显示助手选择提示，引导用户选择或创建助手
 */
export default function ChatPage() {
  const { t } = useI18n();

  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center space-y-4 max-w-md px-4">
        <div className="flex justify-center">
          <div className="rounded-full bg-muted p-6">
            <MessageSquare className="h-12 w-12 text-muted-foreground" />
          </div>
        </div>
        
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">
            {t('chat.welcome.title')}
          </h2>
          <p className="text-muted-foreground">
            {t('chat.welcome.description')}
          </p>
        </div>

        <div className="text-sm text-muted-foreground space-y-1">
          <p>{t('chat.welcome.hint1')}</p>
          <p>{t('chat.welcome.hint2')}</p>
        </div>
      </div>
    </div>
  );
}
