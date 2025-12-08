"use client";

import React, { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  CreateProviderPresetRequest,
  ProviderPreset,
  providerPresetService,
} from "@/http/provider-preset";
import { useProviderPresets } from "@/lib/hooks/use-provider-presets";
import { ProviderPresetTable } from "@/components/dashboard/provider-presets/provider-preset-table";
import { ProviderPresetForm } from "@/components/dashboard/provider-presets/provider-preset-form";
import { Download, Plus, Search, Upload } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export default function ProviderPresetsPage() {
  const [formOpen, setFormOpen] = useState(false);
  const [editingPreset, setEditingPreset] = useState<ProviderPreset | undefined>();
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingPresetId, setDeletingPresetId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [parsedPresets, setParsedPresets] = useState<CreateProviderPresetRequest[]>([]);
  const [importError, setImportError] = useState<string | null>(null);
  const [importFileName, setImportFileName] = useState("");
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const [fileInputKey, setFileInputKey] = useState(0);

  // 使用自定义 Hook + SWR 获取数据
  const {
    presets,
    loading: isLoading,
    error,
    refresh,
  } = useProviderPresets();

  // 本地搜索过滤
  const filteredPresets = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return presets;

    return presets.filter((preset) => {
      const displayName = preset.display_name?.toLowerCase() ?? "";
      const presetId = preset.preset_id?.toLowerCase() ?? "";
      const description = preset.description?.toLowerCase() ?? "";
      const baseUrl = preset.base_url?.toLowerCase() ?? "";

      return (
        displayName.includes(query) ||
        presetId.includes(query) ||
        description.includes(query) ||
        baseUrl.includes(query)
      );
    });
  }, [presets, searchQuery]);

  // 打开创建表单
  const handleCreate = () => {
    setEditingPreset(undefined);
    setFormOpen(true);
  };

  // 打开编辑表单
  const handleEdit = (preset: ProviderPreset) => {
    setEditingPreset(preset);
    setFormOpen(true);
  };

  // 打开删除确认
  const handleDeleteClick = (presetId: string) => {
    setDeletingPresetId(presetId);
    setDeleteConfirmOpen(true);
  };

  // 确认删除
  const handleDeleteConfirm = async () => {
    if (!deletingPresetId) return;

    setIsDeleting(true);
    try {
      await providerPresetService.deleteProviderPreset(deletingPresetId);
      toast.success("预设删除成功");
      await refresh(); // 刷新列表
    } catch (error: any) {
      console.error("删除失败:", error);
      const message = error.response?.data?.detail || error.message || "删除失败";
      toast.error(message);
    } finally {
      setIsDeleting(false);
      setDeleteConfirmOpen(false);
      setDeletingPresetId(null);
    }
  };

  const resetImportState = () => {
    setParsedPresets([]);
    setImportError(null);
    setImportFileName("");
    setOverwriteExisting(false);
    setFileInputKey((key) => key + 1);
  };

  const handleImportDialogChange = (open: boolean) => {
    if (!open) {
      resetImportState();
    }
    setImportDialogOpen(open);
  };

  const handleImportFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setImportFileName(file.name);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const presetsData = Array.isArray(parsed) ? parsed : parsed?.presets;

      if (!Array.isArray(presetsData)) {
        setImportError("JSON 文件格式不正确，请提供包含 presets 数组的内容");
        setParsedPresets([]);
        return;
      }

      if (presetsData.length === 0) {
        setImportError("文件中的 presets 数组为空");
        setParsedPresets([]);
        return;
      }

      setParsedPresets(presetsData as CreateProviderPresetRequest[]);
      setImportError(null);
    } catch (err) {
      console.error("导入文件解析失败:", err);
      setImportError("解析导入文件失败，请提供合法的 JSON 文件");
      setParsedPresets([]);
    }
  };

  const handleImportSubmit = async () => {
    if (parsedPresets.length === 0) {
      setImportError("请选择包含有效 presets 的 JSON 文件");
      return;
    }

    setImporting(true);
    try {
      const result = await providerPresetService.importProviderPresets({
        presets: parsedPresets,
        overwrite: overwriteExisting,
      });

      const summaryParts = [
        `新增 ${result.created.length} 个`,
        `更新 ${result.updated.length} 个`,
      ];
      if (result.skipped.length > 0) {
        summaryParts.push(`跳过 ${result.skipped.length} 个`);
      }

      toast.success(`导入完成（${summaryParts.join(" / ")}）`);
      if (result.failed.length > 0) {
        toast.error(`有 ${result.failed.length} 个预设导入失败，请检查文件内容`);
      }

      resetImportState();
      setImportDialogOpen(false);
      await refresh();
    } catch (error: any) {
      console.error("导入预设失败:", error);
      const message = error.response?.data?.detail || error.message || "导入失败";
      toast.error(message);
    } finally {
      setImporting(false);
    }
  };

  const handleExport = async () => {
    try {
      const data = await providerPresetService.exportProviderPresets();
      const payload = JSON.stringify({ presets: data.presets }, null, 2);
      const blob = new Blob([payload], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `provider-presets-${new Date()
        .toISOString()
        .replace(/[:T]/g, "-")
        .split(".")[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success(`已导出 ${data.total} 个预设`);
    } catch (error: any) {
      console.error("导出预设失败:", error);
      const message = error.response?.data?.detail || error.message || "导出失败";
      toast.error(message);
    }
  };

  // 表单提交成功
  const handleFormSuccess = () => {
    refresh(); // 刷新列表
  };

  if (error) {
    const errorMessage =
      (error as any)?.message || "加载失败";
    return (
      <div className="space-y-6 max-w-7xl">
        <div>
          <h1 className="text-3xl font-bold mb-2">提供商预设管理</h1>
          <p className="text-muted-foreground">管理官方提供商预设配置</p>
        </div>
        <div className="rounded-md border border-destructive p-8 text-center">
          <p className="text-destructive">加载失败: {errorMessage}</p>
          <Button onClick={() => refresh()} className="mt-4">
            重试
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl">
      {/* 页面标题、搜索框和创建按钮 */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold">提供商预设管理</h1>
          <p className="text-muted-foreground text-sm">
            管理官方提供商预设配置，用户可在创建私有提供商时选择使用
          </p>
        </div>
        <div className="flex flex-col gap-2 md:flex-row md:items-center">
          <div className="relative w-full md:w-64">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索预设（ID / 名称 / 描述 / Base URL）..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex flex-wrap gap-2 md:justify-end">
            <Button variant="outline" onClick={handleExport}>
              <Download className="w-4 h-4 mr-2" />
              导出
            </Button>
            <Button variant="secondary" onClick={() => setImportDialogOpen(true)}>
              <Upload className="w-4 h-4 mr-2" />
              导入
            </Button>
            <Button onClick={handleCreate} className="md:ml-2">
              <Plus className="w-4 h-4 mr-2" />
              创建预设
            </Button>
          </div>
        </div>
      </div>

      {/* 预设列表表格 */}
      <ProviderPresetTable
        presets={filteredPresets}
        isLoading={isLoading}
        onEdit={handleEdit}
        onDelete={handleDeleteClick}
      />

      {/* 创建/编辑表单对话框 */}
      <ProviderPresetForm
        open={formOpen}
        onOpenChange={setFormOpen}
        preset={editingPreset}
        onSuccess={handleFormSuccess}
      />

      {/* 导入预设对话框 */}
      <Dialog open={importDialogOpen} onOpenChange={handleImportDialogChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>导入提供商预设</DialogTitle>
            <DialogDescription>
              上传包含 presets 数组的 JSON 文件，可选择是否覆盖已存在的同名预设。
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="import-file">选择导入文件</Label>
              <Input
                key={fileInputKey}
                id="import-file"
                type="file"
                accept=".json,application/json"
                onChange={handleImportFileChange}
              />
              {importFileName && (
                <p className="text-sm text-muted-foreground">
                  已选择：{importFileName}
                </p>
              )}
              {importError && (
                <p className="text-sm text-destructive">{importError}</p>
              )}
            </div>

            <div className="flex items-start gap-3 rounded-md border p-3">
              <Checkbox
                id="overwrite-existing"
                checked={overwriteExisting}
                onCheckedChange={(checked) => setOverwriteExisting(Boolean(checked))}
              />
              <div className="space-y-1">
                <Label htmlFor="overwrite-existing" className="cursor-pointer">
                  覆盖已存在的同名预设
                </Label>
                <p className="text-xs text-muted-foreground">
                  关闭时，同名预设会被跳过；开启后将用导入文件覆盖已有配置。
                </p>
              </div>
            </div>

            {parsedPresets.length > 0 && (
              <div className="rounded-md border bg-muted/50 p-3 text-sm">
                <p>将导入 {parsedPresets.length} 个预设。</p>
                <p className="text-muted-foreground">
                  示例 ID：{" "}
                  {parsedPresets
                    .slice(0, 3)
                    .map((p) => p.preset_id)
                    .filter(Boolean)
                    .join(", ")}
                  {parsedPresets.length > 3 ? " ..." : ""}
                </p>
              </div>
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setImportDialogOpen(false);
                resetImportState();
              }}
              disabled={importing}
            >
              取消
            </Button>
            <Button
              onClick={handleImportSubmit}
              disabled={importing || parsedPresets.length === 0}
            >
              {importing ? "导入中..." : "开始导入"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认对话框 */}
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除预设 <span className="font-mono font-semibold">{deletingPresetId}</span> 吗？
              此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmOpen(false)}
              disabled={isDeleting}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? "删除中..." : "删除"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
