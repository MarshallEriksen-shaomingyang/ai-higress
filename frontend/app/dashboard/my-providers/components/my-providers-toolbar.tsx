"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/lib/i18n-context";
import { Plus, RefreshCw, Search } from "lucide-react";

export interface MyProvidersToolbarProps {
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  isRefreshing: boolean;
  onRefresh: () => void;
  onCreate: () => void;
}

export function MyProvidersToolbar({
  searchQuery,
  onSearchQueryChange,
  isRefreshing,
  onRefresh,
  onCreate,
}: MyProvidersToolbarProps) {
  const { t } = useI18n();

  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="relative w-full md:w-80">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t("my_providers.search_placeholder")}
          value={searchQuery}
          onChange={(e) => onSearchQueryChange(e.target.value)}
          className="pl-9"
        />
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          onClick={onRefresh}
          disabled={isRefreshing}
          className="flex-1 md:flex-none"
        >
          <RefreshCw
            className={`w-4 h-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`}
          />
          {t("my_providers.refresh")}
        </Button>
        <Button onClick={onCreate} className="flex-1 md:flex-none">
          <Plus className="w-4 h-4 mr-2" />
          {t("my_providers.create_provider")}
        </Button>
      </div>
    </div>
  );
}

