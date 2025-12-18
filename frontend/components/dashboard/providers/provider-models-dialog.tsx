"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Info } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { providerService } from "@/http/provider";
import { useErrorDisplay } from "@/lib/errors";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface ProviderModelsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    providerId: string | null;
    modelsPathByProvider: Record<string, string>;
    onModelsPathChange: (providerId: string, path: string) => void;
}

export function ProviderModelsDialog({
    open,
    onOpenChange,
    providerId,
    modelsPathByProvider,
    onModelsPathChange,
}: ProviderModelsDialogProps) {
    const { t } = useI18n();
    const { showError } = useErrorDisplay();
    const [remoteModels, setRemoteModels] = useState<string[]>([]);
    const [checking, setChecking] = useState(false);

    const handleModelsPathUpdate = async () => {
        if (!providerId) return;
        const path = modelsPathByProvider[providerId] ?? "/v1/models";
        onModelsPathChange(providerId, path);

        // 触发一次上游 /models 检查，并在下方展示返回的模型名称，帮助用户确认路径配置是否生效。
        setChecking(true);
        setRemoteModels([]);
        try {
            const res = await providerService.getProviderModels(providerId);
            const ids =
                res.models?.map((m) => (m.model_id || (m as any).id || "").toString()) ||
                [];
            setRemoteModels(ids.filter(Boolean));
            if (!ids.length) {
                // 不额外弹 toast，列表为空本身就是信号。
            }
        } catch (err: any) {
            showError(err, {
                context: t("providers.models_check_error"),
            });
        } finally {
            setChecking(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="w-full max-w-2xl">
                <DialogHeader>
                    <DialogTitle>{t("providers.models_dialog_title")}</DialogTitle>
                    <DialogDescription>{t("providers.models_dialog_description")}</DialogDescription>
                </DialogHeader>

                <div className="max-h-[70vh] overflow-y-auto space-y-4">
                    {providerId && (
                        <div className="text-sm text-muted-foreground">
                            {t("providers.models_provider_id_label")}:{" "}
                            <span className="font-mono">{providerId}</span>
                        </div>
                    )}

                    {providerId && (
                        <div className="space-y-2">
                            <div className="flex items-center gap-2">
                                <Label className="text-sm font-medium">
                                    {t("providers.models_path_label")}
                                </Label>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon"
                                            className="h-7 w-7 text-muted-foreground"
                                            aria-label={t("providers.models_path_tooltip")}
                                        >
                                            <Info className="h-3.5 w-3.5" aria-hidden="true" />
                                        </Button>
                                    </TooltipTrigger>
                                    <TooltipContent>{t("providers.models_path_tooltip")}</TooltipContent>
                                </Tooltip>
                            </div>

                            <div className="flex gap-2">
                                <Input
                                    className="flex-1"
                                    placeholder={t("providers.models_path_placeholder")}
                                    value={modelsPathByProvider[providerId] ?? "/v1/models"}
                                    onChange={(event) =>
                                        onModelsPathChange(providerId, event.target.value)
                                    }
                                />
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={handleModelsPathUpdate}
                                    disabled={checking}
                                >
                                    {checking
                                        ? t("providers.models_path_checking")
                                        : t("providers.models_path_update_button")}
                                </Button>
                            </div>

                            <p className="text-xs text-muted-foreground">
                                {t("providers.models_path_note")}
                            </p>

                            {remoteModels.length > 0 && (
                                <div className="mt-2 rounded-md border bg-muted/40 p-2 max-h-36 overflow-y-auto">
                                    <div className="text-xs font-medium text-muted-foreground mb-1">
                                        {t("providers.models_check_result_label")}
                                    </div>
                                    <ul className="text-xs space-y-1 font-mono">
                                        {remoteModels.map((name) => (
                                            <li key={name}>{name}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button onClick={() => onOpenChange(false)}>{t("common.close")}</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
