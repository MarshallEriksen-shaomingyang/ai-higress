"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useI18n } from "@/lib/i18n-context";
import { adminService, Permission } from "@/http/admin";
import type { UserInfo } from "@/lib/api-types";
import type { UserPermission } from "@/lib/api-types";
import { toast } from "sonner";

interface UserPermissionsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    currentUser: UserInfo | null;
    permissions: Permission[];
    selectedPermCodes: string[];
    onSelectedPermCodesChange: (codes: string[]) => void;
    currentUserPermissions: UserPermission[];
    onSuccess: () => void;
}

export function UserPermissionsDialog({
    open,
    onOpenChange,
    currentUser,
    permissions,
    selectedPermCodes,
    onSelectedPermCodesChange,
    currentUserPermissions,
    onSuccess,
}: UserPermissionsDialogProps) {
    const { t } = useI18n();
    const [saving, setSaving] = useState(false);

    const togglePermission = (code: string) => {
        onSelectedPermCodesChange(
            selectedPermCodes.includes(code)
                ? selectedPermCodes.filter((c) => c !== code)
                : [...selectedPermCodes, code]
        );
    };

    const handleSave = async () => {
        if (!currentUser) return;
        setSaving(true);
        try {
            const desired = new Set(selectedPermCodes);
            const existing = new Map(currentUserPermissions.map((perm) => [perm.permission_type, perm]));

            const toAdd = Array.from(desired).filter((code) => !existing.has(code));
            const toRemove = currentUserPermissions.filter((perm) => !desired.has(perm.permission_type));

            await Promise.all([
                ...toAdd.map((code) =>
                    adminService.grantUserPermission(currentUser.id, { permission_type: code })
                ),
                ...toRemove.map((perm) =>
                    adminService.revokeUserPermission(currentUser.id, perm.id)
                ),
            ]);

            toast.success(t("users.permissions_save_success"));
            onOpenChange(false);
            onSuccess();
        } catch (error) {
            toast.error(t("users.permissions_save_error"));
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle>{t("users.permissions_dialog_title")}</DialogTitle>
                    <DialogDescription>{t("users.permissions_dialog_desc")}</DialogDescription>
                </DialogHeader>
                <div className="py-4 max-h-[60vh] overflow-y-auto">
                    <p className="text-sm text-muted-foreground mb-4">{t("users.select_permissions")}</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {permissions.map((perm) => (
                            <div key={perm.id} className="flex items-start space-x-3 p-3 border rounded hover:bg-muted/50">
                                <Checkbox
                                    id={perm.code}
                                    checked={selectedPermCodes.includes(perm.code)}
                                    onCheckedChange={() => togglePermission(perm.code)}
                                />
                                <div className="grid gap-1.5 leading-none">
                                    <label
                                        htmlFor={perm.code}
                                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                                    >
                                        {perm.code}
                                    </label>
                                    <p className="text-xs text-muted-foreground">{perm.description}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        {t("providers.btn_cancel")}
                    </Button>
                    <Button onClick={handleSave} disabled={saving}>
                        {saving ? t("common.saving") : t("providers.btn_save")}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
