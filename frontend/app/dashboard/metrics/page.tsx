"use client";

import React from "react";
import { MetricsCards } from "@/components/dashboard/metrics/metrics-cards";
import { MetricsCharts } from "@/components/dashboard/metrics/metrics-charts";
import { ProviderPerformance } from "@/components/dashboard/metrics/provider-performance";

export default function MetricsPage() {
    return (
        <div className="space-y-6 max-w-7xl">
            <div>
                <h1 className="text-3xl font-bold mb-2">System Metrics</h1>
                <p className="text-muted-foreground">Real-time performance monitoring</p>
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
