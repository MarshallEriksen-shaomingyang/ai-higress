"use client";

import React from "react";
import { StatsGrid } from "@/components/dashboard/overview/stats-grid";
import { ActiveProviders } from "@/components/dashboard/overview/active-providers";
import { RecentActivity } from "@/components/dashboard/overview/recent-activity";
import { GatewayConfigCard } from "@/components/dashboard/overview/gateway-config-card";
import { useI18n } from "@/lib/i18n-context";

export default function OverviewPage() {
    const { t } = useI18n();

    return (
        <div className="space-y-8 max-w-7xl">
            <div>
                <h1 className="text-3xl font-bold mb-2">{t("overview.title")}</h1>
                <p className="text-muted-foreground">{t("overview.subtitle")}</p>
            </div>

            {/* Stats Grid */}
            <StatsGrid />

            {/* Gateway configuration (visible to all logged-in users) */}
            <GatewayConfigCard />

            {/* Active Providers */}
            <ActiveProviders />

            {/* Recent Activity */}
            <RecentActivity />
        </div>
    );
}
