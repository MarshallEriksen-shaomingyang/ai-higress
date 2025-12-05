import { cookies } from "next/headers";
import { ProviderDetailClient } from "@/components/dashboard/providers/provider-detail-client";
import { providerDetailTranslations } from "@/lib/i18n/provider-detail";

interface ProviderDetailPageProps {
  params: {
    providerId: string;
  };
}

export default async function ProviderDetailPage({ params }: ProviderDetailPageProps) {
  // 从 cookies 获取语言设置
  const cookieStore = await cookies();
  const locale = cookieStore.get("locale")?.value || "zh-CN";
  
  // 获取对应语言的翻译
  const translations = providerDetailTranslations[locale as keyof typeof providerDetailTranslations] 
    || providerDetailTranslations["zh-CN"];

  return (
    <ProviderDetailClient 
      providerId={params.providerId} 
      translations={translations}
    />
  );
}
