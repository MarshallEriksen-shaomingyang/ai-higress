import { cookies } from "next/headers";
import { ProviderDetailClient } from "@/components/dashboard/providers/provider-detail-client";
import { providerDetailTranslations } from "@/lib/i18n/provider-detail";

interface ProviderDetailPageProps {
  params: Promise<{
    providerId: string;
  }>;
}

export default async function ProviderDetailPage({ params }: ProviderDetailPageProps) {
  // Next.js 15 中 params 是 Promise，这里先解包再使用
  const { providerId } = await params;

  // 从 cookies 获取语言设置
  const cookieStore = await cookies();
  const locale = cookieStore.get("locale")?.value || "zh-CN";

  // 获取对应语言的翻译
  const translations =
    providerDetailTranslations[locale as keyof typeof providerDetailTranslations] ??
    providerDetailTranslations["zh-CN"];

  return (
    <ProviderDetailClient
      providerId={providerId}
      translations={translations}
    />
  );
}
