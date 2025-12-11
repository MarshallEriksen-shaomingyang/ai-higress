"use client";

import type { ElementType } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowUpRight, ArrowDownRight } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";

interface StatCardProps {
  titleKey: string;
  value: string;
  change: string;
  trend: "up" | "down";
  icon: ElementType;
}

export function StatCard({ titleKey, value, change, trend, icon: Icon }: StatCardProps) {
  const { t } = useI18n();

  return (
    <Card className="border-none shadow-sm">
      <CardContent className="pt-6 pb-6">
        <div className="flex items-start justify-between mb-4">
          <p className="text-xs text-muted-foreground uppercase tracking-wider">
            {t(titleKey)}
          </p>
          <Icon className="w-4 h-4 text-muted-foreground" />
        </div>
        <div className="space-y-2">
          <h3 className="text-4xl font-light tracking-tight">{value}</h3>
          <div className="flex items-center text-xs">
            {trend === "up" ? (
              <ArrowUpRight className="w-3 h-3 text-muted-foreground mr-1" />
            ) : (
              <ArrowDownRight className="w-3 h-3 text-muted-foreground mr-1" />
            )}
            <span className="text-muted-foreground">
              {change}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface ProviderStatusProps {
  name: string;
  statusKey: string;
  latency: string;
  success: string;
}

export function ProviderStatusCard({ name, statusKey, latency, success }: ProviderStatusProps) {
  const { t } = useI18n();

  return (
    <Card className="border-none shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">{name}</CardTitle>
          <span
            className={`h-2 w-2 rounded-full ${
              statusKey === "overview.status_healthy"
                ? "bg-green-500"
                : "bg-yellow-500"
            }`}
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 text-xs">
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground uppercase tracking-wide">{t("table.latency")}</span>
            <span className="font-light">{latency}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-muted-foreground uppercase tracking-wide">{t("table.success_rate")}</span>
            <span className="font-light">{success}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
