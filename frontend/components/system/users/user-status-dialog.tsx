"use client";

import { useState } from "react";
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
import { useI18n } from "@/lib/i18n-context";
import { userService } from "@/http/user";
import type { UserInfo } from "@/lib/api-types";
import { toast } from "sonner";

interface UserStatusDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    targetUser: UserInfo | null;
    targetActive: boolean | null;
    onSuccess: (updatedUser: UserInfo) => void;
}

export function UserStatusDialog({
    open,
    onOpenChange,
    targetUser,
    targetActive,
    onSuccess,
}: UserStatusDialogProps) {
    const { t } = useI18n();
    const [updating, setUpdating] = useState(false);

    const handleConfirm = async () => {
        if (!targetUser || targetActive === null) return;

        try {
            setUpdating(true);
            const updated = await userService.updateUserStatus(targetUser.id, {
                is_active: targetActive,
            });

            toast.success(
                targetActive
                    ? t("users.status_enable_success")
                    : t("users.status_disable_success")
            );

            onSuccess(updated);
            onOpenChange(false);
        } catch (error) {
            console.error("Failed to update user status:", error);
            toast.error(
                targetActive
                    ? t("users.status_enable_error")
                    : t("users.status_disable_error")
            );
        } finally {
            setUpdating(false);
        }
    };

    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent>
                <AlertDialogHeader>
                    <AlertDialogTitle>
                        {targetActive
                            ? t("users.status_enable_title")
                            : t("users.status_disable_title")}
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                        {targetActive
                            ? t("users.status_enable_description")
                            : t("users.status_disable_description")}
                    </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                    <AlertDialogCancel disabled={updating}>
                        {t("users.status_dialog_cancel")}
                    </AlertDialogCancel>
                    <AlertDialogAction disabled={updating} onClick={handleConfirm}>
                        {t("users.status_dialog_confirm")}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}
