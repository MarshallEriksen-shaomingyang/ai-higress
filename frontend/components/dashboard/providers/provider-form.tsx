"use client";

import { useState, useEffect } from "react";
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
import { ProviderPreset } from "@/http/provider-preset";
import { CreatePrivateProviderRequest, privateProviderService, ApiStyle, SdkVendor } from "@/http/private-provider";
import { PresetSelector } from "./preset-selector";
import { BasicProviderConfig } from "./basic-provider-config";
import { AdvancedProviderConfig } from "./advanced-provider-config";

// 表单验证 Schema
const providerFormSchema = z
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
        sdkVendor: z.enum(["openai", "google", "claude"]).optional().or(z.literal("")),
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
        if (values.transport === "sdk" && !values.sdkVendor) {
            ctx.addIssue({
                code: z.ZodIssueCode.custom,
                path: ["sdkVendor"],
                message: "SDK 模式必须选择 SDK 类型",
            });
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

type ProviderFormValues = z.infer<typeof providerFormSchema>;

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
}

export function ProviderFormEnhanced({
    open,
    onOpenChange,
    onSuccess,
}: ProviderFormEnhancedProps) {
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [selectedPreset, setSelectedPreset] = useState<ProviderPreset | null>(null);
    const [overriddenFields, setOverriddenFields] = useState<Set<string>>(new Set());
    const [isSubmitting, setIsSubmitting] = useState(false);

    const form = useForm<ProviderFormValues>({
        // @ts-ignore
        resolver: zodResolver(providerFormSchema),
        defaultValues: providerFormDefaults,
        mode: "onSubmit",
    });

    const transport = form.watch("transport");
    const isSdkTransport = transport === "sdk";

    // 当选择预设时，填充表单
    useEffect(() => {
        if (selectedPreset) {
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
    }, [selectedPreset, form, overriddenFields]);

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

            const payload: CreatePrivateProviderRequest = {
                preset_id: values.presetId || undefined,
                name: values.name.trim(),
                provider_type: values.providerType,
                transport: values.transport,
                weight: Number(values.weight),
            };

            // Base URL（所有模式下都需要）
            if (values.baseUrl?.trim()) {
                payload.base_url = values.baseUrl.trim();
            }

            // SDK 模式下显式传递 sdk_vendor
            if (values.transport === "sdk" && values.sdkVendor) {
                payload.sdk_vendor = values.sdkVendor as SdkVendor;
            }

            // API 路径
            if (values.modelsPath?.trim()) payload.models_path = values.modelsPath.trim();
            if (values.messagesPath?.trim()) payload.messages_path = values.messagesPath.trim();
            if (values.chatCompletionsPath?.trim()) payload.chat_completions_path = values.chatCompletionsPath.trim();
            if (values.responsesPath?.trim()) payload.responses_path = values.responsesPath.trim();

            // 可选字段
            if (values.region?.trim()) payload.region = values.region.trim();
            if (values.maxQps?.trim()) payload.max_qps = Number(values.maxQps);
            if (values.costInput?.trim()) payload.cost_input = Number(values.costInput);
            if (values.costOutput?.trim()) payload.cost_output = Number(values.costOutput);
            if (values.apiKey?.trim()) payload.api_key = values.apiKey.trim();

            // 高级配置
            if (values.retryableStatusCodes.length > 0) {
                payload.retryable_status_codes = values.retryableStatusCodes;
            }
            if (Object.keys(values.customHeaders).length > 0) {
                payload.custom_headers = values.customHeaders as Record<string, string>;
            }
            if (values.staticModels.length > 0) {
                payload.static_models = values.staticModels;
            }
            if (values.supportedApiStyles.length > 0) {
                payload.supported_api_styles = values.supportedApiStyles as ApiStyle[];
            }

            // 使用用户级别的 API
            const { providerService } = await import("@/http/provider");
            await providerService.createPrivateProvider(userId, payload);
            
            toast.success("Provider 创建成功");
            form.reset(providerFormDefaults);
            setSelectedPreset(null);
            setOverriddenFields(new Set());
            setShowAdvanced(false);
            onOpenChange(false);
            
            if (onSuccess) {
                onSuccess();
            }
        } catch (error: any) {
            console.error("创建 Provider 失败:", error);
            const message = error.response?.data?.detail || error.message || "创建失败";
            toast.error(message);
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
                        创建 Private Provider
                    </DialogTitle>
                    <DialogDescription>
                        选择预设快速创建，或完全自定义配置。支持基于预设的字段覆盖。
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
                                {isSubmitting ? "创建中..." : "创建 Provider"}
                            </Button>
                        </DialogFooter>
                    </form>
                </Form>
            </DialogContent>
        </Dialog>
    );
}
