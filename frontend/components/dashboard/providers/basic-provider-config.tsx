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
}

export function BasicProviderConfig({
    form,
    isFieldOverridden,
    markFieldAsOverridden,
    isSdkTransport
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
                            <FormLabel required>Provider 名称</FormLabel>
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
                            <FormLabel required>Provider 类型</FormLabel>
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
                            <FormLabel required>传输方式</FormLabel>
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
                            <FormLabel required>SDK 类型</FormLabel>
                            <div className="flex gap-2">
                                <Button
                                    type="button"
                                    variant={field.value === "openai" ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => {
                                        field.onChange("openai");
                                        markFieldAsOverridden("sdkVendor");
                                    }}
                                >
                                    OpenAI
                                </Button>
                                <Button
                                    type="button"
                                    variant={field.value === "google" ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => {
                                        field.onChange("google");
                                        markFieldAsOverridden("sdkVendor");
                                    }}
                                >
                                    Google / Gemini
                                </Button>
                                <Button
                                    type="button"
                                    variant={field.value === "claude" ? "default" : "outline"}
                                    size="sm"
                                    onClick={() => {
                                        field.onChange("claude");
                                        markFieldAsOverridden("sdkVendor");
                                    }}
                                >
                                    Claude / Anthropic
                                </Button>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                选择与上游 API 兼容的官方 SDK 类型，例如 Kimi 这类 OpenAI 兼容服务选择 OpenAI。
                            </p>
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
                            <FormLabel required>Base URL</FormLabel>
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
                        <FormLabel>API Key（可选）</FormLabel>
                        <Input
                            {...field}
                            type="password"
                            placeholder="sk-..."
                        />
                        <p className="text-xs text-muted-foreground">
                            创建后也可以在 Provider 详情页单独管理密钥
                        </p>
                    </div>
                )}
            />
        </div>
    );
}
