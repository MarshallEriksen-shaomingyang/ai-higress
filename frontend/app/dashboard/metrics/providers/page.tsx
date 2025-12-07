"use client";

import React, { useState, useMemo } from "react";
import { useActiveProvidersOverview } from "@/lib/swr/use-overview-metrics";
import { ProvidersMetricsTable } from "@/components/dashboard/metrics/providers-metrics-table";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";

type TimeRange = "today" | "7d" | "30d" | "all";

export default function ProvidersMetricsPage() {
  const { t } = useI18n();
  const [timeRange, setTimeRange] = useState<TimeRange>("7d");

  const { data, loading } = useActiveProvidersOverview({
    time_range: timeRange,
    limit: 100,
  });

  const items = useMemo(() => data?.items ?? [], [data]);

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-3xl font-bold mb-2">
          {t("metrics.providers.title")}
        </h1>
        <p className="text-muted-foreground">
          {t("metrics.providers.subtitle")}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">
            {t("metrics.providers.time_range")}:
          </span>
          <div className="inline-flex rounded-md border bg-background p-0.5">
            <Button
              type="button"
              size="sm"
              variant={timeRange === "today" ? "default" : "ghost"}
              className="rounded-sm px-3 text-xs"
              onClick={() => setTimeRange("today")}
            >
              {t("metrics.providers.time_today")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={timeRange === "7d" ? "default" : "ghost"}
              className="rounded-sm px-3 text-xs"
              onClick={() => setTimeRange("7d")}
            >
              {t("metrics.providers.time_7d")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={timeRange === "30d" ? "default" : "ghost"}
              className="rounded-sm px-3 text-xs"
              onClick={() => setTimeRange("30d")}
            >
              {t("metrics.providers.time_30d")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant={timeRange === "all" ? "default" : "ghost"}
              className="rounded-sm px-3 text-xs"
              onClick={() => setTimeRange("all")}
            >
              {t("metrics.providers.time_all")}
            </Button>
          </div>
        </div>
        {loading && (
          <span className="text-xs text-muted-foreground">
            {t("metrics.providers.loading")}
          </span>
        )}
      </div>

      <div className="border rounded-lg bg-card">
        <ProvidersMetricsTable items={items} />
      </div>
    </div>
  );
}
