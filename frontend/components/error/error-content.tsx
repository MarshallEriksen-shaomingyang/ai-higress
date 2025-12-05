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