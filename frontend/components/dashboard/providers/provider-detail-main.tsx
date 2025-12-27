"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ArrowLeft, AlertCircle, RefreshCw, Share2, Loader2, Shield, CheckCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useProviderDetail } from "@/lib/hooks/use-provider-detail";
import { useProviderAudit } from "@/lib/hooks/use-provider-audit";
import type {
  ProviderAuditStatus,
  ProviderOperationStatus,
  ProviderTestResult,
  Model,
} from "@/http/provider";
import { providerService } from "@/http/provider";
import { useI18n } from "@/lib/i18n-context";
import { useMyProviderSubmissions } from "@/lib/swr";
import { providerSubmissionService } from "@/http/provider-submission";
import type { ProviderSubmission, SubmissionStatus } from "@/http/provider-submission";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { useAuthStore } from "@/lib/stores/auth-store";
import { ModelSettingsDialog } from "./model-settings-dialog";
import { StatusBadge } from "./status-badges";
import { ProviderOverviewTab } from "./provider-overview-tab";
import { ProviderSharingConfig } from "./provider-sharing-config";

type SubmissionLike = Pick<
  ProviderSubmission,
  "id" | "approval_status" | "created_at" | "updated_at"
>;

// 使用 dynamic 导入非首屏 Tab 组件
const ProviderModelsTab = dynamic(() => import("./provider-models-tab").then(mod => ({ default: mod.ProviderModelsTab })), {
  loading: () => <Skeleton className="h-[400px] w-full" />,
  ssr: false,
});

const ProviderKeysTab = dynamic(() => import("./provider-keys-tab").then(mod => ({ default: mod.ProviderKeysTab })), {
  loading: () => <Skeleton className="h-[400px] w-full" />,
  ssr: false,
});

const ProviderMetricsTab = dynamic(() => import("./provider-metrics-tab").then(mod => ({ default: mod.ProviderMetricsTab })), {
  loading: () => <Skeleton className="h-[400px] w-full" />,
  ssr: false,
});

const ProviderProbesTab = dynamic(() => import("./provider-probes-tab").then(mod => ({ default: mod.ProviderProbesTab })), {
  loading: () => <Skeleton className="h-[400px] w-full" />,
  ssr: false,
});

// 审计相关组件使用 dynamic 导入
const ProbeConfigDrawer = dynamic(() => import("./audit/probe-config-drawer").then(mod => ({ default: mod.ProbeConfigDrawer })), {
  loading: () => null,
  ssr: false,
});

const AuditTabContent = dynamic(() => import("./audit/audit-tab-content").then(mod => ({ default: mod.AuditTabContent })), {
  loading: () => <Skeleton className="h-[600px] w-full" />,
  ssr: false,
});

interface ProviderDetailClientProps {
  providerId: string;
  currentUserId?: string | null;
  translations: any;
}

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

const SHARE_STATUS_BADGE_META: Record<
  SubmissionStatus,
  {
    icon: LucideIcon;
    className: string;
    iconClassName?: string;
  }
> = {
  pending: {
    icon: Loader2,
    className:
      "gap-1.5 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-800",
    iconClassName: "animate-spin",
  },
  testing: {
    icon: Loader2,
    className:
      "gap-1.5 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-300 dark:border-amber-800",
    iconClassName: "animate-spin",
  },
  approved: {
    icon: CheckCircle,
    className:
      "gap-1.5 bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800",
  },
  approved_limited: {
    icon: CheckCircle,
    className:
      "gap-1.5 bg-green-50 text-green-700 border-green-200 dark:bg-green-900/20 dark:text-green-400 dark:border-green-800",
  },
  rejected: {
    icon: AlertCircle,
    className:
      "gap-1.5 bg-red-50 text-red-700 border-red-200 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800",
  },
};

export function ProviderDetailMain({ providerId, currentUserId, translations }: ProviderDetailClientProps) {
  const router = useRouter();
  const { t } = useI18n();
  const { showError } = useErrorDisplay();
  const authUser = useAuthStore((state) => state.user);
  const authUserId = authUser?.id ?? null;
  const isSuperuser = authUser?.is_superuser ?? false;
  const roleCodes = authUser?.role_codes ?? [];
  const isAdminUser =
    isSuperuser || roleCodes.includes("system_admin") || roleCodes.includes("admin");
  const effectiveUserId = currentUserId ?? authUserId;
  
  // 状态管理
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancellingSubmission, setIsCancellingSubmission] = useState(false);
  const [isUserOwnedPrivate, setIsUserOwnedPrivate] = useState<boolean>(false);
  const [settingsModel, setSettingsModel] = useState<Model | null>(null);
  const { provider, models, health, metrics, loading, error, refresh } = useProviderDetail({
    providerId,
  });

  // 使用审计管理 Hook
  const {
    auditRemark,
    setAuditRemark,
    rejectReason,
    setRejectReason,
    limitQps,
    setLimitQps,
    auditSubmitting,
    recentTests,
    setRecentTests,
    auditLogs,
    setAuditLogs,
    probeEnabled,
    setProbeEnabled,
    probeInterval,
    setProbeInterval,
    probeModel,
    setProbeModel,
    savingProbe,
    probeDrawerOpen,
    setProbeDrawerOpen,
    validationResults,
    validationLoading,
    handleAdminTest,
    handleSaveProbeConfig,
    handleValidateModels,
    handleApprove,
    handleReject,
    handleOperation,
  } = useProviderAudit({ providerId, refresh, translations });

  // 检查是否为用户私有 Provider
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

  // 同步探针配置
  useEffect(() => {
    if (!provider) return;
    setProbeEnabled(provider.probe_enabled ?? true);
    setProbeInterval(
      provider.probe_interval_seconds != null ? String(provider.probe_interval_seconds) : "",
    );
    setProbeModel(provider.probe_model ?? "");
  }, [provider]);

  // 计算权限
  const permissions = useMemo(() => {
    const hasEffectiveUserId = !!effectiveUserId;
    const providerVisibility = provider?.visibility;
    const providerOwnerId = provider?.owner_id;
    
    const canEditSharing = hasEffectiveUserId && isUserOwnedPrivate;
    const canManageAudit = isAdminUser;
    const isSharedPoolProvider = providerVisibility === "public";
    const canShowAuditUI = canManageAudit && isSharedPoolProvider;
    const canShareToPool = hasEffectiveUserId && 
      (isUserOwnedPrivate || 
       (providerVisibility === "private" && providerOwnerId === effectiveUserId));
    const canManageKeys = canManageAudit || (hasEffectiveUserId && isUserOwnedPrivate);
    const canEditModelMapping = canManageAudit || (hasEffectiveUserId && isUserOwnedPrivate);
    const canManageUserProbes = hasEffectiveUserId && isUserOwnedPrivate;
    
    return {
      canEditSharing,
      canManageAudit,
      canShowAuditUI,
      canShareToPool,
      canManageKeys,
      canEditModelMapping,
      canManageUserProbes,
    };
  }, [effectiveUserId, isUserOwnedPrivate, isAdminUser, provider?.visibility, provider?.owner_id]);

  const shouldLoadSubmissionStatus = !!provider?.provider_id && !!effectiveUserId;

  const {
    submissions: mySubmissions,
    loading: submissionStatusLoading,
    refresh: refreshSubmissionStatus,
  } = useMyProviderSubmissions(shouldLoadSubmissionStatus);

  const latestSubmissionFromApi = useMemo(() => {
    if (!shouldLoadSubmissionStatus || !provider?.provider_id || !mySubmissions?.length) {
      return null;
    }
    const sorted = [...mySubmissions].filter(
      (submission) => submission.provider_id === provider.provider_id,
    );
    if (sorted.length === 0) {
      return null;
    }
    return sorted.sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )[0];
  }, [mySubmissions, provider?.provider_id, shouldLoadSubmissionStatus]);

  const hasLoadedSubmissionList = mySubmissions !== undefined;
  const baseSubmission = useMemo<SubmissionLike | null>(() => {
    if (hasLoadedSubmissionList) {
      return latestSubmissionFromApi ?? null;
    }
    if (provider?.latest_submission) {
      return provider.latest_submission as SubmissionLike;
    }
    return null;
  }, [hasLoadedSubmissionList, latestSubmissionFromApi, provider?.latest_submission]);
  const [optimisticSubmission, setOptimisticSubmission] = useState<SubmissionLike | null>(null);
  const latestSubmission = optimisticSubmission ?? baseSubmission;

  useEffect(() => {
    if (
      optimisticSubmission &&
      baseSubmission &&
      optimisticSubmission.id === baseSubmission.id &&
      optimisticSubmission.approval_status === baseSubmission.approval_status
    ) {
      setOptimisticSubmission(null);
    }
  }, [optimisticSubmission, baseSubmission]);

  const shareStatusBadge = useMemo(() => {
    if (!latestSubmission) {
      return null;
    }
    const status = latestSubmission.approval_status as SubmissionStatus;
    const config = SHARE_STATUS_BADGE_META[status];
    const Icon = config.icon;
    const iconClasses = ["h-3.5", "w-3.5", config.iconClassName].filter(Boolean).join(" ");
    return (
      <Badge variant="outline" className={config.className}>
        <Icon className={iconClasses} />
        {t("submissions.share_status_prefix")} {t(`submissions.status_${status}`)}
      </Badge>
    );
  }, [latestSubmission, t]);

  const isAwaitingShareReview =
    !!latestSubmission &&
    (latestSubmission.approval_status === "pending" || latestSubmission.approval_status === "testing");
  const canDisplayShareButton =
    permissions.canShareToPool &&
    (!latestSubmission || latestSubmission.approval_status === "rejected");
  const canCancelSubmission =
    permissions.canShareToPool && !!latestSubmission && isAwaitingShareReview;
  const shareButtonLabel =
    latestSubmission?.approval_status === "rejected"
      ? t("submissions.share_again_button")
      : t("submissions.share_from_private_button");
  const shareButtonDisabled = isSubmitting || submissionStatusLoading;

  // 管理员加载测试记录与审核日志
  useEffect(() => {
    if (permissions.canShowAuditUI && providerId) {
      const load = async () => {
        try {
          const [tests, logs] = await Promise.all([
            providerService.getProviderTests(providerId, { limit: 5 }),
            providerService.getProviderAuditLogs(providerId, { limit: 10 }),
          ]);
          setRecentTests(tests || []);
          setAuditLogs(logs || []);
        } catch (err) {
          console.warn("Failed to load audit data", err);
        }
      };
      load();
    }
  }, [permissions.canShowAuditUI, providerId]);

  // 事件处理函数
  const handleShareToPool = useCallback(async () => {
    if (!canDisplayShareButton || !effectiveUserId) {
      return;
    }

    setIsSubmitting(true);
    try {
      const submission = await providerSubmissionService.submitFromPrivateProvider(
        effectiveUserId,
        providerId,
      );
      toast.success(t("submissions.toast_submit_success"));
      setOptimisticSubmission(submission);
      await Promise.all([
        shouldLoadSubmissionStatus ? refreshSubmissionStatus() : Promise.resolve(),
        refresh(),
      ]);
    } catch (error: any) {
      if (error?.response?.status === 403) {
        toast.error(t("submissions.toast_no_permission"));
      } else {
        showError(error, {
          context: t("submissions.toast_submit_error"),
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  }, [
    canDisplayShareButton,
    effectiveUserId,
    providerId,
    t,
    showError,
    shouldLoadSubmissionStatus,
    refreshSubmissionStatus,
  ]);

  const handleCancelSubmission = useCallback(async () => {
    if (!latestSubmission) {
      return;
    }
    setIsCancellingSubmission(true);
    try {
      await providerSubmissionService.cancelSubmission(latestSubmission.id);
      toast.success(t("submissions.toast_cancel_success"));
      setOptimisticSubmission(null);
      await Promise.all([refreshSubmissionStatus(), refresh()]);
    } catch (error: any) {
      showError(error, {
        context: t("submissions.toast_cancel_error"),
      });
    } finally {
      setIsCancellingSubmission(false);
    }
  }, [latestSubmission, t, showError, refreshSubmissionStatus]);

  const openModelSettings = useCallback((model: Model) => {
    setSettingsModel(model);
  }, []);

  const latestTest: ProviderTestResult | null | undefined = useMemo(() => 
    provider?.latest_test_result, [provider?.latest_test_result]
  );

  const historyTabVisible = useMemo(() => 
    permissions.canShowAuditUI && (recentTests.length > 0 || auditLogs.length > 0),
    [permissions.canShowAuditUI, recentTests.length, auditLogs.length]
  );

  // 加载状态 - 初始加载或刷新中
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

  // 未找到提供商 - 使用相同的容器结构避免 hydration 错误
  if (!provider) {
    return (
      <div className="space-y-6 max-w-7xl">
        <div className="flex flex-col items-center justify-center h-[50vh] gap-4">
          <div className="text-xl font-semibold">{translations.notFound}</div>
          <Button onClick={() => router.back()}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {translations.back}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl animate-in fade-in duration-500">
      {/* 页头 */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4 flex-1 min-w-0">
          <Button variant="ghost" size="icon" onClick={() => router.back()} className="mt-1 shrink-0">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-3xl font-bold tracking-tight">{provider.name}</h1>
              <StatusBadge status={health?.status} translations={translations.status} />
              {shareStatusBadge}
            </div>
            <div className="flex items-center gap-2 text-muted-foreground flex-wrap">
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
                      : provider.visibility === "restricted"
                        ? `👥 ${t("providers.visibility_restricted")}`
                        : `🌐 ${translations.visibility.public}`}
                  </Badge>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-start gap-2 shrink-0 mt-1">
          {canDisplayShareButton && (
            <Button
              variant="default"
              size="sm"
              onClick={handleShareToPool}
              disabled={shareButtonDisabled}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("submissions.btn_submitting")}
                </>
              ) : (
                <>
                  <Share2 className="h-4 w-4 mr-2" />
                  {shareButtonLabel}
                </>
              )}
            </Button>
          )}
          {canCancelSubmission && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleCancelSubmission}
              disabled={isCancellingSubmission}
            >
              {isCancellingSubmission ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("submissions.btn_cancelling")}
                </>
              ) : (
                t("submissions.cancel_share_button")
              )}
            </Button>
          )}
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
          {permissions.canManageUserProbes && (
            <TabsTrigger value="probes">{translations.tabs.probes}</TabsTrigger>
          )}
          {permissions.canShowAuditUI && (
            <TabsTrigger value="audit">
              <Shield className="h-4 w-4 mr-1" />
              {translations.audit.title}
            </TabsTrigger>
          )}
        </TabsList>

        {/* 概览标签页 */}
        <TabsContent value="overview" className="space-y-6">
          <ProviderOverviewTab
            provider={provider}
            metrics={metrics}
            translations={translations.overview}
          >
            {permissions.canEditSharing && effectiveUserId && (
              <ProviderSharingConfig
                providerId={providerId}
                effectiveUserId={effectiveUserId}
                provider={provider}
              />
            )}
          </ProviderOverviewTab>
        </TabsContent>

        {/* 模型标签页 */}
        <TabsContent value="models">
          <ProviderModelsTab
            providerId={providerId}
            models={models}
            canEdit={!!permissions.canEditModelMapping}
            onOpenSettings={openModelSettings}
            onRefresh={refresh}
            translations={translations.models}
          />
        </TabsContent>

        {/* API 密钥标签页 */}
        <TabsContent value="keys">
          <ProviderKeysTab
            providerId={providerId}
            provider={provider}
            canManage={permissions.canManageKeys}
            translations={translations.keys}
            actionManageKeys={t("providers.action_manage_keys")}
          />
        </TabsContent>

        {/* 指标详情标签页 */}
        <TabsContent value="metrics">
          <ProviderMetricsTab
            metrics={metrics}
            translations={translations.metrics}
          />
        </TabsContent>

        {/* 用户探针任务标签页（仅私有 Provider 所有者可见） */}
        {permissions.canManageUserProbes && effectiveUserId && (
          <TabsContent value="probes">
            <ProviderProbesTab
              providerId={providerId}
              userId={effectiveUserId}
              models={models?.models || []}
              translations={translations.userProbes}
            />
          </TabsContent>
        )}

        {/* 审核与运营标签页 */}
        {permissions.canShowAuditUI && (
          <TabsContent value="audit">
            <AuditTabContent
              auditStatus={provider.audit_status as ProviderAuditStatus | undefined}
              operationStatus={provider.operation_status as ProviderOperationStatus | undefined}
              latestTest={latestTest}
              auditRemark={auditRemark}
              setAuditRemark={setAuditRemark}
              rejectReason={rejectReason}
              setRejectReason={setRejectReason}
              limitQps={limitQps}
              setLimitQps={setLimitQps}
              auditSubmitting={auditSubmitting}
              onTest={handleAdminTest}
              onApprove={handleApprove}
              onReject={handleReject}
              onPause={() => handleOperation("pause")}
              onResume={() => handleOperation("resume")}
              onOffline={() => handleOperation("offline")}
              validationResults={validationResults}
              validationLoading={validationLoading}
              onValidate={handleValidateModels}
              onOpenProbeDrawer={() => setProbeDrawerOpen(true)}
              recentTests={recentTests}
              auditLogs={auditLogs}
              historyTabVisible={historyTabVisible}
              translations={translations}
            />
          </TabsContent>
        )}
      </Tabs>

      <ModelSettingsDialog
        open={settingsModel !== null}
        onOpenChange={(open) => !open && setSettingsModel(null)}
        providerId={providerId}
        model={settingsModel}
        canEditModelMapping={!!permissions.canEditModelMapping}
        onRefresh={refresh}
      />

      {/* 探针配置 Drawer */}
      <ProbeConfigDrawer
        open={probeDrawerOpen}
        onOpenChange={setProbeDrawerOpen}
        probeEnabled={probeEnabled}
        setProbeEnabled={setProbeEnabled}
        probeInterval={probeInterval}
        setProbeInterval={setProbeInterval}
        probeModel={probeModel}
        setProbeModel={setProbeModel}
        models={models?.models || []}
        savingProbe={savingProbe}
        onSave={handleSaveProbeConfig}
        translations={{
          probeTitle: translations.audit.probeTitle,
          probeDesc: translations.audit.probeDesc,
          probeToggle: translations.audit.probeToggle,
          probeInterval: translations.audit.probeInterval,
          probeIntervalPlaceholder: translations.audit.probeIntervalPlaceholder,
          probeIntervalHint: translations.audit.probeIntervalHint,
          probeModel: translations.audit.probeModel,
          probeModelPlaceholder: translations.audit.probeModelPlaceholder,
          probeModelHint: translations.audit.probeModelHint,
          probeSave: translations.audit.probeSave,
          probeSaving: translations.audit.probeSaving,
          cancel: t("common.cancel"),
        }}
      />
    </div>
  );
}
