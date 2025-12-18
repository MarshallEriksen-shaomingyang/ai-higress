"use client";

import { useState, useEffect, useMemo } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { ProviderPreset } from "@/http/provider-preset";
import type { CreatePrivateProviderRequest } from "@/http/provider";
import { ApiStyle, SdkVendor } from "@/http/private-provider";
import { PresetSelector } from "./preset-selector";
import { BasicProviderConfig } from "./basic-provider-config";
import { AdvancedProviderConfig } from "./advanced-provider-config";
import { useSdkVendors } from "@/lib/swr";
import { useI18n } from "@/lib/i18n-context";
import {
    Drawer,
    DrawerContent,
    DrawerDescription,
    DrawerFooter,
    DrawerHeader,
    DrawerTitle,
} from "@/components/ui/drawer";

// 表单验证 Schema（根据服务端返回的 SDK 列表动态校验）
const createProviderFormSchema = (sdkVendorOptions: string[], t: (key: string) => string) =>
    z
    .object({
        // 预设相关
        presetId: z.string().default(""),
        
        // 基础信息
        name: z
            .string()
            .trim()
            .min(1, t("providers.form_error_name_required"))
            .max(100, t("providers.form_error_name_max_length")),
        
        // Provider 配置
        providerType: z.enum(["native", "aggregator"]),
        transport: z.enum(["http", "sdk", "claude_cli"]),
        sdkVendor: z.string().optional().or(z.literal("")),
        baseUrl: z.string().trim().default(""),
        
        // API 路径
        modelsPath: z.string().trim().default("/v1/models"),
        messagesPath: z.string().trim().default(""),
        chatCompletionsPath: z.string().trim().default("/v1/chat/completions"),
        responsesPath: z.string().trim().default(""),
        
        // 路由配置
        weight: z.string().trim().default("1"),
        maxQps: z.string().trim().default(""),
        region: z.string().trim().default(""),
        
        // 成本配置
        costInput: z.string().trim().default(""),
        costOutput: z.string().trim().default(""),
        
        // 高级配置
        retryableStatusCodes: z.array(z.number()).default([]),
        customHeaders: z.record(z.string(), z.string()).default({}),
        staticModels: z.array(z.any()).default([]),
        supportedApiStyles: z.array(z.string()).default([]),
        
        // API Key（必填）
        apiKey: z.string().trim().min(1, t("providers.form_error_api_key_required")),
    })
    .superRefine((values, ctx) => {
        // 所有模式下，当未使用预设时都需要合法的 Base URL
        if (!values.baseUrl?.trim()) {
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["baseUrl"],
                message: t("providers.form_error_base_url_required"),
            });
        } else {
            try {
                new URL(values.baseUrl);
            } catch (_) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["baseUrl"],
                    message: t("providers.form_error_base_url_invalid"),
                });
            }
        }

        // SDK 模式下必须选择 SDK 类型
        if (values.transport === "sdk") {
            if (!values.sdkVendor) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["sdkVendor"],
                    message: t("providers.form_error_sdk_vendor_required"),
                });
            } else if (
                sdkVendorOptions.length > 0 &&
                !sdkVendorOptions.includes(values.sdkVendor)
            ) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["sdkVendor"],
                    message: t("providers.form_error_sdk_vendor_invalid"),
                });
            }
        }

        // 路径验证
        const paths = [
            { value: values.modelsPath, name: "modelsPath" },
            { value: values.messagesPath, name: "messagesPath" },
            { value: values.chatCompletionsPath, name: "chatCompletionsPath" },
            { value: values.responsesPath, name: "responsesPath" },
        ];

        paths.forEach(({ value, name }) => {
            if (value && !value.startsWith("/")) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: [name],
                    message: t("providers.form_error_path_format"),
                });
            }
        });

        // 至少需要一个有效的 API 路径（Messages Path、Chat Completions Path 或 Responses Path）
        const hasMessagesPath = values.messagesPath?.trim();
        const hasChatCompletionsPath = values.chatCompletionsPath?.trim();
        const hasResponsesPath = values.responsesPath?.trim();
        
        if (!hasMessagesPath && !hasChatCompletionsPath && !hasResponsesPath) {
            const errorMsg = t("providers.form_error_path_required");
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["messagesPath"],
                message: errorMsg,
            });
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["chatCompletionsPath"],
                message: errorMsg,
            });
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["responsesPath"],
                message: errorMsg,
            });
        }

        // 权重验证
        const weightValue = Number(values.weight);
        if (!values.weight || Number.isNaN(weightValue) || weightValue <= 0) {
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["weight"],
                message: t("providers.form_error_weight_required"),
            });
        }

        // QPS 验证
        if (values.maxQps) {
            const qpsValue = Number(values.maxQps);
            if (Number.isNaN(qpsValue) || qpsValue <= 0) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["maxQps"],
                    message: t("providers.form_error_qps_invalid"),
                });
            }
        }

        // 成本验证
        if (values.costInput) {
            const cost = Number(values.costInput);
            if (Number.isNaN(cost) || cost < 0) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["costInput"],
                    message: t("providers.form_error_cost_input_invalid"),
                });
            }
        }

        if (values.costOutput) {
            const cost = Number(values.costOutput);
            if (Number.isNaN(cost) || cost < 0) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["costOutput"],
                    message: t("providers.form_error_cost_output_invalid"),
                });
            }
        }
    });

type ProviderFormSchema = ReturnType<typeof createProviderFormSchema>;
type ProviderFormValues = z.input<ProviderFormSchema>;

const providerFormDefaults: ProviderFormValues = {
    presetId: "",
    name: "",
    providerType: "native",
    transport: "http",
    sdkVendor: "",
    baseUrl: "",
    modelsPath: "",
    messagesPath: "",
    chatCompletionsPath: "",
    responsesPath: "",
    weight: "1",
    maxQps: "",
    region: "",
    costInput: "",
    costOutput: "",
    retryableStatusCodes: [],
    customHeaders: {},
    staticModels: [],
    supportedApiStyles: [],
    apiKey: "",
};

const buildFormValuesFromProvider = (provider: any, isEditing: boolean = false): ProviderFormValues => {
    return {
        presetId: provider?.preset_id ?? "",
        name: provider?.name ?? "",
        providerType: provider?.provider_type ?? "native",
        transport: provider?.transport ?? "http",
        sdkVendor: provider?.sdk_vendor ?? "",
        baseUrl: provider?.base_url ?? "",
        modelsPath: provider?.models_path ?? "",
        messagesPath: provider?.messages_path ?? "",
        chatCompletionsPath: provider?.chat_completions_path ?? "",
        responsesPath: provider?.responses_path ?? "",
        weight:
            provider?.weight !== undefined && provider?.weight !== null
                ? String(provider.weight)
                : providerFormDefaults.weight,
        maxQps:
            provider?.max_qps !== undefined && provider?.max_qps !== null
                ? String(provider.max_qps)
                : providerFormDefaults.maxQps,
        region: provider?.region || "",
        costInput:
            provider?.cost_input !== undefined && provider?.cost_input !== null
                ? String(provider.cost_input)
                : providerFormDefaults.costInput,
        costOutput:
            provider?.cost_output !== undefined && provider?.cost_output !== null
                ? String(provider.cost_output)
                : providerFormDefaults.costOutput,
        retryableStatusCodes: provider?.retryable_status_codes || [],
        customHeaders: provider?.custom_headers || {},
        staticModels: provider?.static_models || [],
        supportedApiStyles: provider?.supported_api_styles || [],
        // 编辑模式下不回填 API Key（后端不返回完整密钥）
        apiKey: isEditing ? "" : (provider?.api_keys?.[0]?.key || provider?.api_key || ""),
    };
};

interface ProviderFormEnhancedProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSuccess?: () => void;
    editingProvider?: any;
}

export function ProviderFormEnhanced({
    open,
    onOpenChange,
    onSuccess,
    editingProvider,
}: ProviderFormEnhancedProps) {
    const { t } = useI18n();
    const { showError } = useErrorDisplay();
    const { data: sdkVendorsData, loading: sdkVendorsLoading } = useSdkVendors();
    const sdkVendors = sdkVendorsData?.vendors || [];
    const providerFormSchema = useMemo(
        () => createProviderFormSchema(sdkVendors, t),
        [sdkVendors, t]
    );
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [selectedPreset, setSelectedPreset] = useState<ProviderPreset | null>(null);
    const [overriddenFields, setOverriddenFields] = useState<Set<string>>(new Set());
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [editingProviderDetail, setEditingProviderDetail] = useState<any | null>(null);
    const [isLoadingEditingProvider, setIsLoadingEditingProvider] = useState(false);

    const form = useForm<ProviderFormValues>({
        resolver: zodResolver(providerFormSchema),
        defaultValues: providerFormDefaults,
        mode: "onSubmit",
    });

    const transport = form.watch("transport");
    const isSdkTransport = transport === "sdk";

    useEffect(() => {
        if (open) return;
        form.reset(providerFormDefaults);
        setSelectedPreset(null);
        setOverriddenFields(new Set());
        setShowAdvanced(false);
        setEditingProviderDetail(null);
        setIsLoadingEditingProvider(false);
        setIsSubmitting(false);
    }, [open, form]);

    // 编辑模式下拉取最新配置
    useEffect(() => {
        let cancelled = false;

        if (!editingProvider || !open) {
            setEditingProviderDetail(null);
            setIsLoadingEditingProvider(false);
            return;
        }

        setEditingProviderDetail(null);
        setIsLoadingEditingProvider(true);

        const fetchProviderDetail = async () => {
            try {
                const { providerService } = await import("@/http/provider");
                const detail = await providerService.getProvider(editingProvider.provider_id);
                if (!cancelled) {
                    setEditingProviderDetail(detail);
                }
            } catch (error) {
                if (!cancelled) {
                    showError(error, { context: t("providers.form_context_loading_detail") });
                }
            } finally {
                if (!cancelled) {
                    setIsLoadingEditingProvider(false);
                }
            }
        };

        fetchProviderDetail();

        return () => {
            cancelled = true;
        };
    }, [editingProvider, open, showError]);

    // 根据当前模式回填表单
    useEffect(() => {
        if (!open) {
            return;
        }

        const sourceData = editingProviderDetail || editingProvider;

        if (sourceData) {
            const formValues = buildFormValuesFromProvider(sourceData, Boolean(editingProvider));
            form.reset(formValues);
            setOverriddenFields(new Set());
            if (editingProvider) {
                setSelectedPreset(null);
            }
        } else {
            form.reset(providerFormDefaults);
            setOverriddenFields(new Set());
        }
    }, [editingProviderDetail, editingProvider, form, open]);

    // 当选择预设时，填充表单
    useEffect(() => {
        if (selectedPreset && !editingProvider) {
            const presetValues: Partial<ProviderFormValues> = {
                presetId: selectedPreset.preset_id,
                providerType: selectedPreset.provider_type,
                transport: selectedPreset.transport,
                sdkVendor: selectedPreset.sdk_vendor ?? "",
                baseUrl: selectedPreset.base_url,
                modelsPath: selectedPreset.models_path,
                messagesPath: selectedPreset.messages_path || "",
                chatCompletionsPath: selectedPreset.chat_completions_path,
                responsesPath: selectedPreset.responses_path || "",
                retryableStatusCodes: selectedPreset.retryable_status_codes || [],
                customHeaders: selectedPreset.custom_headers || {},
                staticModels: selectedPreset.static_models || [],
                supportedApiStyles: selectedPreset.supported_api_styles || [],
            };

            // 只更新未被覆盖的字段
            Object.entries(presetValues).forEach(([key, value]) => {
                if (!overriddenFields.has(key)) {
                    form.setValue(key as any, value);
                }
            });

            // 如果没有名称，使用预设名称
            if (!form.getValues("name")) {
                form.setValue("name", selectedPreset.display_name);
            }
        }
    }, [selectedPreset, form, overriddenFields, editingProvider]);

    // 标记字段为已覆盖
    const markFieldAsOverridden = (fieldName: string) => {
        setOverriddenFields((prev) => new Set(prev).add(fieldName));
    };

    // 检查字段是否被覆盖
    const isFieldOverridden = (fieldName: string) => {
        return overriddenFields.has(fieldName);
    };

    const handleFormSubmit = async (values: any) => {
        try {
            setIsSubmitting(true);

            // 从 auth store 获取当前用户 ID
            const { useAuthStore } = await import("@/lib/stores/auth-store");
            const userId = useAuthStore.getState().user?.id;
            
            if (!userId) {
                throw new Error(t("providers.form_error_user_not_logged_in"));
            }

            // 使用用户级别的 API
            const { providerService } = await import("@/http/provider");
            
            if (editingProvider) {
                // 更新模式
                const updatePayload = {
                    name: values.name.trim(),
                    provider_type: values.providerType,
                    transport: values.transport,
                    sdk_vendor: values.transport === "sdk" && values.sdkVendor ? values.sdkVendor as SdkVendor : undefined,
                    base_url: values.baseUrl?.trim(),
                    models_path: values.modelsPath?.trim() || undefined,
                    messages_path: values.messagesPath?.trim() || undefined,
                    chat_completions_path: values.chatCompletionsPath?.trim() || undefined,
                    responses_path: values.responsesPath?.trim() || undefined,
                    region: values.region?.trim(),
                    max_qps: values.maxQps?.trim() ? Number(values.maxQps) : undefined,
                    cost_input: values.costInput?.trim() ? Number(values.costInput) : undefined,
                    cost_output: values.costOutput?.trim() ? Number(values.costOutput) : undefined,
                    weight: Number(values.weight),
                    retryable_status_codes: values.retryableStatusCodes.length > 0 ? values.retryableStatusCodes : undefined,
                    custom_headers: Object.keys(values.customHeaders).length > 0 ? values.customHeaders : undefined,
                    static_models: values.staticModels.length > 0 ? values.staticModels : undefined,
                    supported_api_styles: values.supportedApiStyles.length > 0 ? values.supportedApiStyles as ApiStyle[] : undefined,
                };

                await providerService.updatePrivateProvider(userId, editingProvider.provider_id, updatePayload);
                toast.success(t("providers.form_success_updated"));
            } else {
                // 创建模式
                const createPayload: CreatePrivateProviderRequest = {
                    preset_id: values.presetId || undefined,
                    name: values.name.trim() || undefined,
                    base_url: values.baseUrl?.trim() || undefined,
                    api_key: values.apiKey.trim(),
                    provider_type: values.providerType,
                    transport: values.transport,
                    weight: Number(values.weight),
                };

                // SDK 模式下显式传递 sdk_vendor
                if (values.transport === "sdk" && values.sdkVendor) {
                    createPayload.sdk_vendor = values.sdkVendor as SdkVendor;
                }

                // API 路径
                if (values.modelsPath?.trim()) createPayload.models_path = values.modelsPath.trim();
                if (values.messagesPath?.trim()) createPayload.messages_path = values.messagesPath.trim();
                if (values.chatCompletionsPath?.trim()) createPayload.chat_completions_path = values.chatCompletionsPath.trim();
                if (values.responsesPath?.trim()) createPayload.responses_path = values.responsesPath.trim();

                // 可选字段
                if (values.region?.trim()) createPayload.region = values.region.trim();
                if (values.maxQps?.trim()) createPayload.max_qps = Number(values.maxQps);
                if (values.costInput?.trim()) createPayload.cost_input = Number(values.costInput);
                if (values.costOutput?.trim()) createPayload.cost_output = Number(values.costOutput);
                // 高级配置
                if (values.retryableStatusCodes.length > 0) {
                    createPayload.retryable_status_codes = values.retryableStatusCodes;
                }
                if (Object.keys(values.customHeaders).length > 0) {
                    createPayload.custom_headers = values.customHeaders as Record<string, string>;
                }
                if (values.staticModels.length > 0) {
                    createPayload.static_models = values.staticModels;
                }
                if (values.supportedApiStyles.length > 0) {
                    createPayload.supported_api_styles = values.supportedApiStyles as ApiStyle[];
                }

                await providerService.createPrivateProvider(userId, createPayload);
                toast.success(t("providers.form_success_created"));
            }
            
            form.reset(providerFormDefaults);
            setSelectedPreset(null);
            setOverriddenFields(new Set());
            setShowAdvanced(false);
            onOpenChange(false);
            
            if (onSuccess) {
                onSuccess();
            }
        } catch (error) {
            showError(error, {
                context: editingProvider ? t("providers.form_context_updating") : t("providers.form_context_creating")
            });
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleCancel = () => {
        form.reset(providerFormDefaults);
        setSelectedPreset(null);
        setOverriddenFields(new Set());
        setShowAdvanced(false);
        onOpenChange(false);
    };

    return (
        <Drawer open={open} onOpenChange={onOpenChange} direction="right">
            <DrawerContent className="h-full w-full data-[vaul-drawer-direction=right]:sm:max-w-3xl data-[vaul-drawer-direction=right]:lg:max-w-4xl">
                <DrawerHeader>
                    <DrawerTitle className="flex items-center justify-center gap-2 md:justify-start">
                        <Sparkles className="h-5 w-5 text-primary" />
                        {editingProvider ? t("providers.form_edit_title") : t("providers.form_create_title")}
                    </DrawerTitle>
                    <DrawerDescription>
                        {editingProvider
                            ? t("providers.form_edit_description")
                            : t("providers.form_create_description")}
                    </DrawerDescription>
                </DrawerHeader>

                <Form {...form}>
                    <form
                        onSubmit={form.handleSubmit(handleFormSubmit)}
                        className="flex min-h-0 flex-1 flex-col"
                    >
                        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
                            <fieldset
                                disabled={Boolean(editingProvider && isLoadingEditingProvider)}
                                aria-busy={editingProvider ? isLoadingEditingProvider : undefined}
                                className="space-y-6"
                            >
                                <PresetSelector
                                    selectedPresetId={selectedPreset?.preset_id || null}
                                    onPresetSelect={setSelectedPreset}
                                    disabled={isSubmitting}
                                />

                                {editingProvider && isLoadingEditingProvider && (
                                    <div className="rounded-md border border-dashed border-muted-foreground/40 bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
                                        {t("providers.form_loading_config")}
                                    </div>
                                )}

                                <BasicProviderConfig
                                    form={form}
                                    isFieldOverridden={isFieldOverridden}
                                    markFieldAsOverridden={markFieldAsOverridden}
                                    isSdkTransport={isSdkTransport}
                                    sdkVendorOptions={sdkVendors}
                                    sdkVendorsLoading={sdkVendorsLoading}
                                />

                                <AdvancedProviderConfig
                                    form={form}
                                    isFieldOverridden={isFieldOverridden}
                                    markFieldAsOverridden={markFieldAsOverridden}
                                    showAdvanced={showAdvanced}
                                    onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
                                />
                            </fieldset>
                        </div>

                        <DrawerFooter className="border-t bg-background/80 backdrop-blur">
                            <div className="flex w-full justify-end gap-2">
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={handleCancel}
                                    disabled={isSubmitting}
                                >
                                    {t("providers.form_cancel")}
                                </Button>
                                <Button
                                    type="submit"
                                    disabled={isSubmitting || Boolean(editingProvider && isLoadingEditingProvider)}
                                >
                                    {isSubmitting
                                        ? editingProvider
                                            ? t("providers.form_updating")
                                            : t("providers.form_creating")
                                        : editingProvider
                                            ? isLoadingEditingProvider
                                                ? t("providers.form_waiting_config")
                                                : t("providers.form_update")
                                            : t("providers.form_create")}
                                </Button>
                            </div>
                        </DrawerFooter>
                    </form>
                </Form>
            </DrawerContent>
        </Drawer>
    );
}
