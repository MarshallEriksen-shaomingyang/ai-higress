"use client";

import React from "react";
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
import { Loader2 } from "lucide-react";

interface DeleteKeyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  keyLabel: string;
  onConfirm: () => Promise<void>;
  isDeleting?: boolean;
}

export function DeleteKeyDialog({
  open,
  onOpenChange,
  keyLabel,
  onConfirm,
  isDeleting = false,
}: DeleteKeyDialogProps) {
  const { t } = useI18n();

  const handleConfirm = async () => {
    await onConfirm();
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {t("provider_keys.delete_dialog_title")}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t("provider_keys.delete_dialog_description")} <strong>{keyLabel}</strong>
            {t("provider_keys.delete_dialog_warning")}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>
            {t("provider_keys.delete_cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={isDeleting}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            {isDeleting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {t("provider_keys.delete_confirm")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}