"use client";

import { Input } from "@/components/ui/input";
import { FormField } from "@/components/ui/form";
import { JsonEditor } from "./json-editor";
import { NumberArrayEditor } from "./array-editor";
import { ApiStylesConfig } from "./api-styles-config";
import { ChevronDown, ChevronUp } from "lucide-react";
import { useI18n } from "@/lib/i18n-context";

// 类型安全的FormField包装器
const SafeFormField = FormField as any;

interface AdvancedProviderConfigProps {
    form: any;
    isFieldOverridden: (fieldName: string) => boolean;
    markFieldAsOverridden: (fieldName: string) => void;
    showAdvanced: boolean;
    onToggleAdvanced: () => void;
}

export function AdvancedProviderConfig({
    form,
    isFieldOverridden,
    markFieldAsOverridden,
    showAdvanced,
    onToggleAdvanced
}: AdvancedProviderConfigProps) {
    const { t } = useI18n();

    return (
        <div className="space-y-3">
            <button
                type="button"
                className="flex w-full items-center justify-between rounded-md border border-dashed border-muted-foreground/40 bg-muted/40 px-4 py-3 text-left"
                onClick={onToggleAdvanced}
            >
                <span className="font-medium text-sm">{t("providers.form_section_advanced")}</span>
                {showAdvanced ? (
                    <ChevronUp className="h-4 w-4" />
                ) : (
                    <ChevronDown className="h-4 w-4" />
                )}
            </button>

            {showAdvanced && (
                <div className="space-y-4 rounded-md border bg-muted/20 p-4">
                    {/* API 路径配置 */}
                    <div className="space-y-4">
                        <div>
                            <h4 className="text-sm font-medium">{t("providers.form_section_api_paths")}</h4>
                            <p className="text-xs text-muted-foreground mt-1">
                                {t("providers.form_section_api_paths_help")}
                            </p>
                        </div>

                        {/* Models Path - 可选 */}
                        <SafeFormField
                            control={form.control}
                            name="modelsPath"
                            render={({ field }: { field: any }) => (
                                <div className="space-y-2">
                                    <label className="text-xs font-medium">
                                        {t("providers.form_field_models_path")} <span className="text-muted-foreground font-normal">{t("providers.form_field_optional")}</span>
                                    </label>
                                    <p className="text-xs text-muted-foreground">
                                        {t("providers.form_field_models_path_help")}
                                    </p>
                                    <Input
                                        {...field}
                                        placeholder={t("providers.form_field_models_path_placeholder")}
                                        className="text-sm"
                                        onChange={(e) => {
                                            field.onChange(e);
                                            markFieldAsOverridden("modelsPath");
                                        }}
                                    />
                                </div>
                            )}
                        />

                        {/* API 端点 - 至少选择一个 */}
                        <div className="space-y-3 pt-2 border-t">
                            <div>
                                <h5 className="text-xs font-medium">
                                    {t("providers.form_section_api_endpoints")} <span className="text-destructive">*</span>
                                </h5>
                                <p className="text-xs text-muted-foreground mt-1">
                                    {t("providers.form_section_api_endpoints_help")}
                                </p>
                            </div>

                            <div className="grid grid-cols-1 gap-4">
                                <SafeFormField
                                    control={form.control}
                                    name="messagesPath"
                                    render={({ field }: { field: any }) => (
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium">{t("providers.form_field_messages_path")}</label>
                                            <p className="text-xs text-muted-foreground">
                                                {t("providers.form_field_messages_path_help")}
                                            </p>
                                            <Input
                                                {...field}
                                                placeholder={t("providers.form_field_messages_path_placeholder")}
                                                className="text-sm"
                                                onChange={(e) => {
                                                    field.onChange(e);
                                                    markFieldAsOverridden("messagesPath");
                                                }}
                                            />
                                        </div>
                                    )}
                                />

                                <SafeFormField
                                    control={form.control}
                                    name="chatCompletionsPath"
                                    render={({ field }: { field: any }) => (
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium">{t("providers.form_field_chat_completions_path")}</label>
                                            <p className="text-xs text-muted-foreground">
                                                {t("providers.form_field_chat_completions_path_help")}
                                            </p>
                                            <Input
                                                {...field}
                                                placeholder={t("providers.form_field_chat_completions_path_placeholder")}
                                                className="text-sm"
                                                onChange={(e) => {
                                                    field.onChange(e);
                                                    markFieldAsOverridden("chatCompletionsPath");
                                                }}
                                            />
                                        </div>
                                    )}
                                />

                                <SafeFormField
                                    control={form.control}
                                    name="responsesPath"
                                    render={({ field }: { field: any }) => (
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium">{t("providers.form_field_responses_path")}</label>
                                            <p className="text-xs text-muted-foreground">
                                                {t("providers.form_field_responses_path_help")}
                                            </p>
                                            <Input
                                                {...field}
                                                placeholder={t("providers.form_field_responses_path_placeholder")}
                                                className="text-sm"
                                                onChange={(e) => {
                                                    field.onChange(e);
                                                    markFieldAsOverridden("responsesPath");
                                                }}
                                            />
                                        </div>
                                    )}
                                />

                                <SafeFormField
                                    control={form.control}
                                    name="imagesGenerationsPath"
                                    render={({ field }: { field: any }) => (
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium">
                                                {t("providers.form_field_images_generations_path")}{" "}
                                                <span className="text-muted-foreground font-normal">{t("providers.form_field_optional")}</span>
                                            </label>
                                            <p className="text-xs text-muted-foreground">
                                                {t("providers.form_field_images_generations_path_help")}
                                            </p>
                                            <Input
                                                {...field}
                                                placeholder={t("providers.form_field_images_generations_path_placeholder")}
                                                className="text-sm"
                                                onChange={(e) => {
                                                    field.onChange(e);
                                                    markFieldAsOverridden("imagesGenerationsPath");
                                                }}
                                            />
                                        </div>
                                    )}
                                />
                            </div>
                        </div>
                    </div>

                    {/* 路由配置 */}
                    <div className="space-y-3">
                        <h4 className="text-sm font-medium">{t("providers.form_section_routing")}</h4>
                        <div className="grid grid-cols-3 gap-4">
                            <SafeFormField
                                control={form.control}
                                name="weight"
                                render={({ field }: { field: any }) => (
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium">{t("providers.form_field_weight")}</label>
                                        <Input
                                            {...field}
                                            type="number"
                                            step="0.1"
                                            placeholder={t("providers.form_field_weight_placeholder")}
                                            className="text-sm"
                                        />
                                    </div>
                                )}
                            />

                            <SafeFormField
                                control={form.control}
                                name="maxQps"
                                render={({ field }: { field: any }) => (
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium">{t("providers.form_field_max_qps")}</label>
                                        <Input
                                            {...field}
                                            type="number"
                                            placeholder={t("providers.form_field_max_qps_placeholder")}
                                            className="text-sm"
                                        />
                                    </div>
                                )}
                            />

                            <SafeFormField
                                control={form.control}
                                name="region"
                                render={({ field }: { field: any }) => (
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium">{t("providers.form_field_region")}</label>
                                        <Input
                                            {...field}
                                            placeholder={t("providers.form_field_region_placeholder")}
                                            className="text-sm"
                                        />
                                    </div>
                                )}
                            />
                        </div>
                    </div>

                    {/* 成本配置 */}
                    <div className="space-y-3">
                        <h4 className="text-sm font-medium">{t("providers.form_section_cost")}</h4>
                        <div className="grid grid-cols-2 gap-4">
                            <SafeFormField
                                control={form.control}
                                name="costInput"
                                render={({ field }: { field: any }) => (
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium">{t("providers.form_field_cost_input")}</label>
                                        <Input
                                            {...field}
                                            type="number"
                                            step="0.01"
                                            placeholder={t("providers.form_field_cost_input_placeholder")}
                                            className="text-sm"
                                        />
                                    </div>
                                )}
                            />

                            <SafeFormField
                                control={form.control}
                                name="costOutput"
                                render={({ field }: { field: any }) => (
                                    <div className="space-y-2">
                                        <label className="text-xs font-medium">{t("providers.form_field_cost_output")}</label>
                                        <Input
                                            {...field}
                                            type="number"
                                            step="0.01"
                                            placeholder={t("providers.form_field_cost_output_placeholder")}
                                            className="text-sm"
                                        />
                                    </div>
                                )}
                            />
                        </div>
                    </div>

                    {/* API 样式配置 */}
                    <ApiStylesConfig
                        form={form}
                        isFieldOverridden={isFieldOverridden}
                        markFieldAsOverridden={markFieldAsOverridden}
                    />

                    {/* 可重试状态码 */}
                    <SafeFormField
                        control={form.control}
                        name="retryableStatusCodes"
                        render={({ field }: { field: any }) => (
                            <NumberArrayEditor
                                label={t("providers.form_field_retryable_status_codes")}
                                value={field.value || []}
                                onChange={(value) => {
                                    field.onChange(value);
                                    markFieldAsOverridden("retryableStatusCodes");
                                }}
                                placeholder={t("providers.form_field_retryable_status_codes_placeholder")}
                                description={t("providers.form_field_retryable_status_codes_help")}
                                min={100}
                                max={599}
                            />
                        )}
                    />

                    {/* 自定义请求头 */}
                    <SafeFormField
                        control={form.control}
                        name="customHeaders"
                        render={({ field }: { field: any }) => (
                            <JsonEditor
                                label={t("providers.form_field_custom_headers")}
                                value={field.value}
                                onChange={(value) => {
                                    field.onChange(value);
                                    markFieldAsOverridden("customHeaders");
                                }}
                                placeholder={t("providers.form_field_custom_headers_placeholder")}
                                description={t("providers.form_field_custom_headers_help")}
                                rows={4}
                            />
                        )}
                    />

                    {/* 静态模型列表 */}
                    <SafeFormField
                        control={form.control}
                        name="staticModels"
                        render={({ field }: { field: any }) => (
                            <div className="space-y-2">
                                <JsonEditor
                                    label={t("providers.form_field_static_models")}
                                    value={field.value}
                                    onChange={(value) => {
                                        field.onChange(value);
                                        markFieldAsOverridden("staticModels");
                                    }}
                                    placeholder={t("providers.form_field_static_models_placeholder")}
                                    description={t("providers.form_field_static_models_help")}
                                    rows={6}
                                />
                                <div className="rounded-md bg-muted/50 p-3 text-xs space-y-2">
                                    <div className="font-medium">{t("providers.form_field_static_models_schema_title")}</div>
                                    <ul className="space-y-1 list-disc list-inside text-muted-foreground">
                                        <li><code className="bg-background px-1 rounded">id</code>{t("providers.form_field_static_models_schema_id")}</li>
                                        <li><code className="bg-background px-1 rounded">display_name</code>{t("providers.form_field_static_models_schema_display_name")}</li>
                                        <li><code className="bg-background px-1 rounded">context_length</code>{t("providers.form_field_static_models_schema_context_length")}</li>
                                        <li><code className="bg-background px-1 rounded">family</code>{t("providers.form_field_static_models_schema_family")}</li>
                                        <li><code className="bg-background px-1 rounded">capabilities</code>{t("providers.form_field_static_models_schema_capabilities")}</li>
                                        <li><code className="bg-background px-1 rounded">pricing</code>{t("providers.form_field_static_models_schema_pricing")}{`{"input": 0.03, "output": 0.06}`}</li>
                                    </ul>
                                    <div className="pt-1 border-t border-border/50">
                                        <span className="font-medium">{t("providers.form_field_static_models_schema_example")}</span>
                                        <pre className="mt-1 bg-background p-2 rounded text-[10px] overflow-x-auto">{`[
  {
    "id": "gpt-4",
    "display_name": "GPT-4",
    "family": "gpt-4",
    "context_length": 8192,
    "capabilities": ["chat"],
    "pricing": {"input": 0.03, "output": 0.06}
  },
  {
    "id": "claude-3-opus-20240229",
    "display_name": "Claude 3 Opus",
    "context_length": 200000,
    "capabilities": ["image_generation"]
  }
]`}</pre>
                                    </div>
                                </div>
                            </div>
                        )}
                    />
                </div>
            )}
        </div>
    );
}
