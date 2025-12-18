import { MyProvidersPageClient } from "./components/my-providers-page-client";

export const metadata = {
  title: "我的私有 Provider",
  description: "管理您的私有提供商与配额",
};

export default function MyProvidersPage() {
  // 仅负责页面结构与元数据，登录态与数据加载在客户端处理
  return <MyProvidersPageClient />;
}
