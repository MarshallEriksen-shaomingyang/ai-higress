"use client";

import React, { useState, useEffect } from "react";
import {
  ProviderPreset,
  CreateProviderPresetRequest,
  UpdateProviderPresetRequest,
  providerPresetService,
  SdkVendor,
} from "@/http/provider-preset";
import { useSdkVendors } from "@/lib/swr";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";

interface ProviderPresetFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  preset?: ProviderPreset;
  onSuccess: () => void;
}

export function ProviderPresetForm({
  open,
  onOpenChange,
  preset,
  onSuccess,
}: ProviderPresetFormProps) {
  const isEdit = !!preset;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { data: sdkVendorsData, loading: sdkVendorsLoading } = useSdkVendors();
  const sdkVendorOptions = sdkVendorsData?.vendors || [];

  // 基础配置
  const [presetId, setPresetId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [providerType, setProviderType] = useState<"native" | "aggregator">("native");
  const [transport, setTransport] = useState<"http" | "sdk">("http");
  const [sdkVendor, setSdkVendor] = useState<SdkVendor | "" >("");

  // 高级配置
  const [modelsPath, setModelsPath] = useState("/v1/models");
  const [messagesPath, setMessagesPath] = useState("");
  const [chatCompletionsPath, setChatCompletionsPath] = useState("/v1/chat/completions");
  const [responsesPath, setResponsesPath] = useState("");
  const [imagesGenerationsPath, setImagesGenerationsPath] = useState("");
  const [apiStyles, setApiStyles] = useState<string[]>([]);
  const [retryableCodesText, setRetryableCodesText] = useState("");
  const [customHeadersText, setCustomHeadersText] = useState("{}");
  const [staticModelsText, setStaticModelsText] = useState("[]");

  // 错误状态
  const [errors, setErrors] = useState<Record<string, string>>({});

  // 初始化表单
  useEffect(() => {
    if (open) {
      if (preset) {
        // 编辑模式：填充现有数据
        setPresetId(preset.preset_id);
        setDisplayName(preset.display_name);
        setDescription(preset.description || "");
        setBaseUrl(preset.base_url);
        setProviderType(preset.provider_type);
        setTransport(preset.transport);
        setSdkVendor(preset.sdk_vendor ?? "");
        setModelsPath(preset.models_path);
        setMessagesPath(preset.messages_path || "");
        setChatCompletionsPath(preset.chat_completions_path);
        setResponsesPath(preset.responses_path || "");
        setImagesGenerationsPath(preset.images_generations_path || "");
        setApiStyles(preset.supported_api_styles || []);
        setRetryableCodesText(
          preset.retryable_status_codes?.join(", ") || ""
        );
        setCustomHeadersText(
          JSON.stringify(preset.custom_headers || {}, null, 2)
        );
        setStaticModelsText(
          JSON.stringify(preset.static_models || [], null, 2)
        );
      } else {
        // 创建模式：重置表单
        resetForm();
      }
      setErrors({});
    }
  }, [open, preset]);

  const resetForm = () => {
    setPresetId("");
    setDisplayName("");
    setDescription("");
        setBaseUrl("");
        setProviderType("native");
        setTransport("http");
        setSdkVendor("");
    setModelsPath("/v1/models");
    setMessagesPath("");
    setChatCompletionsPath("/v1/chat/completions");
    setResponsesPath("");
    setImagesGenerationsPath("");
    setApiStyles([]);
    setRetryableCodesText("");
    setCustomHeadersText("{}");
    setStaticModelsText("[]");
  };

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    // 基础验证
    if (!presetId.trim()) {
      newErrors.presetId = "预设ID不能为空";
    } else if (!/^[a-zA-Z0-9_-]+$/.test(presetId)) {
      newErrors.presetId = "预设ID只能包含字母、数字、下划线和连字符";
    }

    if (!displayName.trim()) {
      newErrors.displayName = "显示名称不能为空";
    }

    if (!baseUrl.trim()) {
      newErrors.baseUrl = "基础URL不能为空";
    } else if (!/^https?:\/\/.+/.test(baseUrl)) {
      newErrors.baseUrl = "请输入有效的HTTP/HTTPS URL";
    }

    // SDK 配置校验
    if (transport === "sdk") {
      if (!sdkVendor) {
        newErrors.sdkVendor = "当传输方式为 SDK 时必须选择 SDK 类型";
      } else if (
        sdkVendorOptions.length > 0 &&
        !sdkVendorOptions.includes(sdkVendor)
      ) {
        newErrors.sdkVendor = "SDK 类型不在支持列表中";
      }
    }

    // 路径验证
    const paths = [
      { value: modelsPath, name: "modelsPath", label: "模型路径" },
      { value: messagesPath, name: "messagesPath", label: "消息路径" },
      { value: chatCompletionsPath, name: "chatCompletionsPath", label: "聊天完成路径" },
      { value: responsesPath, name: "responsesPath", label: "响应路径" },
      { value: imagesGenerationsPath, name: "imagesGenerationsPath", label: "文生图路径" },
    ];

    paths.forEach(({ value, name, label }) => {
      if (value && !value.startsWith("/")) {
        newErrors[name] = `${label}必须以 / 开头`;
      }
    });

    // 至少需要一个有效的 API 路径（Messages Path、Chat Completions Path 或 Responses Path）
    const hasMessagesPath = messagesPath?.trim();
    const hasChatCompletionsPath = chatCompletionsPath?.trim();
    const hasResponsesPath = responsesPath?.trim();
    
    if (!hasMessagesPath && !hasChatCompletionsPath && !hasResponsesPath) {
      newErrors.messagesPath = "消息路径、聊天完成路径、响应路径至少需要填写一个";
      newErrors.chatCompletionsPath = "消息路径、聊天完成路径、响应路径至少需要填写一个";
      newErrors.responsesPath = "消息路径、聊天完成路径、响应路径至少需要填写一个";
    }

    // JSON验证
    if (customHeadersText.trim()) {
      try {
        JSON.parse(customHeadersText);
      } catch {
        newErrors.customHeaders = "自定义请求头必须是有效的JSON对象";
      }
    }

    if (staticModelsText.trim()) {
      try {
        JSON.parse(staticModelsText);
      } catch {
        newErrors.staticModels = "静态模型列表必须是有效的JSON数组";
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      toast.error("请检查表单错误");
      return;
    }

    setIsSubmitting(true);

    try {
      // 解析可重试状态码
      const retryableCodes = retryableCodesText
        .split(",")
        .map((s) => parseInt(s.trim()))
        .filter((n) => !isNaN(n));

      // 解析JSON字段
      const customHeaders = customHeadersText.trim()
        ? JSON.parse(customHeadersText)
        : undefined;
      const staticModels = staticModelsText.trim()
        ? JSON.parse(staticModelsText)
        : undefined;

      if (isEdit) {
        // 更新预设
        const updateData: UpdateProviderPresetRequest = {
          display_name: displayName,
          description: description || undefined,
          provider_type: providerType,
          transport,
          sdk_vendor: transport === "sdk" ? (sdkVendor as SdkVendor) : undefined,
          base_url: baseUrl,
          models_path: modelsPath,
          messages_path: messagesPath || undefined,
          chat_completions_path: chatCompletionsPath,
          responses_path: responsesPath || undefined,
          images_generations_path: imagesGenerationsPath || undefined,
          supported_api_styles: apiStyles.length > 0 ? apiStyles as any : undefined,
          retryable_status_codes: retryableCodes.length > 0 ? retryableCodes : undefined,
          custom_headers: customHeaders,
          static_models: staticModels,
        };

        await providerPresetService.updateProviderPreset(presetId, updateData);
        toast.success("预设更新成功");
      } else {
        // 创建预设
        const createData: CreateProviderPresetRequest = {
          preset_id: presetId,
          display_name: displayName,
          description: description || undefined,
          provider_type: providerType,
          transport,
          sdk_vendor: transport === "sdk" ? (sdkVendor as SdkVendor) : undefined,
          base_url: baseUrl,
          models_path: modelsPath,
          messages_path: messagesPath || undefined,
          chat_completions_path: chatCompletionsPath,
          responses_path: responsesPath || undefined,
          images_generations_path: imagesGenerationsPath || undefined,
          supported_api_styles: apiStyles.length > 0 ? apiStyles as any : undefined,
          retryable_status_codes: retryableCodes.length > 0 ? retryableCodes : undefined,
          custom_headers: customHeaders,
          static_models: staticModels,
        };

        await providerPresetService.createProviderPreset(createData);
        toast.success("预设创建成功");
      }

      onSuccess();
      onOpenChange(false);
    } catch (error: any) {
      console.error("提交失败:", error);
      const message = error.response?.data?.detail || error.message || "操作失败";
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleApiStyle = (style: string) => {
    setApiStyles((prev) =>
      prev.includes(style)
        ? prev.filter((s) => s !== style)
        : [...prev, style]
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "编辑提供商预设" : "创建提供商预设"}
          </DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          <Tabs defaultValue="basic" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="basic">基础配置</TabsTrigger>
              <TabsTrigger value="advanced">高级配置</TabsTrigger>
            </TabsList>

            <TabsContent value="basic" className="space-y-4 mt-4">
              {/* 预设ID */}
              <div className="space-y-2">
                <Label htmlFor="presetId">
                  预设ID <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="presetId"
                  value={presetId}
                  onChange={(e) => setPresetId(e.target.value)}
                  disabled={isEdit}
                  placeholder="例如: openai, claude, gemini"
                  className={errors.presetId ? "border-destructive" : ""}
                />
                {errors.presetId && (
                  <p className="text-sm text-destructive">{errors.presetId}</p>
                )}
              </div>

              {/* 显示名称 */}
              <div className="space-y-2">
                <Label htmlFor="displayName">
                  显示名称 <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="displayName"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="例如: OpenAI, Claude, Gemini"
                  className={errors.displayName ? "border-destructive" : ""}
                />
                {errors.displayName && (
                  <p className="text-sm text-destructive">{errors.displayName}</p>
                )}
              </div>

              {/* 描述 */}
              <div className="space-y-2">
                <Label htmlFor="description">描述</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="简要描述此提供商预设..."
                  rows={3}
                />
              </div>

              {/* 基础URL */}
              <div className="space-y-2">
                <Label htmlFor="baseUrl">
                  基础URL <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="baseUrl"
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="https://api.example.com"
                  className={errors.baseUrl ? "border-destructive" : ""}
                />
                {errors.baseUrl && (
                  <p className="text-sm text-destructive">{errors.baseUrl}</p>
                )}
              </div>

              {/* 提供商类型 */}
              <div className="space-y-2">
                <Label htmlFor="providerType">
                  提供商类型 <span className="text-destructive">*</span>
                </Label>
                <Select value={providerType} onValueChange={(v: any) => setProviderType(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="native">原生 (Native)</SelectItem>
                    <SelectItem value="aggregator">聚合 (Aggregator)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

            {/* 传输方式 */}
            <div className="space-y-2">
              <Label htmlFor="transport">
                传输方式 <span className="text-destructive">*</span>
              </Label>
              <Select value={transport} onValueChange={(v: any) => setTransport(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="http">HTTP</SelectItem>
                  <SelectItem value="sdk">SDK</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* SDK 类型（仅在 transport=sdk 时显示） */}
            {transport === "sdk" && (
              <div className="space-y-2">
                <Label htmlFor="sdkVendor">
                  SDK 类型 <span className="text-destructive">*</span>
                </Label>
                <Select
                  value={sdkVendor}
                  disabled={sdkVendorsLoading || sdkVendorOptions.length === 0}
                  onValueChange={(v: any) => setSdkVendor(v)}
                >
                  <SelectTrigger className={errors.sdkVendor ? "border-destructive" : ""}>
                    <SelectValue placeholder="选择 SDK 厂商" />
                  </SelectTrigger>
                  <SelectContent>
                    {sdkVendorOptions.map((vendor) => (
                      <SelectItem key={vendor} value={vendor} className="capitalize">
                        {vendor}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {sdkVendorsLoading && (
                  <p className="text-sm text-muted-foreground">正在加载 SDK 列表...</p>
                )}
                {!sdkVendorsLoading && sdkVendorOptions.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    暂无可用的 SDK 类型，请稍后重试或联系管理员注册。
                  </p>
                )}
                {errors.sdkVendor && (
                  <p className="text-sm text-destructive">{errors.sdkVendor}</p>
                )}
              </div>
            )}
            </TabsContent>

            <TabsContent value="advanced" className="space-y-4 mt-4">
              {/* 模型路径 */}
              <div className="space-y-2">
                <Label htmlFor="modelsPath">模型路径</Label>
                <Input
                  id="modelsPath"
                  value={modelsPath}
                  onChange={(e) => setModelsPath(e.target.value)}
                  placeholder="/v1/models"
                  className={errors.modelsPath ? "border-destructive" : ""}
                />
                {errors.modelsPath && (
                  <p className="text-sm text-destructive">{errors.modelsPath}</p>
                )}
              </div>

              {/* 消息路径 */}
              <div className="space-y-2">
                <Label htmlFor="messagesPath">消息路径</Label>
                <Input
                  id="messagesPath"
                  value={messagesPath}
                  onChange={(e) => setMessagesPath(e.target.value)}
                  placeholder="/v1/message"
                />
              </div>

              {/* 聊天完成路径 */}
              <div className="space-y-2">
                <Label htmlFor="chatCompletionsPath">聊天完成路径</Label>
                <Input
                  id="chatCompletionsPath"
                  value={chatCompletionsPath}
                  onChange={(e) => setChatCompletionsPath(e.target.value)}
                  placeholder="/v1/chat/completions"
                  className={errors.chatCompletionsPath ? "border-destructive" : ""}
                />
                {errors.chatCompletionsPath && (
                  <p className="text-sm text-destructive">{errors.chatCompletionsPath}</p>
                )}
              </div>

              {/* 响应路径 */}
              <div className="space-y-2">
                <Label htmlFor="responsesPath">响应路径</Label>
                <Input
                  id="responsesPath"
                  value={responsesPath}
                  onChange={(e) => setResponsesPath(e.target.value)}
                  placeholder="/v1/responses"
                />
              </div>

              {/* 文生图路径（可选） */}
              <div className="space-y-2">
                <Label htmlFor="imagesGenerationsPath">文生图路径（可选）</Label>
                <Input
                  id="imagesGenerationsPath"
                  value={imagesGenerationsPath}
                  onChange={(e) => setImagesGenerationsPath(e.target.value)}
                  placeholder="/v1/images/generations"
                  className={errors.imagesGenerationsPath ? "border-destructive" : ""}
                />
                {errors.imagesGenerationsPath && (
                  <p className="text-sm text-destructive">{errors.imagesGenerationsPath}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  上游 OpenAI Images API 路径覆盖；留空则由后端从聊天路径推导。
                </p>
              </div>

              {/* 支持的API风格 */}
              <div className="space-y-2">
                <Label>支持的API风格</Label>
                <div className="flex flex-wrap gap-4">
                  {["openai", "responses", "claude"].map((style) => (
                    <div key={style} className="flex items-center space-x-2">
                      <Checkbox
                        id={`style-${style}`}
                        checked={apiStyles.includes(style)}
                        onCheckedChange={() => toggleApiStyle(style)}
                      />
                      <Label htmlFor={`style-${style}`} className="font-normal cursor-pointer">
                        {style}
                      </Label>
                    </div>
                  ))}
                </div>
              </div>

              {/* 可重试状态码 */}
              <div className="space-y-2">
                <Label htmlFor="retryableCodes">可重试状态码</Label>
                <Input
                  id="retryableCodes"
                  value={retryableCodesText}
                  onChange={(e) => setRetryableCodesText(e.target.value)}
                  placeholder="429, 500, 502, 503, 504"
                />
                <p className="text-xs text-muted-foreground">
                  用逗号分隔的HTTP状态码
                </p>
              </div>

              {/* 自定义请求头 */}
              <div className="space-y-2">
                <Label htmlFor="customHeaders">自定义请求头 (JSON)</Label>
                <Textarea
                  id="customHeaders"
                  value={customHeadersText}
                  onChange={(e) => setCustomHeadersText(e.target.value)}
                  placeholder='{"X-Custom-Header": "value"}'
                  rows={4}
                  className={`font-mono text-sm ${errors.customHeaders ? "border-destructive" : ""}`}
                />
                {errors.customHeaders && (
                  <p className="text-sm text-destructive">{errors.customHeaders}</p>
                )}
              </div>

              {/* 静态模型列表 */}
              <div className="space-y-2">
                <Label htmlFor="staticModels">静态模型列表 (JSON)</Label>
                <Textarea
                  id="staticModels"
                  value={staticModelsText}
                  onChange={(e) => setStaticModelsText(e.target.value)}
                  placeholder='[{"id": "model-1", "name": "Model 1"}]'
                  rows={4}
                  className={`font-mono text-sm ${errors.staticModels ? "border-destructive" : ""}`}
                />
                {errors.staticModels && (
                  <p className="text-sm text-destructive">{errors.staticModels}</p>
                )}
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end gap-3 pt-4 border-t">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              取消
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "提交中..." : isEdit ? "更新" : "创建"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
