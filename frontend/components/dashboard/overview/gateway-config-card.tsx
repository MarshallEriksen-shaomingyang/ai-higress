"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useGatewayConfig } from "@/lib/swr";
import { useI18n } from "@/lib/i18n-context";

export function GatewayConfigCard() {
  const { t } = useI18n();
  const { config, loading, error } = useGatewayConfig();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("overview.gateway_config_title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {error && (
          <p className="text-red-500">{t("overview.gateway_config_error")}</p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <div className="text-muted-foreground">
              {t("overview.gateway_api_base_url")}
            </div>
            <div className="font-mono text-xs break-all">
              {loading && !config ? "…" : config?.api_base_url ?? "--"}
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-muted-foreground">
              {t("overview.gateway_max_concurrent")}
            </div>
            <div className="font-medium">
              {loading && !config ? "…" : config?.max_concurrent_requests ?? "--"}
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-muted-foreground">
              {t("overview.gateway_timeout_ms")}
            </div>
            <div className="font-medium">
              {loading && !config ? "…" : config?.request_timeout_ms ?? "--"}
            </div>
          </div>
          <div className="space-y-1">
            <div className="text-muted-foreground">
              {t("overview.gateway_cache_ttl")}
            </div>
            <div className="font-medium">
              {loading && !config ? "…" : config?.cache_ttl_seconds ?? "--"}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

