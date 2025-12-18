"use client";

import type { Provider } from "@/http/provider";
import { HealthStats } from "./health-stats";
import { QuotaCard } from "./quota-card";

export interface MyProvidersSummaryProps {
  providers: Provider[];
  quotaLimit: number;
  isUnlimited: boolean;
  isLoading: boolean;
}

export function MyProvidersSummary({
  providers,
  quotaLimit,
  isUnlimited,
  isLoading,
}: MyProvidersSummaryProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <QuotaCard
        current={providers.length}
        limit={quotaLimit}
        isUnlimited={isUnlimited}
        isLoading={isLoading}
      />
      <HealthStats providers={providers} isLoading={isLoading} />
    </div>
  );
}

