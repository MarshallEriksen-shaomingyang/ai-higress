"use client";

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { UserCircle, Plus, Shield, Key, Ban, RotateCcw, Zap } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import type { UserInfo } from "@/lib/api-types";

interface UsersTableProps {
    users: UserInfo[];
    loading: boolean;
    isSuperUser: boolean;
    selectedUserIds: string[];
    onSelectedUserIdsChange: (ids: string[]) => void;
    onOpenRoles: (user: UserInfo) => void;
    onOpenPermissions: (user: UserInfo) => void;
    onOpenStatus: (user: UserInfo, nextActive: boolean) => void;
    onOpenTopup: (user: UserInfo) => void;
    onOpenAutoTopup: (user: UserInfo) => void;
}

export function UsersTable({
    users,
    loading,
    isSuperUser,
    selectedUserIds,
    onSelectedUserIdsChange,
    onOpenRoles,
    onOpenPermissions,
    onOpenStatus,
    onOpenTopup,
    onOpenAutoTopup,
}: UsersTableProps) {
    const { t } = useI18n();

    const allSelected = users.length > 0 && selectedUserIds.length === users.length;
    const partiallySelected = users.length > 0 && selectedUserIds.length > 0 && selectedUserIds.length < users.length;

    const getStatusBadge = (isActive: boolean) => {
        return isActive ? (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                {t("common.active")}
            </span>
        ) : (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                {t("common.inactive")}
            </span>
        );
    };

    const getAutoTopupBadge = (user: UserInfo) => {
        const config = user.credit_auto_topup;
        if (!config) {
            return (
                <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                    {t("credits.auto_topup_not_configured")}
                </span>
            );
        }
        return config.is_active ? (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300">
                {t("credits.auto_topup_status_active")}
            </span>
        ) : (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300">
                {t("credits.auto_topup_status_inactive")}
            </span>
        );
    };

    const getAutoTopupIconClassName = (user: UserInfo) => {
        const config = user.credit_auto_topup;
        if (!config) return "text-muted-foreground";
        return config.is_active ? "text-emerald-500" : "text-amber-500";
    };

    const getRiskBadge = (user: UserInfo) => {
        const riskLevel = (user.risk_level || "low").toLowerCase();
        const riskScore = typeof user.risk_score === "number" ? user.risk_score : 0;
        const remark = user.risk_remark || null;
        const labelKey =
            riskLevel === "high"
                ? "users.risk.high"
                : riskLevel === "medium"
                  ? "users.risk.medium"
                  : "users.risk.low";
        const variant =
            riskLevel === "high"
                ? "destructive"
                : riskLevel === "medium"
                  ? "default"
                  : "secondary";

        const badge = (
            <Badge variant={variant}>
                {t(labelKey)} {riskScore > 0 ? `(${riskScore})` : ""}
            </Badge>
        );

        if (!remark) return badge;
        return (
            <Tooltip>
                <TooltipTrigger asChild>{badge}</TooltipTrigger>
                <TooltipContent>{remark}</TooltipContent>
            </Tooltip>
        );
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("users.title")}</CardTitle>
                <CardDescription>{t("users.subtitle")}</CardDescription>
            </CardHeader>
            <CardContent>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead className="w-12">
                                <Checkbox
                                    checked={allSelected ? true : partiallySelected ? "indeterminate" : false}
                                    onCheckedChange={(checked) => {
                                        if (checked) {
                                            onSelectedUserIdsChange(users.map((u) => u.id));
                                        } else {
                                            onSelectedUserIdsChange([]);
                                        }
                                    }}
                                    aria-label="Select all users"
                                />
                            </TableHead>
                            <TableHead>{t("users.table_column_name")}</TableHead>
                            <TableHead>{t("users.table_column_email")}</TableHead>
                            <TableHead>{t("users.table_column_roles")}</TableHead>
                            <TableHead>{t("users.table_column_status")}</TableHead>
                            <TableHead>{t("users.table_column_auto_topup")}</TableHead>
                            <TableHead>{t("users.table_column_risk")}</TableHead>
                            <TableHead className="text-right">{t("providers.table_column_actions")}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {users.map((user) => (
                            <TableRow key={user.id}>
                                <TableCell className="w-12">
                                    <Checkbox
                                        checked={selectedUserIds.includes(user.id)}
                                        onCheckedChange={(checked) => {
                                            onSelectedUserIdsChange(
                                                checked
                                                    ? [...selectedUserIds, user.id]
                                                    : selectedUserIds.filter((id) => id !== user.id)
                                            );
                                        }}
                                        aria-label="Select user"
                                    />
                                </TableCell>
                                <TableCell className="font-medium">
                                    <div className="flex items-center">
                                        <UserCircle className="w-4 h-4 mr-2 text-muted-foreground" />
                                        {user.display_name || user.email}
                                    </div>
                                </TableCell>
                                <TableCell className="text-muted-foreground">{user.email}</TableCell>
                                <TableCell>
                                    <div className="flex flex-wrap gap-1">
                                        {user.role_codes && user.role_codes.length > 0 ? (
                                            user.role_codes.map((roleCode, index) => (
                                                <span
                                                    key={index}
                                                    className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300"
                                                >
                                                    {roleCode}
                                                </span>
                                            ))
                                        ) : (
                                            <span className="text-xs text-muted-foreground">{t("users.table_value_no_roles")}</span>
                                        )}
                                    </div>
                                </TableCell>
                                <TableCell>{getStatusBadge(user.is_active)}</TableCell>
                                <TableCell>{getAutoTopupBadge(user)}</TableCell>
                                <TableCell>{getRiskBadge(user)}</TableCell>
                                <TableCell className="text-right">
                                    <div className="flex items-center justify-end space-x-2">
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => onOpenStatus(user, !user.is_active)}
                                                >
                                                    {user.is_active ? (
                                                        <Ban className="w-4 h-4 text-amber-500" />
                                                    ) : (
                                                        <RotateCcw className="w-4 h-4 text-emerald-500" />
                                                    )}
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                {user.is_active ? t("users.tooltip_disable") : t("users.tooltip_enable")}
                                            </TooltipContent>
                                        </Tooltip>
                                        {isSuperUser && (
                                            <>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button variant="ghost" size="sm" onClick={() => onOpenTopup(user)}>
                                                            <Plus className="w-4 h-4" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>{t("credits.topup")}</TooltipContent>
                                                </Tooltip>
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button variant="ghost" size="sm" onClick={() => onOpenAutoTopup(user)}>
                                                            <Zap className={`w-4 h-4 ${getAutoTopupIconClassName(user)}`} />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>{t("credits.auto_topup_manage")}</TooltipContent>
                                                </Tooltip>
                                            </>
                                        )}
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button variant="ghost" size="sm" onClick={() => onOpenRoles(user)}>
                                                    <Shield className="w-4 h-4" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>{t("users.tooltip_roles")}</TooltipContent>
                                        </Tooltip>
                                        <Tooltip>
                                            <TooltipTrigger asChild>
                                                <Button variant="ghost" size="sm" onClick={() => onOpenPermissions(user)}>
                                                    <Key className="w-4 h-4" />
                                                </Button>
                                            </TooltipTrigger>
                                            <TooltipContent>{t("users.tooltip_permissions")}</TooltipContent>
                                        </Tooltip>
                                    </div>
                                </TableCell>
                            </TableRow>
                        ))}
                        {!loading && users.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                                    {t("users.table_no_users")}
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </CardContent>
        </Card>
    );
}
