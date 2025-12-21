"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Shield } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { useI18n } from "@/lib/i18n-context";
import { useAdminEvals, type AdminEvalStatusFilter } from "@/lib/swr/use-admin-evals";
import { formatDateTime } from "@/lib/utils/time-formatter";
import type { AdminEvalItem } from "@/lib/api-types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function statusBadgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "rated") return "default";
  if (status === "ready") return "secondary";
  if (status === "running") return "outline";
  return "outline";
}

function getBaselineModel(item: AdminEvalItem): string {
  return item.baseline_run?.requested_logical_model || item.baseline_run_id;
}

function getChallengerModels(item: AdminEvalItem): string {
  const names = (item.challengers || [])
    .map((r) => r.requested_logical_model)
    .filter(Boolean);
  return names.length ? names.join(", ") : "-";
}

function shortId(id: string, max = 8): string {
  if (!id) return "-";
  return id.length > max ? `${id.slice(0, max)}…` : id;
}

export function AdminEvalsPageClient() {
  const { t, language } = useI18n();
  const { user, isLoading } = useAuth();
  const router = useRouter();

  const isSuperuser = user?.is_superuser === true;
  const canAccess = !isLoading && !!user && isSuperuser;

  useEffect(() => {
    if (!isLoading && (!user || !isSuperuser)) {
      router.push("/dashboard");
    }
  }, [isLoading, isSuperuser, router, user]);

  const [status, setStatus] = useState<AdminEvalStatusFilter>("all");
  const [projectId, setProjectId] = useState<string>("");
  const [assistantId, setAssistantId] = useState<string>("");

  const { items, nextCursor, loading, loadMore } = useAdminEvals({
    status,
    projectId,
    assistantId,
    limit: 30,
  });

  const [selected, setSelected] = useState<AdminEvalItem | null>(null);
  const open = !!selected;

  const statusOptions = useMemo(
    () => [
      { value: "all" as const, label: t("chat.admin_evals.status_all") },
      { value: "running" as const, label: t("chat.eval.status_running") },
      { value: "ready" as const, label: t("chat.eval.status_ready") },
      { value: "rated" as const, label: t("chat.eval.status_rated") },
    ],
    [t]
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-2">
          <div className="text-muted-foreground">{t("chat.eval.loading")}</div>
        </div>
      </div>
    );
  }

  if (!canAccess) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center space-y-4 max-w-md px-4">
          <div className="flex justify-center">
            <div className="rounded-full bg-muted p-6">
              <Shield className="h-12 w-12 text-muted-foreground" />
            </div>
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-semibold tracking-tight">
              {t("chat.errors.action_contact_admin")}
            </h2>
            <p className="text-muted-foreground">{t("common.error_superuser_required")}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("chat.admin_evals.title")}</h1>
        <p className="text-muted-foreground mt-2">{t("chat.admin_evals.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("chat.admin_evals.filters")}</CardTitle>
          <CardDescription>{t("chat.admin_evals.filters_hint")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">{t("chat.admin_evals.filter_status")}</div>
              <Select value={status} onValueChange={(v) => setStatus(v as AdminEvalStatusFilter)}>
                <SelectTrigger>
                  <SelectValue placeholder={t("chat.admin_evals.filter_status")} />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">{t("chat.admin_evals.filter_project_id")}</div>
              <Input
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                placeholder={t("chat.admin_evals.filter_project_id_placeholder")}
              />
            </div>

            <div className="space-y-2">
              <div className="text-sm text-muted-foreground">{t("chat.admin_evals.filter_assistant_id")}</div>
              <Input
                value={assistantId}
                onChange={(e) => setAssistantId(e.target.value)}
                placeholder={t("chat.admin_evals.filter_assistant_id_placeholder")}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("chat.admin_evals.list_title")}</CardTitle>
          <CardDescription>{t("chat.admin_evals.list_subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {loading && items.length === 0 ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : items.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t("chat.admin_evals.empty")}</div>
          ) : (
            <div className="space-y-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("chat.admin_evals.col_created_at")}</TableHead>
                    <TableHead>{t("chat.admin_evals.col_status")}</TableHead>
                    <TableHead>{t("chat.admin_evals.col_baseline")}</TableHead>
                    <TableHead>{t("chat.admin_evals.col_challengers")}</TableHead>
                    <TableHead className="text-right">{t("chat.admin_evals.col_actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => (
                    <TableRow key={item.eval_id}>
                      <TableCell className="whitespace-nowrap">
                        {formatDateTime(item.created_at, language)}
                      </TableCell>
                      <TableCell>
                        <Badge variant={statusBadgeVariant(item.status)}>{item.status}</Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{getBaselineModel(item)}</TableCell>
                      <TableCell className="font-mono text-xs">{getChallengerModels(item)}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" onClick={() => setSelected(item)}>
                          {t("chat.admin_evals.view")}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground">
                  {t("chat.admin_evals.loaded_count", { count: items.length })}
                </div>
                <Button
                  variant="secondary"
                  disabled={!nextCursor || loading}
                  onClick={loadMore}
                >
                  {t("chat.admin_evals.load_more")}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={open} onOpenChange={(v) => !v && setSelected(null)}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>{t("chat.admin_evals.detail_title")}</DialogTitle>
            <DialogDescription className="font-mono text-xs">
              {selected ? `${shortId(selected.eval_id, 16)} · ${selected.status}` : ""}
            </DialogDescription>
          </DialogHeader>

          {selected ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">{t("chat.admin_evals.detail_meta")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <div className="flex justify-between gap-3">
                      <span className="text-muted-foreground">{t("chat.admin_evals.field_project")}</span>
                      <span className="font-mono text-xs">{shortId(selected.project_id, 16)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-muted-foreground">{t("chat.admin_evals.field_assistant")}</span>
                      <span className="font-mono text-xs">{shortId(selected.assistant_id, 16)}</span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-muted-foreground">{t("chat.admin_evals.field_created_at")}</span>
                      <span className="font-mono text-xs">
                        {formatDateTime(selected.created_at, language)}
                      </span>
                    </div>
                    <div className="flex justify-between gap-3">
                      <span className="text-muted-foreground">{t("chat.admin_evals.field_updated_at")}</span>
                      <span className="font-mono text-xs">
                        {formatDateTime(selected.updated_at, language)}
                      </span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">{t("chat.admin_evals.detail_rating")}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {selected.rating ? (
                      <>
                        <div className="flex justify-between gap-3">
                          <span className="text-muted-foreground">{t("chat.eval.winner")}</span>
                          <span className="font-mono text-xs">{shortId(selected.rating.winner_run_id, 16)}</span>
                        </div>
                        <div className="flex justify-between gap-3">
                          <span className="text-muted-foreground">{t("chat.eval.reason_tags")}</span>
                          <span className="font-mono text-xs">
                            {(selected.rating.reason_tags || []).join(", ") || "-"}
                          </span>
                        </div>
                      </>
                    ) : (
                      <div className="text-sm text-muted-foreground">{t("chat.admin_evals.unrated")}</div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t("chat.admin_evals.detail_runs")}</CardTitle>
                  <CardDescription>{t("chat.admin_evals.detail_runs_hint")}</CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("chat.admin_evals.run_model")}</TableHead>
                        <TableHead>{t("chat.admin_evals.run_status")}</TableHead>
                        <TableHead>{t("chat.admin_evals.run_latency")}</TableHead>
                        <TableHead>{t("chat.admin_evals.run_cost")}</TableHead>
                        <TableHead>{t("chat.admin_evals.run_error")}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selected.baseline_run ? (
                        <TableRow>
                          <TableCell className="font-mono text-xs">
                            {selected.baseline_run.requested_logical_model}
                          </TableCell>
                          <TableCell>
                            <Badge variant={statusBadgeVariant(selected.baseline_run.status)}>
                              {selected.baseline_run.status}
                            </Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {selected.baseline_run.latency_ms ?? "-"}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {selected.baseline_run.cost_credits ?? "-"}
                          </TableCell>
                          <TableCell className="font-mono text-xs">
                            {selected.baseline_run.error_code ?? "-"}
                          </TableCell>
                        </TableRow>
                      ) : null}

                      {(selected.challengers || []).map((run) => (
                        <TableRow key={run.run_id}>
                          <TableCell className="font-mono text-xs">{run.requested_logical_model}</TableCell>
                          <TableCell>
                            <Badge variant={statusBadgeVariant(run.status)}>{run.status}</Badge>
                          </TableCell>
                          <TableCell className="font-mono text-xs">{run.latency_ms ?? "-"}</TableCell>
                          <TableCell className="font-mono text-xs">{run.cost_credits ?? "-"}</TableCell>
                          <TableCell className="font-mono text-xs">{run.error_code ?? "-"}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

