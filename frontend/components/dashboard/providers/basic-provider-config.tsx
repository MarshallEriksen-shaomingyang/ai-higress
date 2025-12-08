"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { FormField, FormLabel } from "@/components/ui/form";

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
    return (
        <div className="space-y-4">
            <h3 className="text-sm font-semibold">基础配置</h3>

            <SafeFormField
                control={form.control}
                name="name"
                render={({ field }: { field: any }) => (
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <FormLabel>
                                Provider 名称 <span className="text-destructive">*</span>
                            </FormLabel>
                            {isFieldOverridden("name") && (
                                <Badge variant="outline" className="text-xs">
                                    已覆盖
                                </Badge>
                            )}
                        </div>
                        <Input
                            {...field}
                            placeholder="例如：OpenAI Production"
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
                                Provider 类型 <span className="text-destructive">*</span>
                            </FormLabel>
                            <Tabs
                                value={field.value}
                                onValueChange={(value) => {
                                    field.onChange(value);
                                    markFieldAsOverridden("providerType");
                                }}
                            >
                                <TabsList className="grid w-full grid-cols-2">
                                    <TabsTrigger value="native">原生</TabsTrigger>
                                    <TabsTrigger value="aggregator">聚合</TabsTrigger>
                                </TabsList>
                            </Tabs>
                            <p className="text-xs text-muted-foreground">
                                直连厂商选择原生，通过聚合平台选择聚合
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
                                传输方式 <span className="text-destructive">*</span>
                            </FormLabel>
                            <Tabs
                                value={field.value}
                                onValueChange={(value) => {
                                    field.onChange(value);
                                    markFieldAsOverridden("transport");
                                }}
                            >
                                <TabsList className="grid w-full grid-cols-2">
                                    <TabsTrigger value="http">HTTP</TabsTrigger>
                                    <TabsTrigger value="sdk">SDK</TabsTrigger>
                                </TabsList>
                            </Tabs>
                            <p className="text-xs text-muted-foreground">
                                HTTP 需要配置 URL，SDK 需要选择对应官方 SDK 并通常也需要配置 Base URL
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
                                SDK 类型 <span className="text-destructive">*</span>
                            </FormLabel>
                            {sdkVendorsLoading ? (
                                <p className="text-xs text-muted-foreground">正在加载 SDK 列表...</p>
                            ) : sdkVendorOptions.length === 0 ? (
                                <p className="text-xs text-muted-foreground">
                                    暂无可用的 SDK 类型，请稍后重试或联系管理员注册。
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
                                        选择与上游 API 兼容的官方 SDK 类型，例如 Kimi 这类 OpenAI 兼容服务选择 OpenAI。
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
                                Base URL <span className="text-destructive">*</span>
                            </FormLabel>
                            {isFieldOverridden("baseUrl") && (
                                <Badge variant="outline" className="text-xs">
                                    已覆盖
                                </Badge>
                            )}
                        </div>
                        <Input
                            {...field}
                            placeholder="https://api.openai.com/v1 或自建网关地址"
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
                            API Key <span className="text-destructive">*</span>
                        </FormLabel>
                        <Input
                            {...field}
                            type="password"
                            placeholder="sk-..."
                        />
                        <p className="text-xs text-muted-foreground">
                            上游厂商的 API 密钥，将以加密形式存储
                        </p>
                    </div>
                )}
            />
        </div>
    );
}
