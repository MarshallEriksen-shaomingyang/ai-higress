"use client";

import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useI18n } from "@/lib/i18n-context";
import { adminService, Role } from "@/http/admin";
import type { UserInfo } from "@/lib/api-types";
import { toast } from "sonner";

interface UserRolesDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    currentUser: UserInfo | null;
    roles: Role[];
    selectedRoleIds: string[];
    onSelectedRoleIdsChange: (ids: string[]) => void;
    onSuccess: () => void;
}

export function UserRolesDialog({
    open,
    onOpenChange,
    currentUser,
    roles,
    selectedRoleIds,
    onSelectedRoleIdsChange,
    onSuccess,
}: UserRolesDialogProps) {
    const { t } = useI18n();

    const toggleRole = (roleId: string) => {
        onSelectedRoleIdsChange(
            selectedRoleIds.includes(roleId)
                ? selectedRoleIds.filter(id => id !== roleId)
                : [...selectedRoleIds, roleId]
        );
    };

    const handleSave = async () => {
        if (!currentUser) return;
        try {
            await adminService.setUserRoles(currentUser.id, selectedRoleIds);
            toast.success("User roles updated successfully");
            onOpenChange(false);
            onSuccess();
        } catch (error) {
            toast.error("Failed to update user roles");
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
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
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        {t("providers.btn_cancel")}
                    </Button>
                    <Button onClick={handleSave}>{t("providers.btn_save")}</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
