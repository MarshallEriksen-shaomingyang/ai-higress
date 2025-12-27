"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Copy, Check, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

interface TokenDisplayDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    token: string;
    keyName: string;
}

export function TokenDisplayDialog({
    open,
    onOpenChange,
    token,
    keyName,
}: TokenDisplayDialogProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(token);
            setCopied(true);
            toast.success("Token 已复制到剪贴板");
            setTimeout(() => setCopied(false), 2000);
        } catch (error) {
            toast.error("复制失败，请手动复制");
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5 text-amber-500" />
                        API Key 创建成功
                    </DialogTitle>
                    <DialogDescription>
                        请立即保存您的 API Key，它只会显示一次！
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">密钥名称</label>
                        <div className="p-3 bg-muted rounded-md">
                            <p className="text-sm font-mono">{keyName}</p>
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium">完整 Token</label>
                        <div className="relative">
                            <div className="p-3 bg-muted rounded-md pr-12 break-all">
                                <p className="text-sm font-mono">{token}</p>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="absolute right-2 top-2"
                                onClick={handleCopy}
                            >
                                {copied ? (
                                    <Check className="w-4 h-4 text-green-500" />
                                ) : (
                                    <Copy className="w-4 h-4" />
                                )}
                            </Button>
                        </div>
                    </div>

                    <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-md p-4">
                        <div className="flex gap-3">
                            <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
                                    重要提示
                                </p>
                                <ul className="text-sm text-amber-800 dark:text-amber-200 space-y-1 list-disc list-inside">
                                    <li>此 Token 仅显示一次，关闭后将无法再次查看</li>
                                    <li>请将 Token 保存在安全的地方</li>
                                    <li>不要在公开场合分享您的 Token</li>
                                    <li>如果 Token 泄露，请立即删除并创建新的</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={handleCopy}>
                        <Copy className="w-4 h-4 mr-2" />
                        复制 Token
                    </Button>
                    <Button onClick={() => onOpenChange(false)}>
                        我已保存，关闭
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
