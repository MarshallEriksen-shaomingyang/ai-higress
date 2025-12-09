"use client";

import React from "react";
import { MetricsCards } from "@/components/dashboard/metrics/metrics-cards";
import { MetricsCharts } from "@/components/dashboard/metrics/metrics-charts";
import { ProviderPerformance } from "@/components/dashboard/metrics/provider-performance";
import { useI18n } from "@/lib/i18n-context";

export default function MetricsPage() {
    const { t } = useI18n();

    return (
        <div className="space-y-6 max-w-7xl">
            <div>
                <h1 className="text-3xl font-bold mb-2">
                    {t("metrics.overview.title")}
                </h1>
                <p className="text-muted-foreground">
                    {t("metrics.overview.subtitle")}
                </p>
            </div>

            {/* Key Metrics */}
            <MetricsCards />

            {/* Charts */}
            <MetricsCharts />

            {/* Provider Performance */}
            <ProviderPerformance />
        </div>
    );
}
