"use client";

import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ProviderPreset,
  providerPresetService,
} from "@/http/provider-preset";
import { useProviderPresets } from "@/lib/hooks/use-provider-presets";
import { ProviderPresetTable } from "@/components/dashboard/provider-presets/provider-preset-table";
import { Download, Plus, Search, Upload } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  VisuallyHidden,
} from "@/components/ui/dialog";
import dynamic from "next/dynamic";
import { useI18n } from "@/lib/i18n-context";

export function PresetsClient() {
  const { t } = useI18n();
  
  // 动态导入大型对话框组件
  const ProviderPresetForm = dynamic(
    () =>
      import("@/components/dashboard/provider-presets/provider-preset-form").then(
        (mod) => mod.ProviderPresetForm
      ),
    {
      loading: () => (
        <Dialog open={true}>
          <DialogContent>
            <DialogHeader>
              <VisuallyHidden>
                <DialogTitle>{t("provider_presets.loading")}</DialogTitle>
              </VisuallyHidden>
            </DialogHeader>
            <div className="p-8 text-center text-muted-foreground">{t("provider_presets.loading")}</div>
          </DialogContent>
        </Dialog>
      ),
    }
  );

  const ImportDialog = dynamic(
    () => import("./import-dialog").then((mod) => mod.ImportDialog),
    {
      loading: () => (
        <Dialog open={true}>
          <DialogContent>
            <DialogHeader>
              <VisuallyHidden>
                <DialogTitle>{t("provider_presets.loading")}</DialogTitle>
              </VisuallyHidden>
            </DialogHeader>
            <div className="p-8 text-center text-muted-foreground">{t("provider_presets.loading")}</div>
          </DialogContent>
        </Dialog>
      ),
    }
  );
  const [formOpen, setFormOpen] = useState(false);
  const [editingPreset, setEditingPreset] = useState<
    ProviderPreset | undefined
  >();
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingPresetId, setDeletingPresetId] = useState<string | null>(
    null
  );
  const [isDeleting, setIsDeleting] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [importDialogOpen, setImportDialogOpen] = useState(false);

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
      toast.success(t("provider_presets.delete_success"));
      await refresh(); // 刷新列表
    } catch (error: any) {
      console.error("删除失败:", error);
      const message =
        error.response?.data?.detail || error.message || t("provider_presets.delete_error");
      toast.error(message);
    } finally {
      setIsDeleting(false);
      setDeleteConfirmOpen(false);
      setDeletingPresetId(null);
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
      toast.success(t("provider_presets.export_success", { count: data.total }));
    } catch (error: any) {
      console.error("导出预设失败:", error);
      const message =
        error.response?.data?.detail || error.message || t("provider_presets.export_error");
      toast.error(message);
    }
  };

  // 表单提交成功
  const handleFormSuccess = () => {
    refresh(); // 刷新列表
  };

  // 导入成功
  const handleImportSuccess = () => {
    refresh(); // 刷新列表
  };

  if (error) {
    const errorMessage = (error as any)?.message || t("provider_presets.load_error");
    return (
      <div className="rounded-md border border-destructive p-8 text-center">
        <p className="text-destructive">{t("provider_presets.load_error")}: {errorMessage}</p>
        <Button onClick={() => refresh()} className="mt-4">
          {t("provider_presets.retry")}
        </Button>
      </div>
    );
  }

  return (
    <>
      {/* 搜索框和操作按钮 */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center">
        <div className="relative w-full md:w-64">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t("provider_presets.search_placeholder")}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2 md:justify-end">
          <Button variant="outline" onClick={handleExport}>
            <Download className="w-4 h-4 mr-2" />
            {t("provider_presets.export")}
          </Button>
          <Button
            variant="secondary"
            onClick={() => setImportDialogOpen(true)}
          >
            <Upload className="w-4 h-4 mr-2" />
            {t("provider_presets.import")}
          </Button>
          <Button onClick={handleCreate} className="md:ml-2">
            <Plus className="w-4 h-4 mr-2" />
            {t("provider_presets.create")}
          </Button>
        </div>
      </div>

      {/* 预设列表表格 */}
      <ProviderPresetTable
        presets={filteredPresets}
        isLoading={isLoading}
        onEdit={handleEdit}
        onDelete={handleDeleteClick}
      />

      {/* 创建/编辑表单对话框 - 动态导入 */}
      {formOpen && (
        <ProviderPresetForm
          open={formOpen}
          onOpenChange={setFormOpen}
          preset={editingPreset}
          onSuccess={handleFormSuccess}
        />
      )}

      {/* 导入预设对话框 - 动态导入 */}
      {importDialogOpen && (
        <ImportDialog
          open={importDialogOpen}
          onOpenChange={setImportDialogOpen}
          onSuccess={handleImportSuccess}
        />
      )}

      {/* 删除确认对话框 */}
      <Dialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("provider_presets.delete_confirm_title")}</DialogTitle>
            <DialogDescription>
              {t("provider_presets.delete_confirm_desc")}{" "}
              <span className="font-mono font-semibold">
                {deletingPresetId}
              </span>{" "}
              ? {t("provider_presets.delete_confirm_warning")}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteConfirmOpen(false)}
              disabled={isDeleting}
            >
              {t("provider_presets.delete_cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? t("provider_presets.deleting") : t("provider_presets.delete_confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
