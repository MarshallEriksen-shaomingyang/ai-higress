"use client";

import { useState, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Plus, Search, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Provider, providerService } from "@/http/provider";
import { useI18n } from "@/lib/i18n-context";
import { useErrorDisplay } from "@/lib/errors";
import { usePrivateProviderQuota } from "@/lib/swr/use-private-providers";
import { useUserDashboardProvidersMetrics } from "@/lib/swr/use-dashboard-v2";
import { QuotaCard } from "./quota-card";
import { HealthStats } from "./health-stats";
import { ProviderCard } from "@/app/dashboard/providers/_components/card/provider-card";

const ProviderFormEnhanced = dynamic(() => import("@/components/dashboard/providers/provider-form").then(mod => ({ default: mod.ProviderFormEnhanced })), { ssr: false });
const ProviderModelsDialog = dynamic(() => import("@/components/dashboard/providers/provider-models-dialog").then(mod => ({ default: mod.ProviderModelsDialog })), { ssr: false });

interface MyProvidersPageClientProps {
  initialProviders: Provider[];
  userId: string;
}

export function MyProvidersPageClient({
  initialProviders,
  userId,
}: MyProvidersPageClientProps) {
  const { t } = useI18n();
  const router = useRouter();
  const { showError } = useErrorDisplay();

  // 状态管理
  const [providers, setProviders] = useState<Provider[]>(initialProviders);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingProviderId, setDeletingProviderId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [modelsDialogOpen, setModelsDialogOpen] = useState(false);
  const [viewingModelsProviderId, setViewingModelsProviderId] = useState<string | null>(null);
  const [modelsPathByProvider, setModelsPathByProvider] = useState<Record<string, string>>({});

  const providerIdsParam = useMemo(() => {
    const ids = providers
      .map((p) => p.provider_id)
      .filter((id) => !!id)
      .join(",");
    return ids || undefined;
  }, [providers]);

  const {
    items: providerMetricItems,
    loading: isMetricsLoading,
  } = useUserDashboardProvidersMetrics(providerIdsParam, {
    timeRange: "7d",
    transport: "all",
    isStream: "all",
  });

  const metricsByProviderId = useMemo(() => {
    const map: Record<string, (typeof providerMetricItems)[number]> = {};
    for (const item of providerMetricItems) {
      map[item.provider_id] = item;
    }
    return map;
  }, [providerMetricItems]);

  // 私有 Provider 配额信息
  const {
    limit: quotaLimit,
    isUnlimited,
    loading: isQuotaLoading,
  } = usePrivateProviderQuota(userId);

  // 刷新提供商列表
  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const data = await providerService.getUserPrivateProviders(userId);
      setProviders(data);
    } catch (error) {
      showError(error, { context: t("providers.error_loading") });
    } finally {
      setIsRefreshing(false);
    }
  }, [userId, t, showError]);

  // 本地搜索过滤
  const filteredProviders = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return providers;

    return providers.filter((provider) => {
      const name = provider.name?.toLowerCase() ?? "";
      const providerId = provider.provider_id?.toLowerCase() ?? "";
      const baseUrl = provider.base_url?.toLowerCase() ?? "";

      return (
        name.includes(query) ||
        providerId.includes(query) ||
        baseUrl.includes(query)
      );
    });
  }, [providers, searchQuery]);

  // 打开创建表单
  const handleCreate = useCallback(() => {
    // 检查配额
    if (!isUnlimited && quotaLimit > 0 && providers.length >= quotaLimit) {
      toast.error(t("my_providers.quota_warning"));
      return;
    }
    setFormOpen(true);
  }, [providers.length, quotaLimit, isUnlimited, t]);

  // 表单成功回调
  const handleFormSuccess = useCallback(() => {
    refresh();
  }, [refresh]);

  // 编辑提供商
  const handleEdit = useCallback((provider: Provider) => {
    setEditingProvider(provider);
    setFormOpen(true);
  }, []);

  // 打开删除确认
  const handleDeleteClick = useCallback((providerId: string) => {
    setDeletingProviderId(providerId);
    setDeleteConfirmOpen(true);
  }, []);

  // 确认删除
  const handleDeleteConfirm = useCallback(async () => {
    if (!deletingProviderId) return;

    setIsDeleting(true);
    try {
      await providerService.deletePrivateProvider(userId, deletingProviderId);
      toast.success(t("providers.toast_delete_success"));
      await refresh();
    } catch (error) {
      showError(error, {
        context: t("providers.toast_delete_error"),
        onRetry: () => handleDeleteConfirm()
      });
    } finally {
      setIsDeleting(false);
      setDeleteConfirmOpen(false);
      setDeletingProviderId(null);
    }
  }, [deletingProviderId, userId, refresh, t, showError]);

  // 查看详情
  const handleViewDetails = useCallback((providerId: string) => {
    // 使用Next.js原生导航
    router.push(`/dashboard/providers/${providerId}`);
  }, [router]);

  // 查看模型
  const handleViewModels = useCallback((providerId: string) => {
    setViewingModelsProviderId(providerId);
    setModelsDialogOpen(true);
  }, []);

  const handleManageKeys = useCallback(
    (providerInternalId: string) => {
      router.push(`/dashboard/providers/${providerInternalId}/keys`);
    },
    [router]
  );

  // 更新模型路径
  const handleModelsPathChange = useCallback((providerId: string, path: string) => {
    setModelsPathByProvider((prev) => ({
      ...prev,
      [providerId]: path,
    }));
  }, []);

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="space-y-1">
        <h1 className="text-3xl font-bold">{t("my_providers.title")}</h1>
        <p className="text-muted-foreground text-sm">
          {t("my_providers.subtitle")}
        </p>
      </div>

      {/* 顶部统计卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <QuotaCard
          current={providers.length}
          limit={quotaLimit}
          isUnlimited={isUnlimited}
          isLoading={isRefreshing || isQuotaLoading}
        />
        <HealthStats providers={providers} isLoading={isRefreshing} />
      </div>

      {/* 操作栏 */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        {/* 搜索框 */}
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("my_providers.search_placeholder")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={refresh}
            disabled={isRefreshing}
            className="flex-1 md:flex-none"
          >
            <RefreshCw
              className={`w-4 h-4 mr-2 ${isRefreshing ? "animate-spin" : ""}`}
            />
            {t("my_providers.refresh")}
          </Button>
          <Button onClick={handleCreate} className="flex-1 md:flex-none">
            <Plus className="w-4 h-4 mr-2" />
            {t("my_providers.create_provider")}
          </Button>
        </div>
      </div>

      {/* Provider 列表 */}
      {filteredProviders.length === 0 && !isRefreshing ? (
        <div className="rounded-lg border border-dashed p-12 text-center">
          <div className="mx-auto max-w-md space-y-3">
            <h3 className="text-lg font-medium">
              {t("my_providers.empty_message")}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t("my_providers.empty_description")}
            </p>
            <Button onClick={handleCreate} className="mt-4">
              <Plus className="w-4 h-4 mr-2" />
              {t("my_providers.create_provider")}
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredProviders.map((provider) => (
            <ProviderCard
              key={provider.id}
              provider={provider}
              metrics={metricsByProviderId[provider.provider_id]}
              isMetricsLoading={isMetricsLoading}
              onConfigure={handleEdit}
              onDelete={handleDeleteClick}
              onViewDetails={handleViewDetails}
              onViewModels={handleViewModels}
              onManageKeys={handleManageKeys}
              canModify
              canManageKeys
            />
          ))}
        </div>
      )}

      {/* 创建/编辑表单抽屉 */}
      <ProviderFormEnhanced
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setEditingProvider(null);
          }
        }}
        onSuccess={() => {
          handleFormSuccess();
          setEditingProvider(null);
        }}
        editingProvider={editingProvider}
      />

      {/* 删除确认抽屉 */}
      <Drawer open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DrawerContent className="mx-auto w-full max-w-md">
          <DrawerHeader>
            <DrawerTitle>{t("providers.delete_dialog_title")}</DrawerTitle>
            <DrawerDescription>
              {t("providers.delete_dialog_description")}{" "}
              <span className="font-mono font-semibold">{deletingProviderId}</span>
              {t("providers.delete_dialog_warning")}
            </DrawerDescription>
          </DrawerHeader>
          <DrawerFooter className="border-t bg-background/80 backdrop-blur">
            <div className="flex w-full justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setDeleteConfirmOpen(false)}
                disabled={isDeleting}
              >
                {t("providers.btn_cancel")}
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
              >
                {isDeleting
                  ? t("providers.deleting_button")
                  : t("providers.delete_button")}
              </Button>
            </div>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>

      {/* 模型查看抽屉 */}
      <ProviderModelsDialog
        open={modelsDialogOpen}
        onOpenChange={setModelsDialogOpen}
        providerId={viewingModelsProviderId}
        modelsPathByProvider={modelsPathByProvider}
        onModelsPathChange={handleModelsPathChange}
      />
    </div>
  );
}
