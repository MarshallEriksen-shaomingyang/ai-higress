"use client";

import React from "react";
import { Provider } from "@/http/provider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Edit, Trash2, Settings, Lock, Globe, Eye, Database } from "lucide-react";
import { formatRelativeTime } from "@/lib/date-utils";
import { useI18n } from "@/lib/i18n-context";

interface ProvidersTableEnhancedProps {
  privateProviders: Provider[];
  publicProviders: Provider[];
  isLoading: boolean;
  onEdit?: (provider: Provider) => void;
  onDelete?: (providerId: string) => void;
  onViewDetails?: (providerId: string) => void;
  onViewModels?: (providerId: string) => void;
  currentUserId?: string;
}

export function ProvidersTableEnhanced({
  privateProviders,
  publicProviders,
  isLoading,
  onEdit,
  onDelete,
  onViewDetails,
  onViewModels,
  currentUserId,
}: ProvidersTableEnhancedProps) {
  const { t } = useI18n();
  const allProviders = [...privateProviders, ...publicProviders];

  // 判断是否可以编辑/删除
  const canModify = (provider: Provider) => {
    // 私有提供商：仅所有者可编辑
    if (provider.visibility === 'private') {
      return provider.owner_id === currentUserId;
    }
    // 公共提供商：需要管理员权限（这里简化处理，实际应该检查用户角色）
    return false;
  };

  const renderProviderRow = (provider: Provider) => (
    <TableRow key={provider.id}>
      <TableCell className="px-4 py-3 text-sm font-mono">
        {provider.provider_id}
      </TableCell>
      <TableCell className="px-4 py-3 text-sm font-medium">
        <div className="flex items-center gap-2">
          {provider.visibility === 'private' ? (
            <Lock className="w-4 h-4 text-blue-500" />
          ) : (
            <Globe className="w-4 h-4 text-gray-500" />
          )}
          {provider.name}
        </div>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm">
        <div className="max-w-xs truncate" title={provider.base_url}>
          {provider.base_url}
        </div>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm">
        <Badge
          variant={provider.provider_type === "native" ? "default" : "secondary"}
        >
          {provider.provider_type === "native" ? t("providers.type_native") : t("providers.type_aggregator")}
        </Badge>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm">
        <Badge
          variant={provider.transport === "http" ? "outline" : "secondary"}
        >
          {provider.transport.toUpperCase()}
        </Badge>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm">
        <Badge
          variant={
            provider.visibility === 'private' ? "default" :
            provider.visibility === 'public' ? "secondary" : "outline"
          }
        >
          {provider.visibility === 'private' ? t("providers.visibility_private") :
           provider.visibility === 'public' ? t("providers.visibility_public") : t("providers.visibility_restricted")}
        </Badge>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm">
        <Badge
          variant={
            provider.status === 'healthy' ? "default" :
            provider.status === 'degraded' ? "secondary" : "destructive"
          }
        >
          {provider.status === 'healthy' ? t("providers.status_healthy") :
           provider.status === 'degraded' ? t("providers.status_degraded") : t("providers.status_unhealthy")}
        </Badge>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm text-muted-foreground">
        {formatRelativeTime(provider.updated_at)}
      </TableCell>
      <TableCell className="px-4 py-3 text-sm">
        <div className="flex items-center justify-end gap-2">
          {onViewDetails && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onViewDetails(provider.provider_id)}
              className="h-8 w-8 p-0"
              title={t("providers.action_view_details")}
            >
              <Eye className="w-4 h-4" />
            </Button>
          )}
          {onViewModels && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onViewModels(provider.provider_id)}
              className="h-8 w-8 p-0"
              title={t("providers.action_view_models")}
            >
              <Database className="w-4 h-4" />
            </Button>
          )}
          {canModify(provider) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                  <Settings className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
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
      </TableCell>
    </TableRow>
  );

  const renderTable = (providers: Provider[], emptyMessage: string) => {
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
            {emptyMessage}
          </p>
        </div>
      );
    }

    return (
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.table_column_id")}
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.table_column_name")}
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.column_base_url")}
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.column_provider_type")}
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.column_transport")}
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.column_visibility")}
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.table_column_status")}
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              {t("providers.column_updated_at")}
            </TableHead>
            <TableHead className="px-4 py-3 text-right text-sm font-medium">
              {t("providers.table_column_actions")}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {providers.map(renderProviderRow)}
        </TableBody>
      </Table>
    );
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("providers.table_list_title")}</CardTitle>
        <CardDescription>
          {t("providers.table_list_description")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="all" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="all">
              {t("providers.tab_all")} ({allProviders.length})
            </TabsTrigger>
            <TabsTrigger value="private">
              {t("providers.tab_private")} ({privateProviders.length})
            </TabsTrigger>
            <TabsTrigger value="public">
              {t("providers.tab_public")} ({publicProviders.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="all" className="mt-4">
            {privateProviders.length > 0 && (
              <div className="mb-6">
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Lock className="w-4 h-4 text-blue-500" />
                  {t("providers.section_private")}
                </h3>
                <div className="rounded-md border">
                  {renderTable(privateProviders, "")}
                </div>
              </div>
            )}
            {publicProviders.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                  <Globe className="w-4 h-4 text-gray-500" />
                  {t("providers.section_public")}
                </h3>
                <div className="rounded-md border">
                  {renderTable(publicProviders, "")}
                </div>
              </div>
            )}
            {allProviders.length === 0 && !isLoading && (
              <div className="rounded-md border p-12 text-center">
                <p className="text-lg font-medium text-muted-foreground">
                  {t("providers.empty_all")}
                </p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="private" className="mt-4">
            <div className="rounded-md border">
              {renderTable(
                privateProviders,
                t("providers.empty_private")
              )}
            </div>
          </TabsContent>

          <TabsContent value="public" className="mt-4">
            <div className="rounded-md border">
              {renderTable(
                publicProviders,
                t("providers.empty_public")
              )}
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}