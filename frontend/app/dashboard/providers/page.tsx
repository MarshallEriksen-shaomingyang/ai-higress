import { cookies } from "next/headers";
import { ProvidersPageClient } from "@/components/dashboard/providers/providers-page-client";
import { Provider, UserAvailableProvidersResponse } from "@/http/provider";

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

// 服务器端获取提供商数据
async function getProvidersData(
  userId: string,
  token: string
): Promise<{
  privateProviders: Provider[];
  publicProviders: Provider[];
}> {
  const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
  
  try {
    const response = await fetch(`${BASE_URL}/users/${userId}/providers`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      cache: 'no-store', // 不缓存，确保获取最新数据
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch providers: ${response.status}`);
    }

    const data: UserAvailableProvidersResponse = await response.json();
    return {
      privateProviders: data.private_providers,
      publicProviders: data.public_providers,
    };
  } catch (error) {
    console.error("Failed to fetch providers on server:", error);
    return {
      privateProviders: [],
      publicProviders: [],
    };
  }
}

export default async function ProvidersPage() {
  // 在服务器端获取用户信息和 token
  const userAuth = await getUserFromCookies();
  
  // 在服务器端获取初始数据
  let privateProviders: Provider[] = [];
  let publicProviders: Provider[] = [];
  
  if (userAuth) {
    const data = await getProvidersData(userAuth.id, userAuth.token);
    privateProviders = data.privateProviders;
    publicProviders = data.publicProviders;
  }

  return (
    <ProvidersPageClient
      initialPrivateProviders={privateProviders}
      initialPublicProviders={publicProviders}
      userId={userAuth?.id ?? null}
    />
  );
}