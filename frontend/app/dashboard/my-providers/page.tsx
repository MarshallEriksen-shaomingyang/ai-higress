import { MyProvidersPageClient } from "./components/my-providers-page-client";

export const metadata = {
  title: "我的私有 Provider",
  description: "管理您的私有提供商与配额",
};

/**
 * 私有 Provider 页面 - 服务端组件
 * 
 * 注意：此页面需要用户登录，且数据依赖客户端的 userId。
 * 服务端无法获取 userId（存储在客户端 auth store），
 * 因此不进行服务端预取，让客户端直接请求。
 */
export default function MyProvidersPage() {
  return <MyProvidersPageClient />;
}
