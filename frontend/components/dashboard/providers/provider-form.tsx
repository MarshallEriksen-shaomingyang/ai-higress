"use client";

import { useState, useEffect, useMemo } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Form } from "@/components/ui/form";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { ProviderPreset } from "@/http/provider-preset";
import { CreatePrivateProviderRequest, privateProviderService, ApiStyle, SdkVendor } from "@/http/private-provider";
import { PresetSelector } from "./preset-selector";
import { BasicProviderConfig } from "./basic-provider-config";
import { AdvancedProviderConfig } from "./advanced-provider-config";
import { useSdkVendors } from "@/lib/swr";

// 表单验证 Schema（根据服务端返回的 SDK 列表动态校验）
const createProviderFormSchema = (sdkVendorOptions: string[]) =>
    z
    .object({
        // 预设相关
        presetId: z.string().default(""),
        
        // 基础信息
        name: z
            .string()
            .trim()
            .min(1, "Provider 名称不能为空")
            .max(100, "Provider 名称最长 100 个字符"),
        
        // Provider 配置
        providerType: z.enum(["native", "aggregator"]),
        transport: z.enum(["http", "sdk"]),
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
        apiKey: z.string().trim().min(1, "API Key 不能为空"),
    })
    .superRefine((values, ctx) => {
        // 所有模式下，当未使用预设时都需要合法的 Base URL
        if (!values.baseUrl?.trim()) {
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["baseUrl"],
                message: "Base URL 不能为空",
            });
        } else {
            try {
                new URL(values.baseUrl);
            } catch (_) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["baseUrl"],
                    message: "请输入合法的 URL",
                });
            }
        }

        // SDK 模式下必须选择 SDK 类型
        if (values.transport === "sdk") {
            if (!values.sdkVendor) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["sdkVendor"],
                    message: "SDK 模式必须选择 SDK 类型",
                });
            } else if (
                sdkVendorOptions.length > 0 &&
                !sdkVendorOptions.includes(values.sdkVendor)
            ) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["sdkVendor"],
                    message: "SDK 类型不在支持列表中",
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
                    message: "路径应以 / 开头",
                });
            }
        });

        // 权重验证
        const weightValue = Number(values.weight);
        if (!values.weight || Number.isNaN(weightValue) || weightValue <= 0) {
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["weight"],
                message: "请输入大于 0 的权重",
            });
        }

        // QPS 验证
        if (values.maxQps) {
            const qpsValue = Number(values.maxQps);
            if (Number.isNaN(qpsValue) || qpsValue <= 0) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["maxQps"],
                    message: "Max QPS 需为大于 0 的数字",
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
                    message: "输入成本必须为非负数",
                });
            }
        }

        if (values.costOutput) {
            const cost = Number(values.costOutput);
            if (Number.isNaN(cost) || cost < 0) {
                ctx.addIssue({
                    code: z.ZodIssueCode.custom,
                    path: ["costOutput"],
                    message: "输出成本必须为非负数",
                });
            }
        }
    });

type ProviderFormSchema = ReturnType<typeof createProviderFormSchema>;
type ProviderFormValues = z.infer<ProviderFormSchema>;

const providerFormDefaults: ProviderFormValues = {
    presetId: "",
    name: "",
    providerType: "native",
    transport: "http",
    sdkVendor: "",
    baseUrl: "",
    modelsPath: "/v1/models",
    messagesPath: "",
    chatCompletionsPath: "/v1/chat/completions",
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
    const { showError } = useErrorDisplay();
    const { data: sdkVendorsData, loading: sdkVendorsLoading } = useSdkVendors();
    const sdkVendors = sdkVendorsData?.vendors || [];
    const providerFormSchema = useMemo(
        () => createProviderFormSchema(sdkVendors),
        [sdkVendors]
    );
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [selectedPreset, setSelectedPreset] = useState<ProviderPreset | null>(null);
    const [overriddenFields, setOverriddenFields] = useState<Set<string>>(new Set());
    const [isSubmitting, setIsSubmitting] = useState(false);

    const form = useForm<ProviderFormValues>({
        resolver: zodResolver(providerFormSchema),
        defaultValues: providerFormDefaults,
        mode: "onSubmit",
    });

    const transport = form.watch("transport");
    const isSdkTransport = transport === "sdk";

    // 当编辑提供商时，填充表单
    useEffect(() => {
        if (editingProvider) {
            form.reset({
                presetId: "",
                name: editingProvider.name || "",
                providerType: editingProvider.provider_type || "native",
                transport: editingProvider.transport || "http",
                sdkVendor: editingProvider.sdk_vendor || "",
                baseUrl: editingProvider.base_url || "",
                modelsPath: editingProvider.models_path || "/v1/models",
                messagesPath: editingProvider.messages_path || "",
                chatCompletionsPath: editingProvider.chat_completions_path || "/v1/chat/completions",
                responsesPath: editingProvider.responses_path || "",
                weight: String(editingProvider.weight || "1"),
                maxQps: String(editingProvider.max_qps || ""),
                region: editingProvider.region || "",
                costInput: String(editingProvider.cost_input || ""),
                costOutput: String(editingProvider.cost_output || ""),
                retryableStatusCodes: editingProvider.retryable_status_codes || [],
                customHeaders: editingProvider.custom_headers || {},
                staticModels: editingProvider.static_models || [],
                supportedApiStyles: editingProvider.supported_api_styles || [],
                apiKey: editingProvider.api_keys?.[0]?.key || "",
            });
        } else if (open) {
            form.reset(providerFormDefaults);
        }
    }, [editingProvider, form, open]);

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
                throw new Error("用户未登录");
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
                    models_path: values.modelsPath?.trim(),
                    messages_path: values.messagesPath?.trim(),
                    chat_completions_path: values.chatCompletionsPath?.trim(),
                    responses_path: values.responsesPath?.trim(),
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
                toast.success("Provider 更新成功");
            } else {
                // 创建模式
                const createPayload: CreatePrivateProviderRequest = {
                    preset_id: values.presetId || undefined,
                    name: values.name.trim(),
                    provider_type: values.providerType,
                    transport: values.transport,
                    weight: Number(values.weight),
                };

                // Base URL（所有模式下都需要）
                if (values.baseUrl?.trim()) {
                    createPayload.base_url = values.baseUrl.trim();
                }

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
                if (values.apiKey?.trim()) createPayload.api_key = values.apiKey.trim();

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
                toast.success("Provider 创建成功");
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
                context: editingProvider ? "更新 Provider" : "创建 Provider"
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
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-primary" />
                        {editingProvider ? "编辑 Private Provider" : "创建 Private Provider"}
                    </DialogTitle>
                    <DialogDescription>
                        {editingProvider 
                            ? "修改提供商配置信息" 
                            : "选择预设快速创建，或完全自定义配置。支持基于预设的字段覆盖。"}
                    </DialogDescription>
                </DialogHeader>

                <Form {...form}>
                    <form onSubmit={form.handleSubmit(handleFormSubmit)} className="space-y-6 py-4">
                        {/* 预设选择器 */}
                        <PresetSelector
                            selectedPresetId={selectedPreset?.preset_id || null}
                            onPresetSelect={setSelectedPreset}
                            disabled={isSubmitting}
                        />

                        {/* 基础配置 */}
                        <BasicProviderConfig
                            form={form}
                            isFieldOverridden={isFieldOverridden}
                            markFieldAsOverridden={markFieldAsOverridden}
                            isSdkTransport={isSdkTransport}
                            sdkVendorOptions={sdkVendors}
                            sdkVendorsLoading={sdkVendorsLoading}
                        />

                        {/* 高级配置（可折叠） */}
                        <AdvancedProviderConfig
                            form={form}
                            isFieldOverridden={isFieldOverridden}
                            markFieldAsOverridden={markFieldAsOverridden}
                            showAdvanced={showAdvanced}
                            onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
                        />

                        <DialogFooter>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleCancel}
                                disabled={isSubmitting}
                            >
                                取消
                            </Button>
                            <Button type="submit" disabled={isSubmitting}>
                                {isSubmitting ? (editingProvider ? "更新中..." : "创建中...") : (editingProvider ? "更新 Provider" : "创建 Provider")}
                            </Button>
                        </DialogFooter>
                    </form>
                </Form>
            </DialogContent>
        </Dialog>
    );
}
