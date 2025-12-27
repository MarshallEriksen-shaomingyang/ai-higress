"use client";

import { useState, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import type { Provider } from "@/http/provider";
import { useI18n } from "@/lib/i18n-context";
import { useErrorDisplay } from "@/lib/errors";
import { useAuthStore } from "@/lib/stores/auth-store";
import { usePrivateProviderQuota, useUserAvailableProviders } from "@/lib/swr/use-private-providers";
import { useUserDashboardProvidersMetrics } from "@/lib/swr/use-dashboard-v2";
import { DeleteProviderDialog } from "./delete-provider-dialog";
import { PrivateProvidersCards } from "./private-providers-cards";
import { MyProvidersHeader } from "./my-providers-header";
import { MyProvidersSummary } from "./my-providers-summary";
import { MyProvidersToolbar } from "./my-providers-toolbar";

const ProviderFormEnhanced = dynamic(() => import("@/components/dashboard/providers/provider-form").then(mod => ({ default: mod.ProviderFormEnhanced })), { ssr: false });
const ProviderModelsDialog = dynamic(() => import("@/components/dashboard/providers/provider-models-dialog").then(mod => ({ default: mod.ProviderModelsDialog })), { ssr: false });

type TabValue = "private" | "shared" | "public";

/**
 * Provider 管理页面客户端组件
 *
 * - 使用前端 auth store 判断登录态
 * - 使用 SWR hooks 获取私有、共享和公共 Provider 列表
 * - 未登录时展示登录提示，并唤起全局登录对话框
 * - 处理所有业务逻辑：Tab 切换、搜索、刷新、创建、编辑、删除
 */
export function MyProvidersPageClient() {
  const { t } = useI18n();
  const router = useRouter();
  const { showError } = useErrorDisplay();

  // 认证状态
  const user = useAuthStore((state) => state.user);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const authLoading = useAuthStore((state) => state.isLoading);
  const openAuthDialog = useAuthStore((state) => state.openAuthDialog);

  const userId = user?.id ?? null;

  // Tab 状态
  const [activeTab, setActiveTab] = useState<TabValue>("private");

  // 使用 SWR hooks 获取数据
  const {
    privateProviders,
    sharedProviders,
    publicProviders,
    loading: isLoadingAllProviders,
    refresh: refreshAllProviders,
  } = useUserAvailableProviders({ userId });

  // 私有 Provider 配额信息
  const {
    limit: quotaLimit,
    isUnlimited,
    loading: isQuotaLoading,
  } = usePrivateProviderQuota(userId);

  // 状态管理
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

  // 根据当前 Tab 获取对应的 providers
  const currentProviders = useMemo(() => {
    switch (activeTab) {
      case "private":
        return privateProviders;
      case "shared":
        return sharedProviders;
      case "public":
        return publicProviders;
      default:
        return [];
    }
  }, [activeTab, privateProviders, sharedProviders, publicProviders]);

  const providerIdsParam = useMemo(() => {
    const ids = currentProviders
      .map((p) => p.provider_id)
      .filter((id) => !!id)
      .join(",");
    return ids || undefined;
  }, [currentProviders]);

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

  // 刷新提供商列表
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await refreshAllProviders();
    } catch (error) {
      showError(error, { context: t("providers.error_loading") });
    } finally {
      setIsRefreshing(false);
    }
  }, [refreshAllProviders, t, showError]);

  // 本地搜索过滤
  const filteredProviders = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return currentProviders;

    return currentProviders.filter((provider) => {
      const name = provider.name?.toLowerCase() ?? "";
      const providerId = provider.provider_id?.toLowerCase() ?? "";
      const baseUrl = provider.base_url?.toLowerCase() ?? "";

      return (
        name.includes(query) ||
        providerId.includes(query) ||
        baseUrl.includes(query)
      );
    });
  }, [currentProviders, searchQuery]);

  // 打开创建表单
  const handleCreate = useCallback(() => {
    // 检查配额
    if (!isUnlimited && quotaLimit > 0 && privateProviders.length >= quotaLimit) {
      toast.error(t("my_providers.quota_warning"));
      return;
    }
    setFormOpen(true);
  }, [privateProviders.length, quotaLimit, isUnlimited, t]);

  // 表单成功回调
  const handleFormSuccess = useCallback(() => {
    refreshAllProviders();
  }, [refreshAllProviders]);

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
    if (!deletingProviderId || !userId) return;

    setIsDeleting(true);
    try {
      // 调用删除 API
      const { deletePrivateProvider } = await import("@/http/provider").then(m => m.providerService);
      await deletePrivateProvider(userId, deletingProviderId);
      toast.success(t("providers.toast_delete_success"));
      await refreshAllProviders();
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
  }, [deletingProviderId, userId, t, showError, refreshAllProviders]);

  // 查看详情
  const handleViewDetails = useCallback((providerId: string) => {
    router.push(`/dashboard/providers/${providerId}`);
  }, [router]);

  // 查看模型
  const handleViewModels = useCallback((providerId: string) => {
    setViewingModelsProviderId(providerId);
    setModelsDialogOpen(true);
  }, []);

  const handleManageKeys = useCallback(
    (providerId: string) => {
      router.push(`/dashboard/providers/${providerId}/keys`);
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

  // 加载中状态
  if (authLoading || isLoadingAllProviders) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">{t("common.loading")}</p>
      </div>
    );
  }

  // 未登录状态
  if (!isAuthenticated || !userId) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <p className="text-muted-foreground">
          {t("my_providers.login_required")}
        </p>
        <Button onClick={openAuthDialog}>{t("auth.signin_link")}</Button>
      </div>
    );
  }

  // 已登录，显示完整页面
  return (
    <div className="space-y-6">
      <MyProvidersHeader />

      {/* 顶部统计卡片 */}
      <MyProvidersSummary
        providers={privateProviders}
        quotaLimit={quotaLimit}
        isUnlimited={isUnlimited}
        isLoading={isRefreshing || isQuotaLoading}
      />

      {/* Tab 切换 */}
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as TabValue)} className="w-full">
        <TabsList>
          <TabsTrigger value="private">我的私有</TabsTrigger>
          <TabsTrigger value="shared">他人分享</TabsTrigger>
          <TabsTrigger value="public">公共 Provider</TabsTrigger>
        </TabsList>

        <TabsContent value="private" className="space-y-4 mt-6">
          {/* 操作栏 */}
          <MyProvidersToolbar
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            isRefreshing={isRefreshing}
            onRefresh={handleRefresh}
            onCreate={handleCreate}
          />

          {/* Provider 列表 */}
          <PrivateProvidersCards
            providers={filteredProviders}
            isRefreshing={isRefreshing}
            metricsByProviderId={metricsByProviderId}
            isMetricsLoading={isMetricsLoading}
            onCreate={handleCreate}
            onEdit={handleEdit}
            onDelete={handleDeleteClick}
            onViewDetails={handleViewDetails}
            onViewModels={handleViewModels}
            onManageKeys={handleManageKeys}
          />
        </TabsContent>

        <TabsContent value="shared" className="space-y-4 mt-6">
          {/* 操作栏（共享的不需要创建按钮） */}
          <MyProvidersToolbar
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            isRefreshing={isRefreshing}
            onRefresh={handleRefresh}
            onCreate={undefined}
          />

          {/* Provider 列表（共享的不能编辑和删除） */}
          <PrivateProvidersCards
            providers={filteredProviders}
            isRefreshing={isRefreshing}
            metricsByProviderId={metricsByProviderId}
            isMetricsLoading={isMetricsLoading}
            onCreate={undefined}
            onEdit={undefined}
            onDelete={undefined}
            onViewDetails={handleViewDetails}
            onViewModels={handleViewModels}
            onManageKeys={undefined}
          />
        </TabsContent>

        <TabsContent value="public" className="space-y-4 mt-6">
          {/* 操作栏（公共的不需要创建按钮） */}
          <MyProvidersToolbar
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            isRefreshing={isRefreshing}
            onRefresh={handleRefresh}
            onCreate={undefined}
          />

          {/* Provider 列表（公共的不能编辑和删除） */}
          <PrivateProvidersCards
            providers={filteredProviders}
            isRefreshing={isRefreshing}
            metricsByProviderId={metricsByProviderId}
            isMetricsLoading={isMetricsLoading}
            onCreate={undefined}
            onEdit={undefined}
            onDelete={undefined}
            onViewDetails={handleViewDetails}
            onViewModels={handleViewModels}
            onManageKeys={undefined}
          />
        </TabsContent>
      </Tabs>

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
      <DeleteProviderDialog
        open={deleteConfirmOpen}
        onOpenChange={setDeleteConfirmOpen}
        providerId={deletingProviderId}
        isDeleting={isDeleting}
        onConfirm={handleDeleteConfirm}
      />

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
