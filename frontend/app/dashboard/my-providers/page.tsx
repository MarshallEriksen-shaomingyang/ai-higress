import { cookies } from "next/headers";
import { MyProvidersPageClient } from "./components/my-providers-page-client";
import { Provider } from "@/http/provider";

// 服务器端获取用户信息的辅助函数
async function getUserFromCookies(): Promise<{ id: string; token: string } | null> {
  const cookieStore = await cookies();
  const userCookie = cookieStore.get("user");
  const tokenCookie = cookieStore.get("access_token");

  if (!userCookie?.value || !tokenCookie?.value) {
    return null;
  }

  try {
    const user = JSON.parse(userCookie.value);
    return {
      id: user.id,
      token: tokenCookie.value,
    };
  } catch {
    return null;
  }
}

// 服务器端获取私有提供商数据
async function getPrivateProvidersData(
  userId: string,
  token: string
): Promise<Provider[]> {
  const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

  try {
    const response = await fetch(`${BASE_URL}/users/${userId}/private-providers`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      cache: "no-store", // 不缓存，确保获取最新数据
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch private providers: ${response.status}`);
    }

    const data: Provider[] = await response.json();
    return data;
  } catch (error) {
    console.error("Failed to fetch private providers on server:", error);
    return [];
  }
}

// 服务器端获取配额限制（暂时硬编码，后续接入真实 API）
async function getQuotaLimit(userId: string, token: string): Promise<number> {
  // TODO: 接入真实的配额 API
  // const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  // const response = await fetch(`${BASE_URL}/users/${userId}/quota`, {
  //   headers: {
  //     Authorization: `Bearer ${token}`,
  //     "Content-Type": "application/json",
  //   },
  //   cache: "no-store",
  // });
  // const data = await response.json();
  // return data.private_provider_limit;

  // 暂时返回默认值
  return 10;
}

export const metadata = {
  title: "我的私有 Provider",
  description: "管理您的私有提供商与配额",
};

export default async function MyProvidersPage() {
  // 在服务器端获取用户信息和 token
  const userAuth = await getUserFromCookies();

  // 在服务器端获取初始数据
  let privateProviders: Provider[] = [];
  let quotaLimit = 10;

  if (userAuth) {
    privateProviders = await getPrivateProvidersData(userAuth.id, userAuth.token);
    quotaLimit = await getQuotaLimit(userAuth.id, userAuth.token);
  }

  // 如果未登录，重定向到登录页
  if (!userAuth) {
    // TODO: 重定向到登录页
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">请先登录</p>
      </div>
    );
  }

  return (
    <MyProvidersPageClient
      initialProviders={privateProviders}
      userId={userAuth.id}
      quotaLimit={quotaLimit}
    />
  );
}
