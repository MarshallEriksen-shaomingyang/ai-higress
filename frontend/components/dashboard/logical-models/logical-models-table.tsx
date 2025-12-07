"use client";

import React from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Cpu, Eye } from "lucide-react";
import type { LogicalModel } from "@/http/logical-model";
import { useI18n } from "@/lib/i18n-context";

interface LogicalModelsTableProps {
  models: LogicalModel[];
  onSelect: (model: LogicalModel) => void;
}

export function LogicalModelsTable({ models, onSelect }: LogicalModelsTableProps) {
  const { t } = useI18n();

  const formatUpdatedAt = (timestamp: number) => {
    if (!timestamp) return "-";
    return new Date(timestamp * 1000).toLocaleString();
  };

  const totalQps = (model: LogicalModel) =>
    model.upstreams.reduce((sum, up) => sum + (up.max_qps ?? 0), 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("logical_models.table_title")}</CardTitle>
        <CardDescription>
          {t("logical_models.table_description")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {models.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6">
            {t("logical_models.empty")}
          </p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("logical_models.column_name")}</TableHead>
                <TableHead>{t("logical_models.column_logical_id")}</TableHead>
                <TableHead>{t("logical_models.column_capabilities")}</TableHead>
                <TableHead className="text-center">
                  {t("logical_models.column_upstreams")}
                </TableHead>
                <TableHead>{t("logical_models.column_qps")}</TableHead>
                <TableHead>{t("logical_models.column_status")}</TableHead>
                <TableHead>{t("logical_models.column_updated_at")}</TableHead>
                <TableHead className="text-right">
                  {t("logical_models.column_actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {models.map((model) => (
                <TableRow key={model.logical_id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-muted-foreground" />
                      <span>{model.display_name || model.logical_id}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="text-xs text-muted-foreground">
                      {model.logical_id}
                    </code>
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {model.capabilities.map((cap) => (
                        <Badge
                          key={cap}
                          variant="outline"
                          className="text-[11px] font-normal"
                        >
                          {cap}
                        </Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    {model.upstreams.length}
                  </TableCell>
                  <TableCell>
                    {(() => {
                      const qps = totalQps(model);
                      return qps > 0 ? qps : "-";
                    })()}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={model.enabled ? "secondary" : "outline"}
                      className="text-xs"
                    >
                      {model.enabled
                        ? t("logical_models.status_active")
                        : t("logical_models.status_inactive")}
                    </Badge>
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                    {formatUpdatedAt(model.updated_at)}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => onSelect(model)}
                    >
                      <Eye className="w-4 h-4 mr-1" />
                      {t("logical_models.action_view_details")}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
