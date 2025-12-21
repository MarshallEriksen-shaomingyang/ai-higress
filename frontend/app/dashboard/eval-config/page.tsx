import { EvalConfigPageClient } from "./components/eval-config-page-client";

/**
 * 评测配置页
 *
 * 服务端组件：认证与数据请求在客户端组件中处理
 */
export default function EvalConfigPage() {
  return (
    <div className="space-y-6 max-w-7xl">
      <EvalConfigPageClient />
    </div>
  );
}
