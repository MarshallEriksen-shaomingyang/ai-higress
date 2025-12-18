"use client";

import { useState } from "react";
import { ErrorState } from "./error-state";
import { EmptyState } from "./empty-state";
import { Inbox, Database } from "lucide-react";

/**
 * 错误和空状态组件演示
 * 
 * 用于展示 ErrorState 和 EmptyState 组件的各种用法
 */
export function ErrorEmptyDemo() {
  const [retryCount, setRetryCount] = useState(0);

  const handleRetry = () => {
    setRetryCount((prev) => prev + 1);
    console.log("Retry clicked, count:", retryCount + 1);
  };

  return (
    <div className="space-y-8 p-6">
      <div>
        <h2 className="text-2xl font-bold mb-4">错误状态组件演示</h2>
        
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold mb-2">基础用法</h3>
            <ErrorState onRetry={handleRetry} />
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">自定义标题和描述</h3>
            <ErrorState
              title="数据加载失败"
              message="无法连接到服务器，请检查网络连接后重试"
              onRetry={handleRetry}
            />
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">不显示重试按钮</h3>
            <ErrorState
              title="权限不足"
              message="您没有权限访问此数据"
              showRetry={false}
            />
          </div>

          <div className="p-4 bg-muted rounded-lg">
            <p className="text-sm text-muted-foreground">
              重试次数: {retryCount}
            </p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-2xl font-bold mb-4">空状态组件演示</h2>
        
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold mb-2">基础用法</h3>
            <EmptyState />
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">自定义标题和描述</h3>
            <EmptyState
              title="暂无数据"
              message="当前时间范围内没有数据，请尝试调整筛选条件"
            />
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">自定义图标 - Inbox</h3>
            <EmptyState
              icon={<Inbox className="size-12 text-muted-foreground/50" />}
              title="收件箱为空"
              message="您还没有收到任何消息"
            />
          </div>

          <div>
            <h3 className="text-lg font-semibold mb-2">自定义图标 - Database</h3>
            <EmptyState
              icon={<Database className="size-12 text-muted-foreground/50" />}
              title="数据库为空"
              message="还没有任何记录"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
