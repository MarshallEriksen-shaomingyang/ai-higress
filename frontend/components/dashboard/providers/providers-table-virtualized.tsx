"use client";

import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { Provider } from "@/http/provider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Edit, Trash2, Settings, Lock, Globe, Eye, Database, Key, Users } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { useRouter } from "next/navigation";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ProvidersTableVirtualizedProps {
  providers: Provider[];
  isLoading: boolean;
  onEdit?: (provider: Provider) => void;
  onDelete?: (providerId: string) => void;
  onViewDetails?: (providerId: string) => void;
  onViewModels?: (providerId: string) => void;
  currentUserId?: string;
}

/**
 * 虚拟化提供商表格组件
 * 
 * 使用 @tanstack/react-virtual 实现虚拟滚动
 * 优化大量提供商的渲染性能
 * 
 * 性能优化：
 * - 仅渲染可见区域的行
 * - 支持大量数据（100+ 项）的流畅滚动
 * - 减少 DOM 节点数量
 */
export function ProvidersTableVirtualized({
  providers,
  isLoading,
  onEdit,
  onDelete,
  onViewDetails,
  onViewModels,
  currentUserId,
}: ProvidersTableVirtualizedProps) {
  const { t } = useI18n();
  const router = useRouter();
  const parentRef = useRef<HTMLDivElement>(null);

  // 配置虚拟化
  const virtualizer = useVirtualizer({
    count: providers.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80, // 估计每行高度为 80px
    overscan: 5, // 预渲染可见区域外的 5 行
  });

  // 判断是否可以编辑/删除
  const canModify = (provider: Provider) => {
    if (provider.visibility === 'private' || provider.visibility === 'restricted') {
      return provider.owner_id === currentUserId;
    }
    return false;
  };

  // 判断是否可以管理密钥
  const canManageKeys = (provider: Provider) => {
    return (
      (provider.visibility === 'private' || provider.visibility === 'restricted') &&
      provider.owner_id === currentUserId
    );
  };

  const renderProbeBadge = (provider: Provider) => {
    const enabled = provider.probe_enabled !== false;
    const interval = provider.probe_interval_seconds;
    if (!enabled) {
      return <Badge variant="secondary">{t("providers.probe_off")}</Badge>;
    }
    if (interval) {
      const minutes = Math.max(1, Math.round(interval / 60));
      return (
        <Badge variant="outline">
          {t("providers.probe_on_with_interval", { minutes })}
        </Badge>
      );
    }
    return <Badge variant="outline">{t("providers.probe_on")}</Badge>;
  };

  if (isLoading) {
    return (
      <div className="p-8 text-center text-muted-foreground">
        {t("providers.loading")}
      </div>
    );
  }

  if (providers.length === 0) {
    return (
      <div className="p-12 text-center">
        <p className="text-lg font-medium text-muted-foreground mb-2">
          {t("providers.empty_all")}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      {/* 表头 */}
      <div className="bg-muted/50 border-b">
        <div className="grid grid-cols-12 gap-4 px-4 py-3 text-sm font-medium">
          <div className="col-span-2">{t("providers.table_column_id")}</div>
          <div className="col-span-2">{t("providers.table_column_name")}</div>
          <div className="col-span-2">{t("providers.column_base_url")}</div>
          <div className="col-span-1">{t("providers.column_provider_type")}</div>
          <div className="col-span-1">{t("providers.column_visibility")}</div>
          <div className="col-span-1">{t("providers.table_column_status")}</div>
          <div className="col-span-1">{t("providers.column_probe")}</div>
          <div className="col-span-2 text-right">{t("providers.table_column_actions")}</div>
        </div>
      </div>

      {/* 虚拟化滚动容器 */}
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ height: '600px' }}
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const provider = providers[virtualRow.index];
            if (!provider) {
              return null;
            }
            return (
              <div
                key={virtualRow.key}
                data-index={virtualRow.index}
                ref={virtualizer.measureElement}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  transform: `translateY(${virtualRow.start}px)`,
                }}
                className="border-b"
              >
                <div className="grid grid-cols-12 gap-4 px-4 py-3 text-sm items-center">
                  {/* Provider ID */}
                  <div className="col-span-2 font-mono truncate" title={provider.provider_id}>
                    {provider.provider_id}
                  </div>

                  {/* Name */}
                  <div className="col-span-2 font-medium">
                    <div className="flex items-center gap-2">
                      {provider.visibility === 'private' && (
                        <Lock className="w-4 h-4 text-blue-500 flex-shrink-0" />
                      )}
                      {provider.visibility === 'restricted' && (
                        <Users className="w-4 h-4 text-amber-500 flex-shrink-0" />
                      )}
                      {provider.visibility === 'public' && (
                        <Globe className="w-4 h-4 text-gray-500 flex-shrink-0" />
                      )}
                      <span className="truncate">{provider.name}</span>
                    </div>
                  </div>

                  {/* Base URL */}
                  <div className="col-span-2 truncate" title={provider.base_url}>
                    {provider.base_url}
                  </div>

                  {/* Provider Type */}
                  <div className="col-span-1">
                    <Badge
                      variant={provider.provider_type === "native" ? "default" : "secondary"}
                    >
                      {provider.provider_type === "native" ? t("providers.type_native") : t("providers.type_aggregator")}
                    </Badge>
                  </div>

                  {/* Visibility */}
                  <div className="col-span-1">
                    <Badge
                      variant={
                        provider.visibility === 'private' ? "default" :
                        provider.visibility === 'public' ? "secondary" : "outline"
                      }
                    >
                      {provider.visibility === 'private' ? t("providers.visibility_private") :
                       provider.visibility === 'public' ? t("providers.visibility_public") : t("providers.visibility_restricted")}
                    </Badge>
                  </div>

                  {/* Status */}
                  <div className="col-span-1">
                    <Badge
                      variant={
                        provider.status === 'healthy' ? "default" :
                        provider.status === 'degraded' ? "secondary" : "destructive"
                      }
                    >
                      {provider.status === 'healthy' ? t("providers.status_healthy") :
                       provider.status === 'degraded' ? t("providers.status_degraded") : t("providers.status_unhealthy")}
                    </Badge>
                  </div>

                  {/* Probe */}
                  <div className="col-span-1">
                    {renderProbeBadge(provider)}
                  </div>

                  {/* Actions */}
                  <div className="col-span-2 flex items-center justify-end gap-2">
                    {onViewDetails && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewDetails(provider.provider_id)}
                            className="h-8 w-8 p-0"
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {t("providers.action_view_details")}
                        </TooltipContent>
                      </Tooltip>
                    )}
                    {onViewModels && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onViewModels(provider.provider_id)}
                            className="h-8 w-8 p-0"
                          >
                            <Database className="w-4 h-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {t("providers.action_view_models")}
                        </TooltipContent>
                      </Tooltip>
                    )}
                    {canManageKeys(provider) && (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => router.push(`/dashboard/providers/${provider.provider_id}/keys`)}
                            className="h-8 w-8 p-0"
                          >
                            <Key className="w-4 h-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>
                          {t("providers.action_manage_keys")}
                        </TooltipContent>
                      </Tooltip>
                    )}
                    {canModify(provider) && (
                      <DropdownMenu>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                                <Settings className="w-4 h-4" />
                              </Button>
                            </DropdownMenuTrigger>
                          </TooltipTrigger>
                          <TooltipContent>
                            {t("providers.action_settings")}
                          </TooltipContent>
                        </Tooltip>
                        <DropdownMenuContent align="end">
                          {onEdit && (
                            <DropdownMenuItem onClick={() => onEdit(provider)}>
                              <Edit className="mr-2 h-4 w-4" />
                              {t("providers.action_edit")}
                            </DropdownMenuItem>
                          )}
                          {onDelete && (
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => onDelete(provider.provider_id)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              {t("providers.action_delete")}
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
