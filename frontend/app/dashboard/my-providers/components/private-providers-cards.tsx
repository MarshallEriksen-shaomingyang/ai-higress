"use client";

import type { Provider } from "@/http/provider";
import type { DashboardV2ProviderMetricsItem } from "@/lib/api-types";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";
import { Plus } from "lucide-react";
import { ProviderCard } from "@/app/dashboard/providers/_components/card/provider-card";

export interface PrivateProvidersCardsProps {
  providers: Provider[];
  isRefreshing: boolean;
  metricsByProviderId: Record<string, DashboardV2ProviderMetricsItem | undefined>;
  isMetricsLoading: boolean;
  onCreate?: () => void;
  onEdit?: (provider: Provider) => void;
  onDelete?: (providerId: string) => void;
  onViewDetails: (providerId: string) => void;
  onViewModels: (providerId: string) => void;
  onManageKeys?: (providerId: string) => void;
}

export function PrivateProvidersCards({
  providers,
  isRefreshing,
  metricsByProviderId,
  isMetricsLoading,
  onCreate,
  onEdit,
  onDelete,
  onViewDetails,
  onViewModels,
  onManageKeys,
}: PrivateProvidersCardsProps) {
  const { t } = useI18n();

  if (providers.length === 0 && !isRefreshing) {
    return (
      <div className="rounded-lg border border-dashed p-12 text-center">
        <div className="mx-auto max-w-md space-y-3">
          <h3 className="text-lg font-medium">
            {t("my_providers.empty_message")}
          </h3>
          <p className="text-sm text-muted-foreground">
            {t("my_providers.empty_description")}
          </p>
          {onCreate && (
            <Button onClick={onCreate} className="mt-4">
              <Plus className="w-4 h-4 mr-2" />
              {t("my_providers.create_provider")}
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
      {providers.map((provider) => (
        <ProviderCard
          key={provider.provider_id}
          provider={provider}
          metrics={metricsByProviderId[provider.provider_id]}
          isMetricsLoading={isMetricsLoading}
          onConfigure={onEdit}
          onDelete={onDelete}
          onViewDetails={onViewDetails}
          onViewModels={onViewModels}
          onManageKeys={onManageKeys}
          canModify={!!onEdit}
          canManageKeys={!!onManageKeys}
        />
      ))}
    </div>
  );
}
