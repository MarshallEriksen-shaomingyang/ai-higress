"use client";

import React from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Key, Edit, Trash2, Loader2 } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { formatRelativeTime } from "@/lib/date-utils";
import type { ProviderKey } from "@/lib/api-types";

interface ProviderKeysTableProps {
  keys: ProviderKey[];
  loading: boolean;
  onEdit: (key: ProviderKey) => void;
  onDelete: (keyId: string) => void;
  onToggleStatus: (keyId: string, newStatus: 'active' | 'inactive') => void;
}

export function ProviderKeysTable({
  keys,
  loading,
  onEdit,
  onDelete,
  onToggleStatus,
}: ProviderKeysTableProps) {
  const { t } = useI18n();

  // 格式化时间
  const formatTime = (dateString: string) => {
    try {
      return formatRelativeTime(dateString);
    } catch {
      return dateString;
    }
  };

  // 状态徽章
  const getStatusBadge = (status: string) => {
    if (status === 'active') {
      return (
        <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100">
          {t("provider_keys.status_active")}
        </Badge>
      );
    }
    return (
      <Badge variant="secondary">
        {t("provider_keys.status_inactive")}
      </Badge>
    );
  };

  // 格式化密钥前缀
  const formatKeyPrefix = (key: ProviderKey) => {
    if (key.key_prefix) {
      return key.key_prefix;
    }
    // 如果没有 key_prefix，显示占位符
    return "sk-***";
  };

  if (loading && keys.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t("provider_keys.title")}</CardTitle>
          <CardDescription>{t("credits.loading")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Key className="w-5 h-5" />
          {t("provider_keys.title")}
        </CardTitle>
        <CardDescription>
          {t("provider_keys.subtitle")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {keys.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Key className="w-12 h-12 text-muted-foreground mb-4" />
            <h3 className="text-lg font-semibold mb-2">
              {t("provider_keys.empty")}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t("provider_keys.empty_description")}
            </p>
          </div>
        ) : (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[200px]">
                    {t("provider_keys.column_label")}
                  </TableHead>
                  <TableHead className="w-[150px]">
                    {t("provider_keys.column_key_prefix")}
                  </TableHead>
                  <TableHead className="w-[100px]">
                    {t("provider_keys.column_weight")}
                  </TableHead>
                  <TableHead className="w-[120px]">
                    {t("provider_keys.column_qps")}
                  </TableHead>
                  <TableHead className="w-[100px]">
                    {t("provider_keys.column_status")}
                  </TableHead>
                  <TableHead className="w-[180px]">
                    {t("provider_keys.column_created")}
                  </TableHead>
                  <TableHead className="w-[120px] text-right">
                    {t("provider_keys.column_actions")}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((key) => (
                  <TableRow key={key.id}>
                    <TableCell className="font-medium">
                      {key.label}
                    </TableCell>
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      {formatKeyPrefix(key)}
                    </TableCell>
                    <TableCell className="font-mono">
                      {key.weight.toFixed(1)}
                    </TableCell>
                    <TableCell className="font-mono">
                      {key.max_qps || '-'}
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(key.status)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatTime(key.created_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onEdit(key)}
                          title={t("provider_keys.action_edit")}
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onDelete(key.id)}
                          title={t("provider_keys.action_delete")}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}