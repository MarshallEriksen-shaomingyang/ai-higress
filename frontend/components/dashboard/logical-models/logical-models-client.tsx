"use client";

import React, { useState } from "react";
import { useI18n } from "@/lib/i18n-context";
import { useLogicalModels } from "@/lib/swr";
import type { LogicalModel } from "@/http/logical-model";
import { LogicalModelsTable } from "./logical-models-table";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Loader2, AlertCircle, RefreshCcw } from "lucide-react";

export function LogicalModelsClient() {
  const { t } = useI18n();
  const { models, loading, error, refresh } = useLogicalModels();
  const [selected, setSelected] = useState<LogicalModel | null>(null);
  const [open, setOpen] = useState(false);

  const handleSelect = (model: LogicalModel) => {
    setSelected(model);
    setOpen(true);
  };

  const formatTimestamp = (ts: number | null | undefined) => {
    if (!ts) return "-";
    return new Date(ts * 1000).toLocaleString();
  };

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            {t("logical_models.title")}
          </h1>
          <p className="text-muted-foreground mt-2">
            {t("logical_models.subtitle")}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refresh()}
          disabled={loading}
        >
          {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
          {!loading && <RefreshCcw className="w-4 h-4 mr-2" />}
          {t("common.refresh")}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            {t("logical_models.error_loading")}
          </AlertDescription>
        </Alert>
      )}

      {loading && !models.length && (
        <div className="flex items-center text-sm text-muted-foreground gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>{t("logical_models.loading")}</span>
        </div>
      )}

      <LogicalModelsTable models={models} onSelect={handleSelect} />

      <Dialog open={open && !!selected} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {t("logical_models.detail_title")} –{" "}
              {selected?.display_name || selected?.logical_id}
            </DialogTitle>
          </DialogHeader>

          {selected && (
            <div className="space-y-6">
              {/* 基础信息 */}
              <div className="space-y-2">
                <h3 className="text-sm font-medium">
                  {t("logical_models.detail_basic_info")}
                </h3>
                <div className="rounded-md border bg-muted/40 p-3 text-sm space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-muted-foreground">
                      {t("logical_models.column_logical_id")}:
                    </span>
                    <code className="text-xs">{selected.logical_id}</code>
                    <span className="mx-2 text-muted-foreground">·</span>
                    <span className="text-muted-foreground">
                      {t("logical_models.column_status")}:
                    </span>
                    <Badge
                      variant={selected.enabled ? "secondary" : "outline"}
                      className="text-xs"
                    >
                      {selected.enabled
                        ? t("logical_models.status_active")
                        : t("logical_models.status_inactive")}
                    </Badge>
                  </div>
                  <div className="text-muted-foreground">
                    {t("logical_models.detail_description")}:{" "}
                    <span className="text-foreground">
                      {selected.description || "-"}
                    </span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-muted-foreground">
                      {t("logical_models.detail_capabilities")}:
                    </span>
                    {selected.capabilities.length ? (
                      selected.capabilities.map((cap) => (
                        <Badge
                          key={cap}
                          variant="outline"
                          className="text-[11px] font-normal"
                        >
                          {cap}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {t("logical_models.detail.updated_at")}:{" "}
                    {formatTimestamp(selected.updated_at)}
                  </div>
                </div>
              </div>

              {/* 上游列表 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-medium">
                    {t("logical_models.detail_upstreams")}
                  </h3>
                  <p className="text-xs text-muted-foreground">
                    {t("logical_models.detail_upstreams_help")}
                  </p>
                </div>

                {selected.upstreams.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("logical_models.empty")}
                  </p>
                ) : (
                  <div className="rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[120px]">
                            {t("logical_models.detail.provider")}
                          </TableHead>
                          <TableHead className="w-[200px]">
                            {t("logical_models.detail.model_id")}
                          </TableHead>
                          <TableHead>
                            {t("logical_models.detail.endpoint")}
                          </TableHead>
                          <TableHead>
                            {t("logical_models.detail.region")}
                          </TableHead>
                          <TableHead>
                            {t("logical_models.detail.weight")}
                          </TableHead>
                          <TableHead>
                            {t("logical_models.detail.max_qps")}
                          </TableHead>
                          <TableHead>
                            {t("logical_models.detail.api_style")}
                          </TableHead>
                          <TableHead>
                            {t("logical_models.detail.updated_at")}
                          </TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selected.upstreams.map((up) => (
                          <TableRow
                            key={`${up.provider_id}:${up.model_id}:${up.region ?? "default"}`}
                          >
                            <TableCell className="font-mono text-xs">
                              {up.provider_id}
                            </TableCell>
                            <TableCell className="font-mono text-xs">
                              {up.model_id}
                            </TableCell>
                            <TableCell className="font-mono text-xs max-w-xs truncate">
                              {up.endpoint}
                            </TableCell>
                            <TableCell className="text-xs">
                              {up.region || "-"}
                            </TableCell>
                            <TableCell className="text-xs">
                              {up.base_weight}
                            </TableCell>
                            <TableCell className="text-xs">
                              {up.max_qps ?? "-"}
                            </TableCell>
                            <TableCell className="text-xs uppercase">
                              {up.api_style}
                            </TableCell>
                            <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                              {formatTimestamp(up.updated_at)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

