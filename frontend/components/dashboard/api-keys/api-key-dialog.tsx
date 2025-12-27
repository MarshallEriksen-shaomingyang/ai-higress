"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { useApiKeys } from "@/lib/swr/use-api-keys";
import { useErrorDisplay } from "@/lib/errors";
import type { ApiKey, CreateApiKeyRequest, UpdateApiKeyRequest } from "@/lib/api-types";
import { toast } from "sonner";

// 动态加载 Select 组件

const Select = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.Select })), { ssr: false });
const SelectContent = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectContent })), { ssr: false });
const SelectItem = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectItem })), { ssr: false });
const SelectTrigger = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectTrigger })), { ssr: false });
const SelectValue = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectValue })), { ssr: false });

const ProviderSelector = dynamic(() => import("./provider-selector").then(mod => ({ default: mod.ProviderSelector })), { ssr: false });

interface ApiKeyDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    mode: 'create' | 'edit';
    apiKey?: ApiKey;
    onSuccess?: (apiKey: ApiKey) => void;
}

const EXPIRY_OPTIONS = [
    { value: 'week', label: '1 周' },
    { value: 'month', label: '1 个月' },
    { value: 'year', label: '1 年' },
    { value: 'never', label: '永不过期' },
] as const;

export function ApiKeyDialog({
    open,
    onOpenChange,
    mode,
    apiKey,
    onSuccess,
}: ApiKeyDialogProps) {
    const { createApiKey, updateApiKey, creating, updating } = useApiKeys();
    const { showError } = useErrorDisplay();
    
    const [name, setName] = useState('');
    const [expiry, setExpiry] = useState<'week' | 'month' | 'year' | 'never'>('never');
    const [allowedProviderIds, setAllowedProviderIds] = useState<string[]>([]);
    const [errors, setErrors] = useState<{ name?: string }>({});

    useEffect(() => {
        if (open) {
            if (mode === 'edit' && apiKey) {
                setName(apiKey.name);
                setExpiry(apiKey.expiry_type);
                setAllowedProviderIds(apiKey.allowed_provider_ids || []);
            } else {
                setName('');
                setExpiry('never');
                setAllowedProviderIds([]);
            }
            setErrors({});
        }
    }, [open, mode, apiKey]);

    const validate = () => {
        const newErrors: { name?: string } = {};
        
        if (!name.trim()) {
            newErrors.name = '请输入密钥名称';
        } else if (name.trim().length > 255) {
            newErrors.name = '密钥名称不能超过 255 个字符';
        }
        
        setErrors(newErrors);
        return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        
        if (!validate()) {
            return;
        }

        try {
            if (mode === 'create') {
                const data: CreateApiKeyRequest = {
                    name: name.trim(),
                    expiry,
                    allowed_provider_ids: allowedProviderIds.length > 0 ? allowedProviderIds : undefined,
                };
                const result = await createApiKey(data);
                toast.success('API Key 创建成功');
                onSuccess?.(result);
            } else if (mode === 'edit' && apiKey) {
                const data: UpdateApiKeyRequest = {
                    name: name.trim(),
                    expiry,
                    allowed_provider_ids: allowedProviderIds,
                };
                await updateApiKey(apiKey.id, data);
                toast.success('API Key 更新成功');
                onOpenChange(false);
            }
        } catch (error) {
            showError(error, {
                context: mode === 'create' ? '创建 API Key' : '更新 API Key'
            });
        }
    };

    const isSubmitting = creating || updating;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>
                        {mode === 'create' ? '创建 API Key' : '编辑 API Key'}
                    </DialogTitle>
                    <DialogDescription>
                        {mode === 'create' 
                            ? '创建一个新的 API Key 用于访问 AI Higress API'
                            : '修改 API Key 的配置信息'
                        }
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit}>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">
                                密钥名称 <span className="text-destructive">*</span>
                            </label>
                            <Input
                                placeholder="例如：生产环境密钥"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                disabled={isSubmitting}
                                className={errors.name ? 'border-destructive' : ''}
                            />
                            {errors.name && (
                                <p className="text-sm text-destructive">{errors.name}</p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <label className="text-sm font-medium">过期时间</label>
                            <Select
                                value={expiry}
                                onValueChange={(value: any) => setExpiry(value)}
                                disabled={isSubmitting}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {EXPIRY_OPTIONS.map((option) => (
                                        <SelectItem key={option.value} value={option.value}>
                                            {option.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <p className="text-xs text-muted-foreground">
                                密钥过期后将无法使用，需要创建新的密钥
                            </p>
                        </div>

                        <ProviderSelector
                            value={allowedProviderIds}
                            onChange={setAllowedProviderIds}
                            disabled={isSubmitting}
                        />
                    </div>

                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={isSubmitting}
                        >
                            取消
                        </Button>
                        <Button type="submit" disabled={isSubmitting}>
                            {isSubmitting 
                                ? (mode === 'create' ? '创建中...' : '保存中...') 
                                : (mode === 'create' ? '创建密钥' : '保存更改')
                            }
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
