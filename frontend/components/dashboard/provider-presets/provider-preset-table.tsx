"use client";


import { ProviderPreset } from "@/http/provider-preset";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Edit, Trash2, ExternalLink } from "lucide-react";
import { formatRelativeTime } from "@/lib/date-utils";
import { useI18n } from "@/lib/i18n-context";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ProviderPresetTableProps {
  presets: ProviderPreset[];
  isLoading: boolean;
  onEdit: (preset: ProviderPreset) => void;
  onDelete: (presetId: string) => void;
}

export function ProviderPresetTable({
  presets,
  isLoading,
  onEdit,
  onDelete,
}: ProviderPresetTableProps) {
  const { t, language } = useI18n();

  if (isLoading) {
    return (
      <div className="rounded-md border">
        <div className="p-8 text-center text-muted-foreground">
          加载中...
        </div>
      </div>
    );
  }

  if (presets.length === 0) {
    return (
      <div className="rounded-md border">
        <div className="p-12 text-center">
          <p className="text-lg font-medium text-muted-foreground mb-2">
            暂无提供商预设
          </p>
          <p className="text-sm text-muted-foreground">
            点击"创建预设"按钮添加第一个提供商预设
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/50">
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              预设ID
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              显示名称
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              基础URL
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              提供商类型
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              传输方式
            </TableHead>
            <TableHead className="px-4 py-3 text-left text-sm font-medium">
              创建时间
            </TableHead>
            <TableHead className="px-4 py-3 text-right text-sm font-medium">
              操作
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {presets.map((preset) => (
            <TableRow key={preset.id}>
              <TableCell className="px-4 py-3 text-sm font-mono">
                {preset.preset_id}
              </TableCell>
              <TableCell className="px-4 py-3 text-sm font-medium">
                {preset.display_name}
              </TableCell>
              <TableCell className="px-4 py-3 text-sm">
                <div className="flex items-center gap-2 max-w-xs">
                  <span className="truncate" title={preset.base_url}>
                    {preset.base_url}
                  </span>
                  <a
                    href={preset.base_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </TableCell>
              <TableCell className="px-4 py-3 text-sm">
                <Badge
                  variant={
                    preset.provider_type === "native"
                      ? "default"
                      : "secondary"
                  }
                >
                  {preset.provider_type === "native" ? "原生" : "聚合"}
                </Badge>
              </TableCell>
              <TableCell className="px-4 py-3 text-sm">
                <Badge
                  variant={
                    preset.transport === "http" ? "outline" : "secondary"
                  }
                >
                  {preset.transport.toUpperCase()}
                </Badge>
              </TableCell>
              <TableCell className="px-4 py-3 text-sm text-muted-foreground">
                {formatRelativeTime(preset.created_at, language)}
              </TableCell>
              <TableCell className="px-4 py-3 text-sm">
                <div className="flex items-center justify-end gap-2">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onEdit(preset)}
                        className="h-8 w-8 p-0"
                      >
                        <Edit className="w-4 h-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {t("provider_presets.action_edit")}
                    </TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDelete(preset.preset_id)}
                        className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {t("provider_presets.action_delete")}
                    </TooltipContent>
                  </Tooltip>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
