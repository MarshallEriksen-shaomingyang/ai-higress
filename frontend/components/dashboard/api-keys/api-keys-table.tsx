"use client";

import React, { useState } from "react";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Key, Copy, Trash2, Edit, Plus, Shield } from "lucide-react";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { formatRelativeTime } from "@/lib/date-utils";
import type { ApiKey } from "@/lib/api-types";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { useI18n } from "@/lib/i18n-context";

interface ApiKeysTableProps {
    apiKeys: ApiKey[];
    loading: boolean;
    onEdit: (apiKey: ApiKey) => void;
    onDelete: (keyId: string) => Promise<void>;
    onCreate: () => void;
}

export function ApiKeysTable({
    apiKeys,
    loading,
    onEdit,
    onDelete,
    onCreate,
}: ApiKeysTableProps) {
    const { showError } = useErrorDisplay();
    const { t, language } = useI18n();
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [keyToDelete, setKeyToDelete] = useState<ApiKey | null>(null);
    const [deleting, setDeleting] = useState(false);

    const handleCopy = async (keyPrefix: string) => {
        try {
            await navigator.clipboard.writeText(keyPrefix);
            toast.success("Key Prefix 已复制到剪贴板");
        } catch (error) {
            showError(error, { context: "复制 Key Prefix" });
        }
    };

    const handleDeleteClick = (apiKey: ApiKey) => {
        setKeyToDelete(apiKey);
        setDeleteDialogOpen(true);
    };

    const handleDeleteConfirm = async () => {
        if (!keyToDelete) return;

        setDeleting(true);
        try {
            await onDelete(keyToDelete.id);
            toast.success("API Key 已删除");
            setDeleteDialogOpen(false);
            setKeyToDelete(null);
        } catch (error) {
            showError(error, {
                context: "删除 API Key",
                onRetry: () => handleDeleteConfirm()
            });
        } finally {
            setDeleting(false);
        }
    };

    const formatDate = (dateString: string) => {
        try {
            return formatRelativeTime(dateString, language);
        } catch {
            return dateString;
        }
    };

    const getExpiryBadge = (apiKey: ApiKey) => {
        if (apiKey.expiry_type === 'never') {
            return <Badge variant="secondary">永不过期</Badge>;
        }

        if (apiKey.expires_at) {
            const expiresAt = new Date(apiKey.expires_at);
            const now = new Date();
            const isExpired = expiresAt < now;
            const daysUntilExpiry = Math.ceil((expiresAt.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));

            if (isExpired) {
                return <Badge variant="destructive">已过期</Badge>;
            } else if (daysUntilExpiry <= 7) {
                return <Badge variant="destructive">即将过期</Badge>;
            } else if (daysUntilExpiry <= 30) {
                return <Badge className="bg-amber-500">即将过期</Badge>;
            }
        }

        const expiryLabels = {
            week: '1 周',
            month: '1 个月',
            year: '1 年',
        };
        return <Badge variant="secondary">{expiryLabels[apiKey.expiry_type as keyof typeof expiryLabels] || apiKey.expiry_type}</Badge>;
    };

    if (loading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>API Keys</CardTitle>
                    <CardDescription>加载中...</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    </div>
                </CardContent>
            </Card>
        );
    }

    return (
        <>
            <Card>
                <CardHeader>
                    <div className="flex items-center justify-between">
                        <div>
                            <CardTitle>API Keys</CardTitle>
                            <CardDescription>
                                管理您的 API 密钥，保持密钥安全，切勿公开分享
                            </CardDescription>
                        </div>
                        <Button onClick={onCreate}>
                            <Plus className="w-4 h-4 mr-2" />
                            创建 API Key
                        </Button>
                    </div>
                </CardHeader>
                <CardContent>
                    {apiKeys.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                            <Key className="w-12 h-12 text-muted-foreground mb-4" />
                            <h3 className="text-lg font-semibold mb-2">暂无 API Keys</h3>
                            <p className="text-sm text-muted-foreground mb-4">
                                创建您的第一个 API Key 来开始使用 AI Higress API
                            </p>
                            <Button onClick={onCreate}>
                                <Plus className="w-4 h-4 mr-2" />
                                创建 API Key
                            </Button>
                        </div>
                    ) : (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>名称</TableHead>
                                    <TableHead>Key Prefix</TableHead>
                                    <TableHead>创建时间</TableHead>
                                    <TableHead>过期时间</TableHead>
                                    <TableHead>提供商限制</TableHead>
                                    <TableHead className="text-right">操作</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {apiKeys.map((apiKey) => (
                                    <TableRow key={apiKey.id}>
                                        <TableCell className="font-medium">
                                            <div className="flex items-center">
                                                <Key className="w-4 h-4 mr-2 text-muted-foreground" />
                                                {apiKey.name}
                                            </div>
                                        </TableCell>
                                        <TableCell className="font-mono text-sm">
                                            <div className="flex items-center gap-2">
                                                <span>{apiKey.key_prefix}...</span>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            className="h-6 w-6 p-0"
                                                            onClick={() =>
                                                                handleCopy(apiKey.key_prefix)
                                                            }
                                                        >
                                                            <Copy className="w-3 h-3" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        {t("api_keys.tooltip_copy_prefix")}
                                                    </TooltipContent>
                                                </Tooltip>
                                            </div>
                                        </TableCell>
                                        <TableCell className="text-muted-foreground">
                                            {formatDate(apiKey.created_at)}
                                        </TableCell>
                                        <TableCell>
                                            {getExpiryBadge(apiKey)}
                                        </TableCell>
                                        <TableCell>
                                            {apiKey.has_provider_restrictions ? (
                                                <div className="flex items-center gap-1">
                                                    <Shield className="w-4 h-4 text-amber-500" />
                                                    <span className="text-sm">
                                                        {apiKey.allowed_provider_ids.length} 个
                                                    </span>
                                                </div>
                                            ) : (
                                                <span className="text-sm text-muted-foreground">无限制</span>
                                            )}
                                        </TableCell>
                                        <TableCell className="text-right">
                                            <div className="flex items-center justify-end space-x-2">
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => onEdit(apiKey)}
                                                        >
                                                            <Edit className="w-4 h-4" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        {t("api_keys.tooltip_edit")}
                                                    </TooltipContent>
                                                </Tooltip>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() =>
                                                                handleDeleteClick(apiKey)
                                                            }
                                                        >
                                                            <Trash2 className="w-4 h-4 text-destructive" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        {t("api_keys.tooltip_delete")}
                                                    </TooltipContent>
                                                </Tooltip>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                </CardContent>
            </Card>

            <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>确认删除</AlertDialogTitle>
                        <AlertDialogDescription>
                            您确定要删除 API Key "{keyToDelete?.name}" 吗？
                            <br />
                            <br />
                            此操作无法撤销，使用此密钥的所有请求将立即失败。
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel disabled={deleting}>取消</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDeleteConfirm}
                            disabled={deleting}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            {deleting ? '删除中...' : '确认删除'}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}
