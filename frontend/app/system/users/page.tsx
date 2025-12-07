"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { UserCircle, Plus, Edit, Trash2, Shield, Key, Ban, RotateCcw } from "lucide-react";
import { AdminTopupDialog } from "@/components/dashboard/credits/admin-topup-dialog";
import { AutoTopupBatchDialog } from "@/components/dashboard/credits/auto-topup-batch-dialog";
import { useI18n } from "@/lib/i18n-context";
import { useAuthStore } from "@/lib/stores/auth-store";
import { adminService, Role } from "@/http/admin";
import { userService } from "@/http/user";
import { UserInfo } from "@/http/auth";
import { toast } from "sonner";
import {
    useActiveRegistrationWindow,
    useCreateRegistrationWindow,
    useCloseRegistrationWindow,
} from "@/lib/swr/use-registration-windows";

export default function UsersPage() {
    const router = useRouter();
    const { t } = useI18n();
    const currentAuthUser = useAuthStore(state => state.user);
    const isSuperUser = currentAuthUser?.is_superuser === true;

    const [users, setUsers] = useState<UserInfo[]>([]);
    const [roles, setRoles] = useState<Role[]>([]);
    const [loading, setLoading] = useState(true);

    // Dialog states
    const [createOpen, setCreateOpen] = useState(false);
    const [rolesOpen, setRolesOpen] = useState(false);
    const [topupOpen, setTopupOpen] = useState(false);
    const [autoTopupOpen, setAutoTopupOpen] = useState(false);

    // Current user being edited
    const [currentUser, setCurrentUser] = useState<UserInfo | null>(null);
    const [topupUser, setTopupUser] = useState<UserInfo | null>(null);
    const [selectedRoleIds, setSelectedRoleIds] = useState<string[]>([]);
    const [selectedUserIds, setSelectedUserIds] = useState<string[]>([]);

    // Form data
    const [formData, setFormData] = useState({
        email: "",
        password: "",
        display_name: ""
    });

    // 用户启用/禁用确认对话框状态
    const [statusDialogOpen, setStatusDialogOpen] = useState(false);
    const [statusTargetUser, setStatusTargetUser] = useState<UserInfo | null>(null);
    const [statusTargetActive, setStatusTargetActive] = useState<boolean | null>(null);
    const [updatingStatus, setUpdatingStatus] = useState(false);

    // 注册窗口表单状态
    const [startTimeLocal, setStartTimeLocal] = useState<string>(() => {
        const now = new Date();
        const pad = (n: number) => n.toString().padStart(2, "0");
        const year = now.getFullYear();
        const month = pad(now.getMonth() + 1);
        const day = pad(now.getDate());
        const hour = pad(now.getHours());
        const minute = pad(now.getMinutes());
        return `${year}-${month}-${day}T${hour}:${minute}`;
    });
    const [endTimeLocal, setEndTimeLocal] = useState<string>(() => {
        const later = new Date(Date.now() + 60 * 60 * 1000);
        const pad = (n: number) => n.toString().padStart(2, "0");
        const year = later.getFullYear();
        const month = pad(later.getMonth() + 1);
        const day = pad(later.getDate());
        const hour = pad(later.getHours());
        const minute = pad(later.getMinutes());
        return `${year}-${month}-${day}T${hour}:${minute}`;
    });
    const [maxRegistrations, setMaxRegistrations] = useState<string>("100");
    const [createDialogMode, setCreateDialogMode] = useState<"auto" | "manual" | null>(null);

    const {
        window: activeWindow,
        loading: registrationLoading,
        refresh: refreshRegistrationWindow,
    } = useActiveRegistrationWindow();
    const {
        createAuto,
        createManual,
        creating: creatingWindow,
    } = useCreateRegistrationWindow();
    const {
        closeWindow,
        closing: closingWindow,
    } = useCloseRegistrationWindow();

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        try {
            setLoading(true);
            const [usersData, rolesData] = await Promise.all([
                adminService.getAllUsers(),
                adminService.getRoles()
            ]);
            setUsers(usersData);
            setRoles(rolesData);
        } catch (error) {
            console.error("Failed to fetch data:", error);
            toast.error("Failed to load users and roles");
        } finally {
            setLoading(false);
        }
    };

    const handleCreateUser = async () => {
        try {
            await userService.createUser(formData);
            toast.success("User created successfully");
            setCreateOpen(false);
            fetchData();
            setFormData({ email: "", password: "", display_name: "" });
        } catch (error) {
            toast.error("Failed to create user");
        }
    };

    const openRolesDialog = async (user: UserInfo) => {
        setCurrentUser(user);
        try {
            const userRoles = await adminService.getUserRoles(user.id);
            setSelectedRoleIds(userRoles.map(r => r.id));
            setRolesOpen(true);
        } catch (error) {
            toast.error("Failed to fetch user roles");
        }
    };

    const saveUserRoles = async () => {
        if (!currentUser) return;
        try {
            await adminService.setUserRoles(currentUser.id, selectedRoleIds);
            toast.success("User roles updated successfully");
            setRolesOpen(false);
            fetchData();
        } catch (error) {
            toast.error("Failed to update user roles");
        }
    };

    const toggleRole = (roleId: string) => {
        setSelectedRoleIds(prev =>
            prev.includes(roleId)
                ? prev.filter(id => id !== roleId)
                : [...prev, roleId]
        );
    };

    const getRoleNames = (user: UserInfo): string => {
        if (!user.role_codes || user.role_codes.length === 0) return "No roles";
        return user.role_codes.join(", ");
    };

    const getStatusBadge = (isActive: boolean) => {
        return isActive ? (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                Active
            </span>
        ) : (
            <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300">
                Inactive
            </span>
        );
    };

    const openStatusDialog = (user: UserInfo, nextActive: boolean) => {
        setStatusTargetUser(user);
        setStatusTargetActive(nextActive);
        setStatusDialogOpen(true);
    };

    const handleStatusConfirm = async () => {
        if (!statusTargetUser || statusTargetActive === null) {
            return;
        }

        try {
            setUpdatingStatus(true);
            const updated = await userService.updateUserStatus(statusTargetUser.id, {
                is_active: statusTargetActive,
            });

            // 更新本地列表中的用户状态
            setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));

            toast.success(
                statusTargetActive
                    ? t("users.status_enable_success")
                    : t("users.status_disable_success")
            );

            setStatusDialogOpen(false);
            setStatusTargetUser(null);
            setStatusTargetActive(null);
        } catch (error) {
            console.error("Failed to update user status:", error);
            toast.error(
                statusTargetActive
                    ? t("users.status_enable_error")
                    : t("users.status_disable_error")
            );
        } finally {
            setUpdatingStatus(false);
        }
    };

    const allSelected = users.length > 0 && selectedUserIds.length === users.length;
    const partiallySelected =
        users.length > 0 &&
        selectedUserIds.length > 0 &&
        selectedUserIds.length < users.length;

    const handleCreateRegistrationWindow = async () => {
        if (!startTimeLocal || !endTimeLocal || !maxRegistrations) {
            toast.error(t("users.registration.validation_required"));
            return;
        }
        const startDate = new Date(startTimeLocal);
        const endDate = new Date(endTimeLocal);
        if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) {
            toast.error(t("users.registration.validation_required"));
            return;
        }
        if (endDate <= startDate) {
            toast.error(t("users.registration.validation_start_end"));
            return;
        }
        const max = Number(maxRegistrations);
        if (!Number.isFinite(max) || max <= 0) {
            toast.error(t("users.registration.validation_max_positive"));
            return;
        }

        const payload = {
            start_time: startDate.toISOString(),
            end_time: endDate.toISOString(),
            max_registrations: max,
        };

        try {
            if (createDialogMode === "manual") {
                await createManual(payload);
            } else {
                await createAuto(payload);
            }
            await refreshRegistrationWindow();
            toast.success(t("users.registration.create_success"));
            setCreateDialogMode(null);
        } catch (error: any) {
            const message =
                error?.response?.data?.detail ||
                error?.message ||
                t("users.registration.create_error");
            toast.error(message);
        }
    };

    return (
        <div className="space-y-6 max-w-7xl">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold mb-2">{t("users.title")}</h1>
                    <p className="text-muted-foreground">{t("users.subtitle")}</p>
                </div>
                <div className="flex items-center gap-2">
                    {isSuperUser && (
                        <Button
                            variant="outline"
                            disabled={selectedUserIds.length === 0}
                            onClick={() => setAutoTopupOpen(true)}
                        >
                            {t("credits.auto_topup_bulk")}
                        </Button>
                    )}
                    <Button onClick={() => {
                        setFormData({ email: "", password: "", display_name: "" });
                        setCreateOpen(true);
                    }}>
                        <Plus className="w-4 h-4 mr-2" />
                        {t("users.add_user")}
                    </Button>
                </div>
            </div>

            {isSuperUser && (
                <Card>
                    <CardHeader>
                        <CardTitle>{t("users.registration.title")}</CardTitle>
                        <CardDescription>
                            {t("users.registration.subtitle")}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex items-center justify-between gap-4">
                            <div>
                                <p className="text-sm font-medium">
                                    {t("users.registration.current_status")}
                                </p>
                                <p className="text-sm text-muted-foreground">
                                    {registrationLoading
                                        ? t("common.loading")
                                        : activeWindow
                                        ? t("users.registration.status_open")
                                        : t("users.registration.status_closed")}
                                </p>
                            </div>
                            {activeWindow && (
                                <div className="flex items-center gap-2">
                                    <Badge variant="outline">
                                        {activeWindow.auto_activate
                                            ? t("users.registration.mode_auto")
                                            : t("users.registration.mode_manual")}
                                    </Badge>
                                    <Button
                                        variant="destructive"
                                        size="sm"
                                        disabled={closingWindow}
                                        onClick={async () => {
                                            if (!activeWindow) return;
                                            try {
                                                await closeWindow(activeWindow.id);
                                                await refreshRegistrationWindow();
                                                toast.success(t("users.registration.close_success"));
                                            } catch (error: any) {
                                                const message =
                                                    error?.response?.data?.detail?.message ||
                                                    error?.response?.data?.detail ||
                                                    error?.message ||
                                                    t("users.registration.close_error");
                                                toast.error(message);
                                            }
                                        }}
                                    >
                                        {closingWindow
                                            ? t("common.saving")
                                            : t("users.registration.close_now")}
                                    </Button>
                                </div>
                            )}
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    {t("users.registration.window_start")}
                                </label>
                                <Input
                                    type="datetime-local"
                                    value={startTimeLocal}
                                    onChange={(e) => setStartTimeLocal(e.target.value)}
                                    disabled={creatingWindow}
                                    placeholder={t(
                                        "users.registration.form_start_placeholder"
                                    )}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    {t("users.registration.window_end")}
                                </label>
                                <Input
                                    type="datetime-local"
                                    value={endTimeLocal}
                                    onChange={(e) => setEndTimeLocal(e.target.value)}
                                    disabled={creatingWindow}
                                    placeholder={t(
                                        "users.registration.form_end_placeholder"
                                    )}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    {t("users.registration.max_registrations")}
                                </label>
                                <Input
                                    type="number"
                                    min={1}
                                    value={maxRegistrations}
                                    onChange={(e) => setMaxRegistrations(e.target.value)}
                                    disabled={creatingWindow}
                                    placeholder={t(
                                        "users.registration.form_max_placeholder"
                                    )}
                                />
                            </div>
                        </div>

                        {activeWindow ? (
                            <p className="text-xs text-muted-foreground">
                                {t("users.registration.registered_count")}:{" "}
                                {activeWindow.registered_count} /{" "}
                                {activeWindow.max_registrations}
                            </p>
                        ) : (
                            <p className="text-xs text-muted-foreground">
                                {t("users.registration.no_active_window")}
                            </p>
                        )}

                        <p className="text-xs text-muted-foreground">
                            {t("users.registration.form_hint")}
                        </p>

                        <div className="flex flex-wrap gap-2 pt-2">
                            <Button
                                variant="outline"
                                size="sm"
                                disabled={creatingWindow}
                                onClick={() => setCreateDialogMode("manual")}
                            >
                                {t("users.registration.create_manual")}
                            </Button>
                            <Button
                                size="sm"
                                disabled={creatingWindow}
                                onClick={() => setCreateDialogMode("auto")}
                            >
                                {t("users.registration.create_auto")}
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            )}

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
                                        checked={
                                            allSelected
                                                ? true
                                                : partiallySelected
                                                ? "indeterminate"
                                                : false
                                        }
                                        onCheckedChange={(checked) => {
                                            if (checked) {
                                                setSelectedUserIds(users.map((u) => u.id));
                                            } else {
                                                setSelectedUserIds([]);
                                            }
                                        }}
                                        aria-label="Select all users"
                                    />
                                </TableHead>
                                <TableHead>{t("users.table_column_name")}</TableHead>
                                <TableHead>{t("users.table_column_email")}</TableHead>
                                <TableHead>{t("users.table_column_roles")}</TableHead>
                                <TableHead>{t("users.table_column_status")}</TableHead>
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
                                                setSelectedUserIds((prev) => {
                                                    if (checked) {
                                                        if (prev.includes(user.id)) {
                                                            return prev;
                                                        }
                                                        return [...prev, user.id];
                                                    }
                                                    return prev.filter((id) => id !== user.id);
                                                });
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
                                                    <span key={index} className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                                                        {roleCode}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-xs text-muted-foreground">No roles</span>
                                            )}
                                        </div>
                                    </TableCell>
                                    <TableCell>{getStatusBadge(user.is_active)}</TableCell>
                                    <TableCell className="text-right">
                                        <div className="flex items-center justify-end space-x-2">
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => openStatusDialog(user, !user.is_active)}
                                                    >
                                                        {user.is_active ? (
                                                            <Ban className="w-4 h-4 text-amber-500" />
                                                        ) : (
                                                            <RotateCcw className="w-4 h-4 text-emerald-500" />
                                                        )}
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {user.is_active
                                                        ? t("users.tooltip_disable")
                                                        : t("users.tooltip_enable")}
                                                </TooltipContent>
                                            </Tooltip>
                                            {isSuperUser && (
                                                <Tooltip>
                                                    <TooltipTrigger asChild>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => {
                                                                setTopupUser(user);
                                                                setTopupOpen(true);
                                                            }}
                                                        >
                                                            <Plus className="w-4 h-4" />
                                                        </Button>
                                                    </TooltipTrigger>
                                                    <TooltipContent>
                                                        {t("credits.topup")}
                                                    </TooltipContent>
                                                </Tooltip>
                                            )}
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => {
                                                            router.push(`/system/users/${user.id}/roles`);
                                                        }}
                                                    >
                                                        <Shield className="w-4 h-4" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {t("users.tooltip_roles")}
                                                </TooltipContent>
                                            </Tooltip>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => {
                                                            router.push(`/system/users/${user.id}/permissions`);
                                                        }}
                                                    >
                                                        <Key className="w-4 h-4" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {t("users.tooltip_permissions")}
                                                </TooltipContent>
                                            </Tooltip>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button variant="ghost" size="sm">
                                                        <Edit className="w-4 h-4" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {t("users.tooltip_edit")}
                                                </TooltipContent>
                                            </Tooltip>
                                            <Tooltip>
                                                <TooltipTrigger asChild>
                                                    <Button variant="ghost" size="sm">
                                                        <Trash2 className="w-4 h-4 text-destructive" />
                                                    </Button>
                                                </TooltipTrigger>
                                                <TooltipContent>
                                                    {t("users.tooltip_delete")}
                                                </TooltipContent>
                                            </Tooltip>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {!loading && users.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                                        No users found
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            {/* 用户启用/禁用确认对话框 */}
            <AlertDialog
                open={statusDialogOpen}
                onOpenChange={(open) => {
                    setStatusDialogOpen(open);
                    if (!open) {
                        setStatusTargetUser(null);
                        setStatusTargetActive(null);
                    }
                }}
            >
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>
                            {statusTargetActive
                                ? t("users.status_enable_title")
                                : t("users.status_disable_title")}
                        </AlertDialogTitle>
                        <AlertDialogDescription>
                            {statusTargetActive
                                ? t("users.status_enable_description")
                                : t("users.status_disable_description")}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel
                            disabled={updatingStatus}
                            onClick={() => {
                                setStatusDialogOpen(false);
                                setStatusTargetUser(null);
                                setStatusTargetActive(null);
                            }}
                        >
                            {t("users.status_dialog_cancel")}
                        </AlertDialogCancel>
                        <AlertDialogAction
                            disabled={updatingStatus}
                            onClick={handleStatusConfirm}
                        >
                            {t("users.status_dialog_confirm")}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            {/* 注册窗口创建确认对话框 */}
            <Dialog
                open={!!createDialogMode}
                onOpenChange={(open) => {
                    if (!open) {
                        setCreateDialogMode(null);
                    }
                }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>
                            {createDialogMode === "manual"
                                ? t("users.registration.create_manual")
                                : t("users.registration.create_auto")}
                        </DialogTitle>
                        <DialogDescription>
                            {t("users.registration.subtitle")}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-2">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    {t("users.registration.window_start")}
                                </label>
                                <Input
                                    type="datetime-local"
                                    value={startTimeLocal}
                                    onChange={(e) => setStartTimeLocal(e.target.value)}
                                    disabled={creatingWindow}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">
                                    {t("users.registration.window_end")}
                                </label>
                                <Input
                                    type="datetime-local"
                                    value={endTimeLocal}
                                    onChange={(e) => setEndTimeLocal(e.target.value)}
                                    disabled={creatingWindow}
                                />
                            </div>
                            <div className="space-y-2 md:col-span-2">
                                <label className="text-sm font-medium">
                                    {t("users.registration.max_registrations")}
                                </label>
                                <Input
                                    type="number"
                                    min={1}
                                    value={maxRegistrations}
                                    onChange={(e) => setMaxRegistrations(e.target.value)}
                                    disabled={creatingWindow}
                                />
                            </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {t("users.registration.form_hint")}
                        </p>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setCreateDialogMode(null)}
                            disabled={creatingWindow}
                        >
                            {t("users.status_dialog_cancel")}
                        </Button>
                        <Button
                            onClick={handleCreateRegistrationWindow}
                            disabled={creatingWindow}
                        >
                            {creatingWindow
                                ? t("common.saving")
                                : t("users.status_dialog_confirm")}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Create User Dialog */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t("users.add_user")}</DialogTitle>
                        <DialogDescription>Create a new user account</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Email</label>
                            <Input
                                type="email"
                                value={formData.email}
                                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                placeholder="john@example.com"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Display Name</label>
                            <Input
                                value={formData.display_name}
                                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                                placeholder="John Doe"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Password</label>
                            <Input
                                type="password"
                                value={formData.password}
                                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                placeholder="••••••••"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setCreateOpen(false)}>{t("providers.btn_cancel")}</Button>
                        <Button onClick={handleCreateUser}>{t("providers.btn_create")}</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* User Roles Dialog */}
            <Dialog open={rolesOpen} onOpenChange={setRolesOpen}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>{t("users.roles_dialog_title")}</DialogTitle>
                        <DialogDescription>{t("users.roles_dialog_desc")}</DialogDescription>
                    </DialogHeader>
                    <div className="py-4 max-h-[60vh] overflow-y-auto">
                        <p className="text-sm text-muted-foreground mb-4">{t("users.select_roles")}</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {roles.map((role) => (
                                <div key={role.id} className="flex items-start space-x-3 p-3 border rounded hover:bg-muted/50">
                                    <Checkbox
                                        id={role.id}
                                        checked={selectedRoleIds.includes(role.id)}
                                        onCheckedChange={() => toggleRole(role.id)}
                                    />
                                    <div className="grid gap-1.5 leading-none">
                                        <label
                                            htmlFor={role.id}
                                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                        >
                                            {role.name}
                                        </label>
                                        <p className="text-xs text-muted-foreground">
                                            {role.description || role.code}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setRolesOpen(false)}>{t("providers.btn_cancel")}</Button>
                        <Button onClick={saveUserRoles}>{t("providers.btn_save")}</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Admin credit top-up dialog */}
            {isSuperUser && topupUser && (
                <AdminTopupDialog
                    open={topupOpen}
                    onOpenChange={(open) => {
                        setTopupOpen(open);
                        if (!open) {
                            setTopupUser(null);
                        }
                    }}
                    userId={topupUser.id}
                    onSuccess={fetchData}
                />
            )}

            {/* 批量自动充值配置对话框 */}
            {isSuperUser && (
                <AutoTopupBatchDialog
                    open={autoTopupOpen}
                    onOpenChange={(open) => setAutoTopupOpen(open)}
                    userIds={selectedUserIds}
                    onSuccess={fetchData}
                />
            )}
        </div>
    );
}
