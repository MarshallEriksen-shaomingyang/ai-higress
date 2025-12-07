"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowLeft, CheckCircle, AlertCircle, XCircle, RefreshCw, Share2, Loader2, Key } from "lucide-react";
import { useProviderDetail } from "@/lib/hooks/use-provider-detail";
import type { ProviderStatus, ProviderModelPricing, Model } from "@/http/provider";
import { providerService } from "@/http/provider";
import { useI18n } from "@/lib/i18n-context";
import { providerSubmissionService } from "@/http/provider-submission";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { useAuthStore } from "@/lib/stores/auth-store";

interface ProviderDetailClientProps {
  providerId: string;
  currentUserId?: string | null;
  translations: {
    back: string;
    refresh: string;
    loading: string;
    error: string;
    retry: string;
    notFound: string;
    status: {
      healthy: string;
      degraded: string;
      down: string;
      unknown: string;
    };
    tabs: {
      overview: string;
      models: string;
      keys: string;
      metrics: string;
    };
    overview: {
      totalRequests: string;
      avgLatency: string;
      errorRate: string;
      configuration: string;
      baseUrl: string;
      transport: string;
      sdkVendor: string;
      modelsPath: string;
      chatPath: string;
      messagesPath: string;
      region: string;
      maxQps: string;
      weight: string;
      billingFactor: string;
    };
    models: {
      title: string;
      description: string;
      noModels: string;
      ownedBy: string;
      created: string;
    };
    keys: {
      title: string;
      description: string;
      noKeys: string;
      unnamed: string;
      weight: string;
      maxQps: string;
    };
    metrics: {
      title: string;
      description: string;
      noMetrics: string;
      lastUpdated: string;
      requests: string;
      successRate: string;
      p95Latency: string;
      p99Latency: string;
    };
    visibility: {
      private: string;
      public: string;
    };
  };
}

// 状态徽章组件
const StatusBadge = ({ 
  status, 
  translations 
}: { 
  status: ProviderStatus | undefined;
  translations: ProviderDetailClientProps['translations']['status'];
}) => {
  if (!status) {
    return (
      <Badge variant="outline" className="gap-1.5">
        <AlertCircle className="w-3.5 h-3.5" />
        {translations.unknown}
      </Badge>
    );
  }

  const statusConfig = {
    healthy: {
      icon: CheckCircle,
      label: translations.healthy,
      variant: "default" as const,
      className: "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800",
    },
    degraded: {
      icon: AlertCircle,
      label: translations.degraded,
      variant: "outline" as const,
      className: "bg-yellow-50 text-yellow-700 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-400 dark:border-yellow-800",
    },
    down: {
      icon: XCircle,
      label: translations.down,
      variant: "destructive" as const,
      className: "bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800",
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <Badge variant={config.variant} className={`gap-1.5 ${config.className}`}>
      <Icon className="w-3.5 h-3.5" />
      {config.label}
    </Badge>
  );
};

// 加载骨架屏组件
const LoadingSkeleton = ({ loadingText }: { loadingText: string }) => (
  <div className="space-y-6 max-w-7xl">
    <div className="flex items-center gap-4">
      <Skeleton className="h-10 w-10 rounded-md" />
      <div className="space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
      </div>
    </div>
    <div className="text-center text-muted-foreground">{loadingText}</div>
    <Skeleton className="h-[600px] w-full rounded-lg" />
  </div>
);

export function ProviderDetailClient({ providerId, currentUserId, translations }: ProviderDetailClientProps) {
  const router = useRouter();
  const { t } = useI18n();
  const { showError } = useErrorDisplay();
  const authUser = useAuthStore((state) => state.user);
  const authUserId = authUser?.id ?? null;
  const isSuperuser = authUser?.is_superuser ?? false;
  const effectiveUserId = currentUserId ?? authUserId;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isUserOwnedPrivate, setIsUserOwnedPrivate] = useState<boolean | null>(null);
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  const [pricingDraft, setPricingDraft] = useState<{ input: string; output: string }>({
    input: "",
    output: "",
  });
  const [pricingLoading, setPricingLoading] = useState(false);
  const { provider, models, health, metrics, loading, error, refresh } = useProviderDetail({
    providerId,
  });

  // 额外检查：当前 provider 是否为「当前用户的私有 Provider」
  // /providers/{id} 返回的是 ProviderConfig，并不包含 visibility/owner_id，
  // 这里通过用户私有提供商列表再做一次确认，避免按钮误判。
  useEffect(() => {
    if (!effectiveUserId) {
      setIsUserOwnedPrivate(false);
      return;
    }

    let cancelled = false;

    const checkPrivateOwnership = async () => {
      try {
        const list = await providerService.getUserPrivateProviders(effectiveUserId);
        const match = list.find((p) => p.provider_id === providerId);
        if (!cancelled) {
          setIsUserOwnedPrivate(!!match);
        }
      } catch (err) {
        console.error("Failed to load user private providers for detail:", err);
        if (!cancelled) {
          setIsUserOwnedPrivate(false);
        }
      }
    };

    checkPrivateOwnership();

    return () => {
      cancelled = true;
    };
  }, [effectiveUserId, providerId]);

  // 计算汇总指标
  const summaryMetrics = useMemo(() => {
    if (!metrics?.metrics || metrics.metrics.length === 0) {
      return {
        totalRequests: 0,
        avgLatency: 0,
        errorRate: 0,
      };
    }

    const totalRequests = metrics.metrics.reduce((acc, m) => acc + (m.total_requests_1m || 0), 0);
    const avgLatency = metrics.metrics.reduce((acc, m) => acc + (m.avg_latency_ms || 0), 0) / metrics.metrics.length;
    const totalFailures = metrics.metrics.reduce((acc, m) => acc + ((m.total_requests_1m || 0) * m.error_rate), 0);
    const errorRate = totalRequests > 0 ? (totalFailures / totalRequests) * 100 : 0;

    return {
      totalRequests,
      avgLatency: avgLatency.toFixed(0),
      errorRate: errorRate.toFixed(2),
    };
  }, [metrics]);

  // 将模型的计费配置格式化为简短文案，供模型卡片展示。
  const renderPricingLabel = (model: Model): string => {
    const rawPricing = (model.pricing || {}) as Record<string, number>;
    const input = typeof rawPricing["input"] === "number" ? rawPricing["input"] : undefined;
    const output = typeof rawPricing["output"] === "number" ? rawPricing["output"] : undefined;

    if (input != null && output != null) {
      return t("providers.pricing_summary_both")
        .replace("{input}", String(input))
        .replace("{output}", String(output));
    }
    if (input != null) {
      return t("providers.pricing_summary_input").replace("{input}", String(input));
    }
    if (output != null) {
      return t("providers.pricing_summary_output").replace("{output}", String(output));
    }
    // 未配置时仍显示原先的提示文案。
    return t("providers.pricing_label");
  };

  // 加载状态
  if (loading && !provider) {
    return <LoadingSkeleton loadingText={translations.loading} />;
  }

  // 错误状态
  if (error && !provider) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
        <Alert variant="destructive" className="max-w-md">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {translations.error}: {error.message || "Unknown error"}
          </AlertDescription>
        </Alert>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {translations.back}
          </Button>
          <Button onClick={refresh}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {translations.retry}
          </Button>
        </div>
      </div>
    );
  }

  // 未找到提供商
  if (!provider) {
    return (
      <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
        <div className="text-xl font-semibold">{translations.notFound}</div>
        <Button onClick={() => router.back()}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          {translations.back}
        </Button>
      </div>
    );
  }

  const canShareToPool =
    !!effectiveUserId &&
    (isUserOwnedPrivate ||
      (provider.visibility === "private" &&
        provider.owner_id === effectiveUserId));

  const canManageKeys =
    isSuperuser || (!!effectiveUserId && isUserOwnedPrivate);

  const handleShareToPool = async () => {
    if (!canShareToPool || !effectiveUserId) {
      return;
    }

    setIsSubmitting(true);
    try {
      await providerSubmissionService.submitFromPrivateProvider(
        effectiveUserId,
        providerId,
      );
      toast.success(t("submissions.toast_submit_success"));
    } catch (error: any) {
      // 权限不足的场景给出更明确的提示
      if (error?.response?.status === 403) {
        toast.error(t("submissions.toast_no_permission"));
      } else {
        showError(error, {
          context: t("submissions.toast_submit_error"),
          onRetry: () => handleShareToPool(),
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const openPricingEditor = async (modelId: string) => {
    // 这里使用路由参数传入的 providerId 作为短 ID（与后端 Provider.provider_id 对齐）
    if (!providerId) return;
    setEditingModelId(modelId);
    setPricingLoading(true);
    try {
      let pricing: ProviderModelPricing | null = null;
      try {
        pricing = await providerService.getProviderModelPricing(providerId, modelId);
      } catch (err: any) {
        // 若后端尚未为该模型创建配置（404），视为暂无定价。
        if (err?.response?.status !== 404) {
          throw err;
        }
      }
      setPricingDraft({
        input: pricing?.pricing?.input != null ? String(pricing.pricing.input) : "",
        output: pricing?.pricing?.output != null ? String(pricing.pricing.output) : "",
      });
    } catch (err: any) {
      showError(err, {
        context: t("providers.pricing_load_error") ?? "加载计费配置失败",
      });
      setEditingModelId(null);
    } finally {
      setPricingLoading(false);
    }
  };

  const savePricing = async () => {
    if (!providerId || !editingModelId) return;
    setPricingLoading(true);
    try {
      const payload: { input?: number; output?: number } = {};
      if (pricingDraft.input.trim() !== "") {
        payload.input = Number(pricingDraft.input);
      }
      if (pricingDraft.output.trim() !== "") {
        payload.output = Number(pricingDraft.output);
      }
      // 若两者都为空，则传 null 表示清空定价。
      const body = Object.keys(payload).length > 0 ? payload : null;
      await providerService.updateProviderModelPricing(providerId, editingModelId, body);
      toast.success(t("providers.pricing_save_success") ?? "计费配置已保存");
      // 保存成功后刷新 Provider 详情与模型列表，以便卡片展示最新计费配置。
      await refresh();
      setEditingModelId(null);
    } catch (err: any) {
      showError(err, {
        context: t("providers.pricing_save_error") ?? "保存计费配置失败",
      });
    } finally {
      setPricingLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl animate-in fade-in duration-500">
      {/* 页头 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{provider.name}</h1>
            <div className="flex items-center gap-2 text-muted-foreground mt-1">
              <code className="text-sm font-mono bg-muted px-2 py-0.5 rounded">
                {provider.provider_id}
              </code>
              <span>•</span>
              <span className="text-sm capitalize">{provider.provider_type}</span>
              {provider.visibility && (
                <>
                  <span>•</span>
                  <Badge variant="outline" className="text-xs">
                    {provider.visibility === "private" 
                      ? `🔒 ${translations.visibility.private}` 
                      : `🌐 ${translations.visibility.public}`}
                  </Badge>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canShareToPool && (
            <Button
              variant="default"
              size="sm"
              onClick={handleShareToPool}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("submissions.btn_submitting")}
                </>
              ) : (
                <>
                  <Share2 className="h-4 w-4 mr-2" />
                  {t("submissions.share_from_private_button")}
                </>
              )}
            </Button>
          )}
          <StatusBadge status={health?.status} translations={translations.status} />
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            {translations.refresh}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">{translations.tabs.overview}</TabsTrigger>
          <TabsTrigger value="models">
            {translations.tabs.models} ({models?.models?.length || 0})
          </TabsTrigger>
          <TabsTrigger value="keys">{translations.tabs.keys}</TabsTrigger>
          <TabsTrigger value="metrics">{translations.tabs.metrics}</TabsTrigger>
        </TabsList>

        {/* 概览标签页 */}
        <TabsContent value="overview" className="space-y-6">
          {/* 汇总指标卡片 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {translations.overview.totalRequests}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summaryMetrics.totalRequests}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {translations.overview.avgLatency}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summaryMetrics.avgLatency} ms</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {translations.overview.errorRate}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{summaryMetrics.errorRate}%</div>
              </CardContent>
            </Card>
          </div>

          {/* 配置信息卡片 */}
          <Card>
            <CardHeader>
              <CardTitle>{translations.overview.configuration}</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.baseUrl}</div>
                <code className="text-sm p-2 bg-muted rounded block break-all">
                  {provider.base_url}
                </code>
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.transport}</div>
                <div className="capitalize p-2">{provider.transport}</div>
              </div>
              {provider.sdk_vendor && (
                <div className="space-y-1">
                  <div className="text-sm font-medium text-muted-foreground">{translations.overview.sdkVendor}</div>
                  <div className="capitalize p-2">{provider.sdk_vendor}</div>
                </div>
              )}
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.modelsPath}</div>
                <code className="text-sm p-2 bg-muted rounded block break-all">
                  {provider.models_path}
                </code>
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.chatPath}</div>
                <code className="text-sm p-2 bg-muted rounded block break-all">
                  {provider.chat_completions_path}
                </code>
              </div>
              {provider.messages_path && (
                <div className="space-y-1">
                  <div className="text-sm font-medium text-muted-foreground">{translations.overview.messagesPath}</div>
                  <code className="text-sm p-2 bg-muted rounded block break-all">
                    {provider.messages_path}
                  </code>
                </div>
              )}
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.region}</div>
                <div className="text-sm p-2">{provider.region || "-"}</div>
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.maxQps}</div>
                <div className="text-sm p-2">{provider.max_qps || "-"}</div>
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.weight}</div>
                <div className="text-sm p-2">{provider.weight}</div>
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium text-muted-foreground">{translations.overview.billingFactor}</div>
                <div className="text-sm p-2">{provider.billing_factor}</div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* 模型标签页 */}
        <TabsContent value="models">
          <Card>
            <CardHeader>
              <CardTitle>{translations.models.title}</CardTitle>
              <CardDescription>{translations.models.description}</CardDescription>
            </CardHeader>
            <CardContent>
              {!models?.models || models.models.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">{translations.models.noModels}</div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {models.models.map((model) => (
                    <div
                      key={model.model_id}
                      className="p-4 border rounded-lg hover:bg-muted/50 transition-colors flex flex-col justify-between gap-3"
                    >
                      <div>
                        <div className="font-medium break-all">
                          {model.display_name || model.model_id}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {translations.models.ownedBy}:{" "}
                          {model.metadata?.owned_by || "-"}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {translations.models.created}:{" "}
                          {typeof model.metadata?.created === "number"
                            ? new Date(
                                model.metadata.created * 1000,
                              ).toLocaleDateString()
                            : "-"}
                        </div>
                      </div>
                      <div className="flex items-center justify-between gap-2 pt-2 border-t mt-2">
                        <div className="text-xs text-muted-foreground">
                          {renderPricingLabel(model)}
                        </div>
                        <Button
                          variant="outline"
                          size="xs"
                          onClick={() => openPricingEditor(model.model_id)}
                        >
                          {t("providers.pricing_edit_button") ?? "编辑计费"}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* API 密钥标签页 */}
        <TabsContent value="keys">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>{translations.keys.title}</CardTitle>
                <CardDescription>{translations.keys.description}</CardDescription>
              </div>
              {canManageKeys && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push(`/dashboard/providers/${providerId}/keys`)}
                >
                  <Key className="w-4 h-4 mr-1" />
                  {t("providers.action_manage_keys")}
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {!provider.api_keys || provider.api_keys.length === 0 ? (
                <div className="text-sm text-muted-foreground py-8 text-center">
                  {translations.keys.noKeys}
                </div>
              ) : (
                <div className="space-y-4">
                  {provider.api_keys.map((key, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-4 border rounded-lg"
                    >
                      <div>
                        <div className="font-medium">{key.label || translations.keys.unnamed}</div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {translations.keys.weight}: {key.weight} | {translations.keys.maxQps}: {key.max_qps}
                        </div>
                      </div>
                      <code className="text-sm font-mono bg-muted px-2 py-1 rounded">
                        {key.key.substring(0, 8)}...
                      </code>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 指标详情标签页 */}
        <TabsContent value="metrics">
          <Card>
            <CardHeader>
              <CardTitle>{translations.metrics.title}</CardTitle>
              <CardDescription>{translations.metrics.description}</CardDescription>
            </CardHeader>
            <CardContent>
              {!metrics?.metrics || metrics.metrics.length === 0 ? (
                <div className="text-sm text-muted-foreground py-8 text-center">
                  {translations.metrics.noMetrics}
                </div>
              ) : (
                <div className="space-y-4">
                  {metrics.metrics.map((metric, index) => (
                    <div key={index} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <div className="font-medium">{metric.logical_model}</div>
                        <div className="text-xs text-muted-foreground">
                          {translations.metrics.lastUpdated}: {new Date(metric.last_updated * 1000).toLocaleTimeString()}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <div className="text-muted-foreground">{translations.metrics.requests}</div>
                          <div className="font-mono">{metric.total_requests_1m}</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">{translations.metrics.successRate}</div>
                          <div className="font-mono">
                            {((1 - metric.error_rate) * 100).toFixed(1)}%
                          </div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">{translations.metrics.p95Latency}</div>
                          <div className="font-mono">{metric.latency_p95_ms.toFixed(0)}ms</div>
                        </div>
                        <div>
                          <div className="text-muted-foreground">{translations.metrics.p99Latency}</div>
                          <div className="font-mono">{metric.latency_p99_ms.toFixed(0)}ms</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 计费编辑对话框（简单版：使用原生布局，不引入额外 Dialog 组件以减少改动） */}
      {editingModelId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-background rounded-lg shadow-lg w-full max-w-md p-6 space-y-4">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold">
                {t("providers.pricing_edit_title") ?? "编辑模型计费"}
              </h2>
              <p className="text-xs text-muted-foreground break-all">
                {provider?.provider_id} · {editingModelId}
              </p>
              <p className="text-xs text-muted-foreground">
                {t("providers.pricing_edit_desc") ??
                  "单位为每 1000 tokens 扣减的积分数，留空表示不配置 / 清空对应方向的价格。"}
              </p>
            </div>
            <div className="space-y-3">
              <div className="space-y-1">
                <div className="text-xs font-medium text-muted-foreground">
                  {t("providers.pricing_input_label") ?? "输入价格（每 1k tokens）"}
                </div>
                <input
                  className="w-full rounded-md border px-2 py-1 text-sm bg-background"
                  value={pricingDraft.input}
                  onChange={(e) =>
                    setPricingDraft((prev) => ({ ...prev, input: e.target.value }))
                  }
                  placeholder={t("providers.pricing_input_placeholder") ?? "例如 5"}
                />
              </div>
              <div className="space-y-1">
                <div className="text-xs font-medium text-muted-foreground">
                  {t("providers.pricing_output_label") ?? "输出价格（每 1k tokens）"}
                </div>
                <input
                  className="w-full rounded-md border px-2 py-1 text-sm bg-background"
                  value={pricingDraft.output}
                  onChange={(e) =>
                    setPricingDraft((prev) => ({ ...prev, output: e.target.value }))
                  }
                  placeholder={t("providers.pricing_output_placeholder") ?? "例如 15"}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setEditingModelId(null)}
                disabled={pricingLoading}
              >
                {t("common.cancel") ?? "取消"}
              </Button>
              <Button size="sm" onClick={savePricing} disabled={pricingLoading}>
                {pricingLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    {t("common.saving") ?? "保存中"}
                  </>
                ) : (
                  t("common.save") ?? "保存"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
