import { ProvidersPageClient } from "@/components/dashboard/providers/providers-page-client";
import { Provider } from "@/http/provider";

export default async function ProvidersPage() {
  // 服务器端暂不依赖 Cookie 获取用户信息，初始列表留空，交由客户端根据登录态加载
  const privateProviders: Provider[] = [];
  const publicProviders: Provider[] = [];

  return (
    <ProvidersPageClient
      initialPrivateProviders={privateProviders}
      initialPublicProviders={publicProviders}
      userId={null}
    />
  );
}
