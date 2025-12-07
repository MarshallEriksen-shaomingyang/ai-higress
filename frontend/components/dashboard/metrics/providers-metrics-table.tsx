"use client";

import React from "react";
import type { ActiveProviderMetrics } from "@/lib/api-types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useI18n } from "@/lib/i18n-context";

function formatNumber(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return value.toString();
}

function formatPercent01(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMs(value: number | null): string {
  if (value == null) {
    return "--";
  }
  return `${Math.round(value)} ms`;
}

interface ProvidersMetricsTableProps {
  items: ActiveProviderMetrics[];
}

export function ProvidersMetricsTable({ items }: ProvidersMetricsTableProps) {
  const { t } = useI18n();
  if (!items.length) {
    return (
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        {t("metrics.providers.empty")}
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>
            {t("metrics.providers.column.provider")}
          </TableHead>
          <TableHead className="text-right">
            {t("metrics.providers.column.total_requests")}
          </TableHead>
          <TableHead className="text-right">
            {t("metrics.providers.column.success_rate")}
          </TableHead>
          <TableHead className="text-right">
            {t("metrics.providers.column.error_rate")}
          </TableHead>
          <TableHead className="text-right">
            {t("metrics.providers.column.latency_p95")}
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((item) => {
          const errorRate =
            item.total_requests > 0
              ? item.error_requests / item.total_requests
              : 0;
          return (
            <TableRow key={item.provider_id}>
              <TableCell className="font-medium">
                {item.provider_id}
              </TableCell>
              <TableCell className="text-right">
                {formatNumber(item.total_requests)}
              </TableCell>
              <TableCell className="text-right">
                {formatPercent01(item.success_rate)}
              </TableCell>
              <TableCell className="text-right">
                {formatPercent01(errorRate)}
              </TableCell>
              <TableCell className="text-right">
                {formatMs(item.latency_p95_ms)}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
