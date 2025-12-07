"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip";
import { Info, Plus, Minus } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";
import { providerService } from "@/http/provider";
import { useErrorDisplay } from "@/lib/errors";

interface ProviderModelsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    providerId: string | null;
    modelsPathByProvider: Record<string, string>;
    providerModels: Record<string, string[]>;
    selectedModelByProvider: Record<string, string | null>;
    newModelNameByProvider: Record<string, string>;
    onModelsPathChange: (providerId: string, path: string) => void;
    onAddModel: () => void;
    onRemoveModel: () => void;
    onSelectModel: (model: string) => void;
    onModelNameChange: (name: string) => void;
    onSave: () => void;
}

export function ProviderModelsDialog({
    open,
    onOpenChange,
    providerId,
    modelsPathByProvider,
    providerModels,
    selectedModelByProvider,
    newModelNameByProvider,
    onModelsPathChange,
    onAddModel,
    onRemoveModel,
    onSelectModel,
    onModelNameChange,
    onSave,
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
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{t("providers.models_dialog_title")}</DialogTitle>
                    <DialogDescription>
                        {t("providers.models_dialog_description")}
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                    <div className="text-sm text-muted-foreground">
                        {providerId && (
                            <span>
                                Provider ID:{" "}
                                <span className="font-mono">{providerId}</span>
                            </span>
                        )}
                    </div>

                    {providerId && (
                        <div className="space-y-2">
                            <label className="flex items-center gap-1 text-sm font-medium">
                                <span>{t("providers.models_path_label")}</span>
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <button
                                            type="button"
                                            className="inline-flex h-4 w-4 items-center justify-center text-muted-foreground"
                                        >
                                            <Info
                                                className="h-3 w-3"
                                                aria-hidden="true"
                                            />
                                        </button>
                                    </TooltipTrigger>
                                    <TooltipContent>
                                        {t("providers.models_path_tooltip")}
                                    </TooltipContent>
                                </Tooltip>
                            </label>
                            <div className="flex gap-2">
                                <Input
                                    className="flex-1"
                                    placeholder={t("providers.models_path_placeholder")}
                                    value={
                                        modelsPathByProvider[providerId] ??
                                        "/v1/models"
                                    }
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

                    {providerId && (
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>{t("providers.models_list_label")}</span>
                            <div className="flex items-center gap-2">
                                <Button
                                    type="button"
                                    size="icon"
                                    variant="outline"
                                    onClick={onAddModel}
                                    aria-label={t("providers.models_add_aria")}
                                >
                                    <Plus className="h-4 w-4" />
                                </Button>
                                <Button
                                    type="button"
                                    size="icon"
                                    variant="outline"
                                    onClick={onRemoveModel}
                                    aria-label={t("providers.models_remove_aria")}
                                    disabled={
                                        !selectedModelByProvider[providerId]
                                    }
                                >
                                    <Minus className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                    )}

                    <div className="rounded-md border bg-muted/40 p-4 max-h-[40vh] overflow-y-auto">
                        <ul className="space-y-2 text-sm">
                            {providerId &&
                            providerModels[providerId] &&
                            providerModels[providerId].length > 0 ? (
                                providerModels[providerId].map((model) => (
                                    <li
                                        key={model}
                                        className={`flex items-center justify-between rounded border bg-background px-3 py-2 cursor-pointer ${
                                            selectedModelByProvider[providerId] ===
                                            model
                                                ? "border-primary bg-primary/10"
                                                : ""
                                        }`}
                                        onClick={() => onSelectModel(model)}
                                    >
                                        <span className="font-mono text-xs sm:text-sm">
                                            {model}
                                        </span>
                                        <span className="text-xs text-muted-foreground">
                                            {t("providers.models_example_tag")}
                                        </span>
                                    </li>
                                ))
                            ) : (
                                <li className="text-xs text-muted-foreground">
                                    {t("providers.models_empty_hint")}
                                </li>
                            )}
                        </ul>
                    </div>
                    {providerId && (
                        <div className="mt-3 flex gap-2">
                            <Input
                                placeholder={t("providers.models_input_placeholder")}
                                value={newModelNameByProvider[providerId] ?? ""}
                                onChange={(event) =>
                                    onModelNameChange(event.target.value)
                                }
                            />
                        </div>
                    )}
                </div>
                <DialogFooter>
                    <Button
                        variant="outline"
                        onClick={() => onOpenChange(false)}
                    >
                        {t("providers.btn_cancel")}
                    </Button>
                    <Button onClick={onSave}>
                        {t("providers.btn_save")}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
