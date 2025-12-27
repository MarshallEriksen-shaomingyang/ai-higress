"use client";

import { Button } from "@/components/ui/button";
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

  const handleOpenChange = (nextOpen: boolean) => {
    if (isDeleting) return;
    onOpenChange(nextOpen);
  };

  const handleConfirm = async () => {
    await onConfirm();
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="sm:max-w-md">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {t("provider_keys.delete_dialog_title")}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {t("provider_keys.delete_dialog_description")}{" "}
            <span className="font-mono font-semibold">{keyLabel}</span>
            {t("provider_keys.delete_dialog_warning")}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel asChild>
            <Button variant="outline" disabled={isDeleting}>
              {t("provider_keys.delete_cancel")}
            </Button>
          </AlertDialogCancel>
          <AlertDialogAction asChild>
            <Button
              variant="destructive"
              onClick={handleConfirm}
              disabled={isDeleting}
            >
              {isDeleting && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              {t("provider_keys.delete_confirm")}
            </Button>
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
