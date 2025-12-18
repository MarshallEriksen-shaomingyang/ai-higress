"use client";

import { buttonVariants } from "@/components/ui/button";
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

export interface DeleteProviderDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  providerId: string | null;
  isDeleting: boolean;
  onConfirm: () => void;
}

export function DeleteProviderDialog({
  open,
  onOpenChange,
  providerId,
  isDeleting,
  onConfirm,
}: DeleteProviderDialogProps) {
  const { t } = useI18n();

  if (!providerId) return null;

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {t("providers.delete_dialog_title")}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t("providers.delete_dialog_description")}{" "}
            <span className="font-mono font-semibold">{providerId}</span>
            {t("providers.delete_dialog_warning")}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel
            disabled={isDeleting}
            className={buttonVariants({ variant: "outline" })}
          >
            {t("providers.btn_cancel")}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className={buttonVariants({ variant: "destructive" })}
          >
            {isDeleting
              ? t("providers.deleting_button")
              : t("providers.delete_button")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
