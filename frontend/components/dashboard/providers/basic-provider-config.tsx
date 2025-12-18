"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { FormField, FormLabel } from "@/components/ui/form";
import { useI18n } from "@/lib/i18n-context";

// 类型安全的FormField包装器
const SafeFormField = FormField as any;

interface BasicProviderConfigProps {
    form: any;
    isFieldOverridden: (fieldName: string) => boolean;
    markFieldAsOverridden: (fieldName: string) => void;
    isSdkTransport: boolean;
    sdkVendorOptions: string[];
    sdkVendorsLoading?: boolean;
}

export function BasicProviderConfig({
    form,
    isFieldOverridden,
    markFieldAsOverridden,
    isSdkTransport,
    sdkVendorOptions,
    sdkVendorsLoading,
}: BasicProviderConfigProps) {
    const { t } = useI18n();
    const sdkVendor = form.watch("sdkVendor");
    const isVertexAiSdk = isSdkTransport && sdkVendor === "vertexai";
    
    return (
        <div className="space-y-4">
            <h3 className="text-sm font-semibold">{t("providers.form_section_basic")}</h3>

            <SafeFormField
                control={form.control}
                name="name"
                render={({ field }: { field: any }) => (
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <FormLabel>
                                {t("providers.form_field_name")} <span className="text-destructive">*</span>
                            </FormLabel>
                            {isFieldOverridden("name") && (
                                <Badge variant="outline" className="text-xs">
                                    {t("providers.form_field_overridden")}
                                </Badge>
                            )}
                        </div>
                        <Input
                            {...field}
                            placeholder={t("providers.form_field_name_placeholder")}
                            onChange={(e) => {
                                field.onChange(e);
                                markFieldAsOverridden("name");
                            }}
                        />
                    </div>
                )}
            />

            <div className="grid grid-cols-2 gap-4">
                <SafeFormField
                    control={form.control}
                    name="providerType"
                    render={({ field }: { field: any }) => (
                        <div className="space-y-2">
                            <FormLabel>
                                {t("providers.form_field_provider_type")} <span className="text-destructive">*</span>
                            </FormLabel>
                            <Tabs
                                value={field.value}
                                onValueChange={(value) => {
                                    field.onChange(value);
                                    markFieldAsOverridden("providerType");
                                }}
                            >
                                <TabsList className="grid w-full grid-cols-2">
                                    <TabsTrigger value="native">{t("providers.form_field_provider_type_native")}</TabsTrigger>
                                    <TabsTrigger value="aggregator">{t("providers.form_field_provider_type_aggregator")}</TabsTrigger>
                                </TabsList>
                            </Tabs>
                            <p className="text-xs text-muted-foreground">
                                {t("providers.form_field_provider_type_help")}
                            </p>
                        </div>
                    )}
                />

                <SafeFormField
                    control={form.control}
                    name="transport"
                    render={({ field }: { field: any }) => (
                        <div className="space-y-2">
                            <FormLabel>
                                {t("providers.form_field_transport")} <span className="text-destructive">*</span>
                            </FormLabel>
                            <Tabs
                                value={field.value}
                                onValueChange={(value) => {
                                    field.onChange(value);
                                    markFieldAsOverridden("transport");
                                }}
                            >
                                <TabsList className="grid w-full grid-cols-3">
                                    <TabsTrigger value="http">{t("providers.form_field_transport_http")}</TabsTrigger>
                                    <TabsTrigger value="sdk">{t("providers.form_field_transport_sdk")}</TabsTrigger>
                                    <TabsTrigger value="claude_cli">{t("providers.form_field_transport_claude_cli")}</TabsTrigger>
                                </TabsList>
                            </Tabs>
                            <p className="text-xs text-muted-foreground">
                                {t("providers.form_field_transport_help")}
                            </p>
                        </div>
                    )}
                />
            </div>

            {/* SDK 类型（仅在 SDK 模式下显示） */}
            {isSdkTransport && (
                <SafeFormField
                    control={form.control}
                    name="sdkVendor"
                    render={({ field }: { field: any }) => (
                        <div className="space-y-2">
                            <FormLabel>
                                {t("providers.form_field_sdk_vendor")} <span className="text-destructive">*</span>
                            </FormLabel>
                            {sdkVendorsLoading ? (
                                <p className="text-xs text-muted-foreground">{t("providers.form_field_sdk_vendor_loading")}</p>
                            ) : sdkVendorOptions.length === 0 ? (
                                <p className="text-xs text-muted-foreground">
                                    {t("providers.form_field_sdk_vendor_empty")}
                                </p>
                            ) : (
                                <>
                                    <div className="flex flex-wrap gap-2">
                                        {sdkVendorOptions.map((vendor) => (
                                            <Button
                                                key={vendor}
                                                type="button"
                                                variant={field.value === vendor ? "default" : "outline"}
                                                size="sm"
                                                className="capitalize"
                                                onClick={() => {
                                                    field.onChange(vendor);
                                                    markFieldAsOverridden("sdkVendor");
                                                }}
                                            >
                                                {vendor}
                                            </Button>
                                        ))}
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        {t("providers.form_field_sdk_vendor_help")}
                                    </p>
                                </>
                            )}
                        </div>
                    )}
                />
            )}

            <SafeFormField
                control={form.control}
                name="baseUrl"
                render={({ field }: { field: any }) => (
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <FormLabel>
                                {t("providers.form_field_base_url")} <span className="text-destructive">*</span>
                            </FormLabel>
                            {isFieldOverridden("baseUrl") && (
                                <Badge variant="outline" className="text-xs">
                                    {t("providers.form_field_overridden")}
                                </Badge>
                            )}
                        </div>
                        <Input
                            {...field}
                            placeholder={t("providers.form_field_base_url_placeholder")}
                            onChange={(e) => {
                                field.onChange(e);
                                markFieldAsOverridden("baseUrl");
                            }}
                        />
                    </div>
                )}
            />

            <SafeFormField
                control={form.control}
                name="apiKey"
                render={({ field }: { field: any }) => (
                    <div className="space-y-2">
                        <FormLabel>
                            {t("providers.form_field_api_key")} <span className="text-destructive">*</span>
                        </FormLabel>
                        {isVertexAiSdk ? (
                            <Textarea
                                {...field}
                                placeholder={t("providers.form_field_api_key_placeholder_vertexai")}
                                className="min-h-[120px] font-mono"
                            />
                        ) : (
                            <Input
                                {...field}
                                type="password"
                                placeholder={t("providers.form_field_api_key_placeholder")}
                            />
                        )}
                        <p className="text-xs text-muted-foreground">
                            {isVertexAiSdk
                                ? t("providers.form_field_api_key_help_vertexai")
                                : t("providers.form_field_api_key_help")}
                        </p>
                    </div>
                )}
            />
        </div>
    );
}
