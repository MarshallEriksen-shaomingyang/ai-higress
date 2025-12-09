'use client';

import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Database } from "lucide-react";
import type { GatewayConfig, ProviderLimits } from "@/lib/api-types";
import { useGatewayConfig, useProviderLimits } from "@/lib/swr";
import { systemService, type CacheSegment } from "@/http";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";

export default function SystemAdminPage() {
  const { t } = useI18n();
  const { config, loading, saving, error, saveConfig, refresh } = useGatewayConfig();
  const {
    limits,
    loading: limitsLoading,
    saving: limitsSaving,
    error: limitsError,
    saveLimits,
    refresh: refreshLimits,
  } = useProviderLimits();
  const [form, setForm] = useState<GatewayConfig | null>(null);
  const [limitForm, setLimitForm] = useState<ProviderLimits | null>(null);
  const [clearing, setClearing] = useState(false);
  const [selectedSegments, setSelectedSegments] = useState<CacheSegment[]>([
    "models",
    "metrics_overview",
    "provider_models",
    "logical_models",
    "routing_metrics",
  ]);

  // 同步后端配置到表单
  useEffect(() => {
    if (config) {
      setForm(config);
    }
  }, [config]);

  useEffect(() => {
    if (limits) {
      setLimitForm(limits);
    }
  }, [limits]);

  const handleChange =
    (field: keyof GatewayConfig) => (event: React.ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value;

      setForm((prev) => {
        if (!prev) {
          return prev;
        }

        if (field === "max_concurrent_requests" || field === "request_timeout_ms" || field === "cache_ttl_seconds") {
          const parsed = value === "" ? 0 : Number(value);
          return {
            ...prev,
            [field]: Number.isNaN(parsed) ? prev[field] : parsed,
          };
        }

        return {
          ...prev,
          [field]: value,
        };
      });
    };

  const handleReset = () => {
    if (config) {
      setForm(config);
    }
  };

  const handleLimitReset = () => {
    if (limits) {
      setLimitForm(limits);
    }
  };

  const handleSave = async () => {
    if (!form) return;
    try {
      const updated = await saveConfig(form);
      setForm(updated);
      await refresh();
      toast.success(t("system.config.save_success"));
    } catch (e: any) {
      const message =
        e?.response?.data?.detail || e?.message || t("system.config.save_error");
      toast.error(message);
    }
  };

  const disabled = loading || saving || !form;
  const limitsDisabled = limitsLoading || limitsSaving || !limitForm;

  const handleLimitChange =
    (field: keyof ProviderLimits) => (event: React.ChangeEvent<HTMLInputElement>) => {
      const value = field === "require_approval_for_shared_providers"
        ? (event.target as HTMLInputElement).checked
        : event.target.value;

      setLimitForm((prev) => {
        if (!prev) return prev;
        if (field === "require_approval_for_shared_providers") {
          return { ...prev, [field]: Boolean(value) };
        }
        const parsed = value === "" ? 0 : Number(value);
        if (Number.isNaN(parsed)) {
          return prev;
        }
        return { ...prev, [field]: parsed };
      });
    };

  const handleLimitSave = async () => {
    if (!limitForm) return;
    try {
      const updated = await saveLimits(limitForm);
      setLimitForm(updated);
      await refreshLimits();
      toast.success(t("system.provider_limits.save_success"));
    } catch (e: any) {
      const message =
        e?.response?.data?.detail || e?.message || t("system.provider_limits.save_error");
      toast.error(message);
    }
  };

  const handleClearCache = async () => {
    if (!selectedSegments.length) {
      toast.error(t("system.cache_segment.none_selected"));
      return;
    }
    try {
      setClearing(true);
      await systemService.clearCache(selectedSegments);
      toast.success(t("system.maintenance.clear_cache_success"));
    } catch (e: any) {
      const message =
        e?.response?.data?.detail || e?.message || t("system.maintenance.clear_cache_error");
      toast.error(message);
    } finally {
      setClearing(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-3xl font-bold mb-2">{t("system.admin.title")}</h1>
        <p className="text-muted-foreground">{t("system.admin.subtitle")}</p>
      </div>

      {/* Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>{t("system.config.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <p className="text-sm text-red-500">
              {t("system.config.load_error")}
            </p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("system.config.api_base_url")}
              </label>
              <Input
                placeholder="https://api.example.com"
                value={form?.api_base_url ?? ""}
                onChange={handleChange("api_base_url")}
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("system.config.max_concurrent")}
              </label>
              <Input
                type="number"
                placeholder="1000"
                value={form?.max_concurrent_requests ?? ""}
                onChange={handleChange("max_concurrent_requests")}
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("system.config.request_timeout_ms")}
              </label>
              <Input
                type="number"
                placeholder="30000"
                value={form?.request_timeout_ms ?? ""}
                onChange={handleChange("request_timeout_ms")}
                disabled={disabled}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("system.config.cache_ttl_seconds")}
              </label>
              <Input
                type="number"
                placeholder="3600"
                value={form?.cache_ttl_seconds ?? ""}
                onChange={handleChange("cache_ttl_seconds")}
                disabled={disabled}
              />
            </div>
          </div>
          <div className="flex justify-end space-x-2 pt-4">
            <Button variant="outline" onClick={handleReset} disabled={disabled}>
              {t("system.config.reset")}
            </Button>
            <Button onClick={handleSave} disabled={disabled}>
              {saving ? t("system.config.saving") : t("system.config.save")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Provider Limits */}
      <Card>
        <CardHeader>
          <CardTitle>{t("system.provider_limits.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {limitsError && (
            <p className="text-sm text-red-500">
              {t("system.provider_limits.load_error")}
            </p>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("system.provider_limits.default_limit")}
              </label>
              <Input
                type="number"
                min={0}
                value={limitForm?.default_user_private_provider_limit ?? ""}
                onChange={handleLimitChange("default_user_private_provider_limit")}
                disabled={limitsDisabled}
              />
              <p className="text-xs text-muted-foreground">
                {t("system.provider_limits.default_hint")}
              </p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t("system.provider_limits.max_limit")}
              </label>
              <Input
                type="number"
                min={0}
                value={limitForm?.max_user_private_provider_limit ?? ""}
                onChange={handleLimitChange("max_user_private_provider_limit")}
                disabled={limitsDisabled}
              />
              <p className="text-xs text-muted-foreground">
                {t("system.provider_limits.max_hint")}
              </p>
            </div>
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">
                {t("system.provider_limits.require_approval")}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("system.provider_limits.require_approval_hint")}
              </p>
            </div>
            <Switch
              checked={limitForm?.require_approval_for_shared_providers ?? false}
              onCheckedChange={(checked) =>
                setLimitForm((prev) =>
                  prev
                    ? { ...prev, require_approval_for_shared_providers: checked }
                    : prev
                )
              }
              disabled={limitsDisabled}
            />
          </div>
          <div className="flex justify-end space-x-2 pt-4">
            <Button variant="outline" onClick={handleLimitReset} disabled={limitsDisabled}>
              {t("system.config.reset")}
            </Button>
            <Button onClick={handleLimitSave} disabled={limitsDisabled}>
              {limitsSaving ? t("system.config.saving") : t("system.config.save")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Maintenance */}
      <Card>
        <CardHeader>
          <CardTitle>{t("system.maintenance.title")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <div>
            <p className="text-sm text-muted-foreground mb-4">
              {t("system.cache_segment.select_hint")}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <label className="flex items-center gap-3 p-3 rounded-lg border transition-colors hover:bg-muted/50 cursor-pointer">
                <Checkbox
                  checked={selectedSegments.includes("models")}
                  onCheckedChange={(checked) =>
                    setSelectedSegments((prev) =>
                      checked
                        ? [...prev, "models"]
                        : prev.filter((item) => item !== "models")
                    )
                  }
                />
                <span className="text-sm">{t("system.cache_segment.models")}</span>
              </label>
              <label className="flex items-center gap-3 p-3 rounded-lg border transition-colors hover:bg-muted/50 cursor-pointer">
                <Checkbox
                  checked={selectedSegments.includes("metrics_overview")}
                  onCheckedChange={(checked) =>
                    setSelectedSegments((prev) =>
                      checked
                        ? [...prev, "metrics_overview"]
                        : prev.filter((item) => item !== "metrics_overview")
                    )
                  }
                />
                <span className="text-sm">{t("system.cache_segment.metrics_overview")}</span>
              </label>
              <label className="flex items-center gap-3 p-3 rounded-lg border transition-colors hover:bg-muted/50 cursor-pointer">
                <Checkbox
                  checked={selectedSegments.includes("provider_models")}
                  onCheckedChange={(checked) =>
                    setSelectedSegments((prev) =>
                      checked
                        ? [...prev, "provider_models"]
                        : prev.filter((item) => item !== "provider_models")
                    )
                  }
                />
                <span className="text-sm">{t("system.cache_segment.provider_models")}</span>
              </label>
              <label className="flex items-center gap-3 p-3 rounded-lg border transition-colors hover:bg-muted/50 cursor-pointer">
                <Checkbox
                  checked={selectedSegments.includes("logical_models")}
                  onCheckedChange={(checked) =>
                    setSelectedSegments((prev) =>
                      checked
                        ? [...prev, "logical_models"]
                        : prev.filter((item) => item !== "logical_models")
                    )
                  }
                />
                <span className="text-sm">{t("system.cache_segment.logical_models")}</span>
              </label>
              <label className="flex items-center gap-3 p-3 rounded-lg border transition-colors hover:bg-muted/50 cursor-pointer">
                <Checkbox
                  checked={selectedSegments.includes("routing_metrics")}
                  onCheckedChange={(checked) =>
                    setSelectedSegments((prev) =>
                      checked
                        ? [...prev, "routing_metrics"]
                        : prev.filter((item) => item !== "routing_metrics")
                    )
                  }
                />
                <span className="text-sm">{t("system.cache_segment.routing_metrics")}</span>
              </label>
            </div>
          </div>
          
          <div className="pt-4 border-t">
            <Button
              variant="outline"
              size="lg"
              className="w-full md:w-auto"
              onClick={handleClearCache}
              disabled={clearing || selectedSegments.length === 0}
            >
              <Database className="w-4 h-4 mr-2" />
              {clearing
                ? t("system.maintenance.clearing")
                : t("system.maintenance.clear_cache")}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
