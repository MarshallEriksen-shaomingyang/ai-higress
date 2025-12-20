"use client";

import { useCallback, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Loader2, Play, Plus, Trash2, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useErrorDisplay } from "@/lib/errors";
import { useUserProbeTasks } from "@/lib/swr/use-user-probes";
import type {
  CreateUserProbeTaskRequest,
  Model,
  ProbeApiStyle,
  UpdateUserProbeTaskRequest,
  UserProbeRun,
  UserProbeTask,
} from "@/http/provider";

interface ProviderProbesTabProps {
  userId: string;
  providerId: string;
  models: Model[];
  translations: any;
}

const _formatTime = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
};

const _parsePositiveInt = (raw: string) => {
  const cleaned = (raw ?? "").replace(/[,_\s，]/g, "").trim();
  if (!cleaned) return Number.NaN;
  const parsed = Number(cleaned);
  if (!Number.isFinite(parsed)) return Number.NaN;
  if (parsed <= 0) return Number.NaN;
  return Math.floor(parsed);
};

const _statusBadge = (task: UserProbeTask) => {
  const run = task.last_run;
  if (!run) return <Badge variant="secondary">-</Badge>;
  if (run.success) return <Badge variant="default">{run.status_code ?? 200}</Badge>;
  return <Badge variant="destructive">{run.status_code ?? "ERR"}</Badge>;
};

export function ProviderProbesTab({
  userId,
  providerId,
  models,
  translations,
}: ProviderProbesTabProps) {
  const { showError } = useErrorDisplay();

  const {
    tasks,
    loading,
    refresh,
    createTask,
    updateTask,
    deleteTask,
    runNow,
    creating,
    updating,
    deleting,
  } = useUserProbeTasks({ userId, providerId });

  const modelOptions = useMemo(() => {
    const items = (models ?? []).map((m) => ({
      id: m.alias || m.model_id,
      label: m.alias ? `${m.alias} (${m.model_id})` : m.model_id,
      value: m.model_id,
    }));
    const seen = new Set<string>();
    return items.filter((it) => {
      if (seen.has(it.value)) return false;
      seen.add(it.value);
      return true;
    });
  }, [models]);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<UserProbeTask | null>(null);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deletingTask, setDeletingTask] = useState<UserProbeTask | null>(null);

  const [resultOpen, setResultOpen] = useState(false);
  const [latestRun, setLatestRun] = useState<UserProbeRun | null>(null);

  const [draftName, setDraftName] = useState("");
  const [draftModelId, setDraftModelId] = useState("");
  const [draftPrompt, setDraftPrompt] = useState("");
  const [draftInterval, setDraftInterval] = useState("300");
  const [draftMaxTokens, setDraftMaxTokens] = useState("16");
  const [draftApiStyle, setDraftApiStyle] = useState<ProbeApiStyle>("auto");
  const [draftEnabled, setDraftEnabled] = useState(true);

  const resetDraft = useCallback(() => {
    setDraftName(translations?.form?.defaultName ?? "probe");
    setDraftModelId(modelOptions[0]?.value ?? "");
    setDraftPrompt(translations?.form?.defaultPrompt ?? "ping");
    setDraftInterval("300");
    setDraftMaxTokens("16");
    setDraftApiStyle("auto");
    setDraftEnabled(true);
  }, [modelOptions, translations]);

  const openCreate = useCallback(() => {
    setEditingTask(null);
    resetDraft();
    setEditorOpen(true);
  }, [resetDraft]);

  const openEdit = useCallback((task: UserProbeTask) => {
    setEditingTask(task);
    setDraftName(task.name ?? "");
    setDraftModelId(task.model_id ?? "");
    setDraftPrompt(task.prompt ?? "");
    setDraftInterval(String(task.interval_seconds ?? 300));
    setDraftMaxTokens(String(task.max_tokens ?? 16));
    setDraftApiStyle((task.api_style as ProbeApiStyle) ?? "auto");
    setDraftEnabled(!!task.enabled);
    setEditorOpen(true);
  }, []);

  const submit = useCallback(async () => {
    const intervalSeconds = _parsePositiveInt(draftInterval);
    const maxTokens = _parsePositiveInt(draftMaxTokens);

    if (!draftName.trim()) {
      toast.error(translations?.errors?.nameRequired ?? "name required");
      return;
    }
    if (!draftModelId.trim()) {
      toast.error(translations?.errors?.modelRequired ?? "model required");
      return;
    }
    if (!draftPrompt.trim()) {
      toast.error(translations?.errors?.promptRequired ?? "prompt required");
      return;
    }
    if (!Number.isFinite(intervalSeconds)) {
      toast.error(translations?.errors?.intervalInvalid ?? "interval invalid");
      return;
    }
    if (!Number.isFinite(maxTokens)) {
      toast.error(translations?.errors?.maxTokensInvalid ?? "max_tokens invalid");
      return;
    }

    try {
      if (!editingTask) {
        const payload: CreateUserProbeTaskRequest = {
          name: draftName.trim(),
          model_id: draftModelId.trim(),
          prompt: draftPrompt.trim(),
          interval_seconds: intervalSeconds,
          max_tokens: maxTokens,
          api_style: draftApiStyle,
          enabled: draftEnabled,
        };
        await createTask(payload);
        toast.success(translations?.toast?.created ?? "created");
      } else {
        const payload: UpdateUserProbeTaskRequest = {
          name: draftName.trim(),
          model_id: draftModelId.trim(),
          prompt: draftPrompt.trim(),
          interval_seconds: intervalSeconds,
          max_tokens: maxTokens,
          api_style: draftApiStyle,
          enabled: draftEnabled,
        };
        await updateTask(editingTask.id, payload);
        toast.success(translations?.toast?.updated ?? "updated");
      }
      setEditorOpen(false);
      setEditingTask(null);
    } catch (err) {
      showError(err, { context: translations?.toast?.failed ?? "failed" });
    }
  }, [
    createTask,
    draftApiStyle,
    draftEnabled,
    draftInterval,
    draftMaxTokens,
    draftModelId,
    draftName,
    draftPrompt,
    editingTask,
    showError,
    translations,
    updateTask,
  ]);

  const requestDelete = useCallback((task: UserProbeTask) => {
    setDeletingTask(task);
    setDeleteOpen(true);
  }, []);

  const confirmDelete = useCallback(async () => {
    if (!deletingTask) return;
    try {
      await deleteTask(deletingTask.id);
      toast.success(translations?.toast?.deleted ?? "deleted");
      setDeleteOpen(false);
      setDeletingTask(null);
    } catch (err) {
      showError(err, { context: translations?.toast?.failed ?? "failed" });
    }
  }, [deleteTask, deletingTask, showError, translations]);

  const toggleEnabled = useCallback(
    async (task: UserProbeTask, enabled: boolean) => {
      try {
        await updateTask(task.id, { enabled });
      } catch (err) {
        showError(err, { context: translations?.toast?.failed ?? "failed" });
      }
    },
    [showError, translations, updateTask]
  );

  const handleRunNow = useCallback(
    async (task: UserProbeTask) => {
      try {
        const run = await runNow(task.id);
        setLatestRun(run);
        setResultOpen(true);
        toast.success(translations?.toast?.ran ?? "ran");
      } catch (err) {
        showError(err, { context: translations?.toast?.runFailed ?? "run failed" });
      }
    },
    [runNow, showError, translations]
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div className="space-y-1">
            <CardTitle>{translations?.title ?? "Probes"}</CardTitle>
            <p className="text-sm text-muted-foreground">
              {translations?.description ?? ""}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => refresh()} disabled={loading}>
              {loading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              {translations?.refresh ?? "Refresh"}
            </Button>
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4 mr-2" />
              {translations?.create ?? "Create"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-sm text-muted-foreground">{translations?.loading ?? "Loading..."}</div>
          ) : tasks.length === 0 ? (
            <div className="text-sm text-muted-foreground">{translations?.empty ?? "Empty"}</div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{translations?.table?.name ?? "Name"}</TableHead>
                    <TableHead>{translations?.table?.model ?? "Model"}</TableHead>
                    <TableHead>{translations?.table?.interval ?? "Interval"}</TableHead>
                    <TableHead>{translations?.table?.enabled ?? "Enabled"}</TableHead>
                    <TableHead>{translations?.table?.lastStatus ?? "Last"}</TableHead>
                    <TableHead>{translations?.table?.lastRunAt ?? "Last Run"}</TableHead>
                    <TableHead className="text-right">{translations?.table?.actions ?? "Actions"}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tasks.map((task) => (
                    <TableRow key={task.id}>
                      <TableCell className="font-medium">{task.name}</TableCell>
                      <TableCell className="font-mono text-xs">{task.model_id}</TableCell>
                      <TableCell>{task.interval_seconds}s</TableCell>
                      <TableCell>
                        <Switch
                          checked={task.enabled}
                          onCheckedChange={(checked) => toggleEnabled(task, checked)}
                          disabled={updating || task.in_progress}
                        />
                      </TableCell>
                      <TableCell>{_statusBadge(task)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {_formatTime(task.last_run_at)}
                      </TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRunNow(task)}
                          disabled={task.in_progress}
                        >
                          <Play className="h-4 w-4 mr-2" />
                          {translations?.actions?.run ?? "Run"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openEdit(task)}
                        >
                          <Pencil className="h-4 w-4 mr-2" />
                          {translations?.actions?.edit ?? "Edit"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => requestDelete(task)}
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          {translations?.actions?.delete ?? "Delete"}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={editorOpen} onOpenChange={setEditorOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {editingTask ? translations?.editTitle ?? "Edit" : translations?.createTitle ?? "Create"}
            </DialogTitle>
            <DialogDescription>{translations?.form?.hint ?? ""}</DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto px-1">
            <div className="grid gap-4">
              <div className="grid gap-2">
                <Label>{translations?.form?.name ?? "Name"}</Label>
                <Input value={draftName} onChange={(e) => setDraftName(e.target.value)} />
              </div>

              <div className="grid gap-2">
                <Label>{translations?.form?.model ?? "Model"}</Label>
                {modelOptions.length > 0 ? (
                  <Select value={draftModelId} onValueChange={setDraftModelId}>
                    <SelectTrigger>
                      <SelectValue placeholder={translations?.form?.modelPlaceholder ?? ""} />
                    </SelectTrigger>
                    <SelectContent>
                      {modelOptions.map((m) => (
                        <SelectItem key={m.value} value={m.value}>
                          {m.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    value={draftModelId}
                    onChange={(e) => setDraftModelId(e.target.value)}
                    placeholder={translations?.form?.modelPlaceholder ?? ""}
                  />
                )}
              </div>

              <div className="grid gap-2">
                <Label>{translations?.form?.prompt ?? "Prompt"}</Label>
                <Textarea
                  value={draftPrompt}
                  onChange={(e) => setDraftPrompt(e.target.value)}
                  rows={4}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="grid gap-2">
                  <Label>{translations?.form?.interval ?? "Interval (s)"}</Label>
                  <Input
                    inputMode="numeric"
                    value={draftInterval}
                    onChange={(e) => setDraftInterval(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>{translations?.form?.maxTokens ?? "Max tokens"}</Label>
                  <Input
                    inputMode="numeric"
                    value={draftMaxTokens}
                    onChange={(e) => setDraftMaxTokens(e.target.value)}
                  />
                </div>
                <div className="grid gap-2">
                  <Label>{translations?.form?.apiStyle ?? "API style"}</Label>
                  <Select
                    value={draftApiStyle}
                    onValueChange={(v) => setDraftApiStyle(v as ProbeApiStyle)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="auto">{translations?.apiStyle?.auto ?? "auto"}</SelectItem>
                      <SelectItem value="openai">{translations?.apiStyle?.openai ?? "openai"}</SelectItem>
                      <SelectItem value="claude">{translations?.apiStyle?.claude ?? "claude"}</SelectItem>
                      <SelectItem value="responses">{translations?.apiStyle?.responses ?? "responses"}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex items-center justify-between rounded-md border p-3">
                <div className="space-y-0.5">
                  <div className="text-sm font-medium">{translations?.form?.enabled ?? "Enabled"}</div>
                  <div className="text-xs text-muted-foreground">
                    {translations?.form?.enabledHint ?? ""}
                  </div>
                </div>
                <Switch checked={draftEnabled} onCheckedChange={setDraftEnabled} />
              </div>
            </div>
          </div>

          <DialogFooter className="pt-4">
            <Button variant="outline" onClick={() => setEditorOpen(false)}>
              {translations?.cancel ?? "Cancel"}
            </Button>
            <Button onClick={submit} disabled={creating || updating}>
              {creating || updating ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : null}
              {translations?.save ?? "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={resultOpen} onOpenChange={setResultOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>{translations?.result?.title ?? "Result"}</DialogTitle>
            <DialogDescription className="font-mono text-xs">
              {latestRun
                ? `${providerId} · ${latestRun.model_id} · ${latestRun.api_style} · ${latestRun.status_code ?? "-"} · ${latestRun.latency_ms ?? "-"}ms`
                : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto px-1 space-y-3">
            {latestRun?.response_text ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{translations?.result?.assistant ?? "Assistant"}</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-sm">{latestRun.response_text}</pre>
                </CardContent>
              </Card>
            ) : null}
            {latestRun?.response_excerpt ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{translations?.result?.raw ?? "Raw"}</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-xs text-muted-foreground">
                    {latestRun.response_excerpt}
                  </pre>
                </CardContent>
              </Card>
            ) : null}
            {latestRun?.error_message ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">{translations?.result?.error ?? "Error"}</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="whitespace-pre-wrap text-xs text-destructive">
                    {latestRun.error_message}
                  </pre>
                </CardContent>
              </Card>
            ) : null}
          </div>
          <DialogFooter className="pt-4">
            <Button variant="outline" onClick={() => setResultOpen(false)}>
              {translations?.cancel ?? "Close"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{translations?.delete?.title ?? "Delete"}</DialogTitle>
            <DialogDescription>{translations?.delete?.description ?? ""}</DialogDescription>
          </DialogHeader>
          <DialogFooter className="pt-4">
            <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={deleting}>
              {translations?.cancel ?? "Cancel"}
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>
              {deleting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
              {translations?.delete?.confirm ?? "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
