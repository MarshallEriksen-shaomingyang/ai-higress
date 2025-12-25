"use client";

import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { useI18n } from "@/lib/i18n-context";
import { useBridgeEvents } from "@/lib/hooks/use-bridge-events";
import { useBridgeAgents, useBridgeCancel, useBridgeInvoke, useBridgeTools } from "@/lib/swr/use-bridge";
import { useChatStore } from "@/lib/stores/chat-store";
import { BRIDGE_TOOL_TIMEOUT_MS } from "@/config/timeouts";

const EMPTY_STRING_ARRAY: string[] = [];

export function BridgePanelClient({
  onClose,
  conversationId,
}: {
  onClose?: () => void;
  conversationId?: string;
}) {
  const { t } = useI18n();

  const { agents } = useBridgeAgents();
  const storedAgentIds = useChatStore((s) =>
    conversationId
      ? (s.conversationBridgeAgentIds[conversationId] ?? EMPTY_STRING_ARRAY)
      : EMPTY_STRING_ARRAY
  );
  const setConversationBridgeAgentIds = useChatStore((s) => s.setConversationBridgeAgentIds);

  const [selectedAgentIds, setSelectedAgentIds] = useState<string[]>(storedAgentIds);
  const [activeAgentId, setActiveAgentId] = useState<string | null>(storedAgentIds[0] ?? null);
  const [agentPopoverOpen, setAgentPopoverOpen] = useState(false);

  const { tools } = useBridgeTools(activeAgentId);
  const [toolName, setToolName] = useState<string | null>(null);

  const [argsText, setArgsText] = useState<string>(t("bridge.invoke.args_placeholder") || "{}");
  const storedActiveReqId = useChatStore((s) =>
    conversationId ? (s.conversationBridgeActiveReqIds[conversationId] ?? null) : null
  );
  const setConversationBridgeActiveReqId = useChatStore((s) => s.setConversationBridgeActiveReqId);

  const [activeReqId, setActiveReqId] = useState<string | null>(storedActiveReqId);

  useEffect(() => {
    setSelectedAgentIds(storedAgentIds);
    setActiveAgentId((prev) => {
      if (prev && storedAgentIds.includes(prev)) return prev;
      return storedAgentIds[0] ?? null;
    });
  }, [storedAgentIds]);

  useEffect(() => {
    setActiveReqId(storedActiveReqId);
  }, [storedActiveReqId]);

  const invoke = useBridgeInvoke();
  const cancel = useBridgeCancel();
  const events = useBridgeEvents(800);

  const filteredEvents = useMemo(() => {
    return events.events
      .filter((e) => {
        if (activeAgentId && e.agent_id && e.agent_id !== activeAgentId) return false;
        if (activeReqId && e.req_id && e.req_id !== activeReqId) return false;
        return true;
      })
      .slice()
      .reverse();
  }, [events.events, activeAgentId, activeReqId]);

  const logLines = useMemo(() => {
    const lines: Array<{ key: string; tone: "muted" | "stdout" | "stderr"; text: string }> = [];
    for (const e of filteredEvents) {
      if (e.type === "CHUNK") {
        const payload = (e.payload ?? {}) as Record<string, any>;
        const channel = String(payload.channel || "stdout");
        const data = String(payload.data || "");
        const droppedBytes = Number(payload.dropped_bytes || 0);
        const droppedLines = Number(payload.dropped_lines || 0);
        if (droppedBytes > 0 || droppedLines > 0) {
          lines.push({
            key: `${e.ts ?? 0}-drop`,
            tone: "muted",
            text: `[${t("bridge.events.dropped")}] bytes=${droppedBytes} lines=${droppedLines}`,
          });
        }
        lines.push({
          key: `${e.ts ?? 0}-${lines.length}`,
          tone: channel === "stderr" ? "stderr" : "stdout",
          text: data,
        });
        continue;
      }

      if (e.type === "RESULT") {
        lines.push({
          key: `${e.ts ?? 0}-result`,
          tone: "muted",
          text: `[${t("bridge.events.result")}] ${JSON.stringify(e.payload ?? {}, null, 2)}`,
        });
        continue;
      }

      if (e.type === "INVOKE_ACK" || e.type === "CANCEL_ACK" || e.type === "DISCONNECT") {
        lines.push({
          key: `${e.ts ?? 0}-${e.type}`,
          tone: "muted",
          text: `[${t("bridge.events.meta")}:${e.type}] ${JSON.stringify(e.payload ?? {}, null, 2)}`,
        });
      }
    }
    return lines;
  }, [filteredEvents, t]);

  const submit = async () => {
    if (!activeAgentId || !toolName) return;

    let args: Record<string, any> = {};
    if (argsText.trim()) {
      try {
        args = JSON.parse(argsText);
      } catch {
        toast.error(t("bridge.error.invalid_json"));
        return;
      }
    }
    const resp = await invoke.trigger({
      agent_id: activeAgentId,
      tool_name: toolName,
      arguments: args,
      stream: true,
      timeout_ms: BRIDGE_TOOL_TIMEOUT_MS,
    });
    setActiveReqId(resp.req_id);
    if (conversationId) {
      setConversationBridgeActiveReqId(conversationId, resp.req_id);
    }
  };

  const cancelActive = async () => {
    if (!activeAgentId || !activeReqId) return;
    await cancel.trigger({ agent_id: activeAgentId, req_id: activeReqId, reason: "user_cancel" });
  };

  const clear = () => {
    events.clear();
    setActiveReqId(null);
    if (conversationId) {
      setConversationBridgeActiveReqId(conversationId, null);
    }
  };

  return (
    <div className="flex h-full w-full flex-col bg-background">
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{t("bridge.title")}</div>
          <div className="text-xs text-muted-foreground">{t("bridge.subtitle")}</div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={events.connected ? "default" : "secondary"}>
            {events.connected ? t("bridge.events.connected") : t("bridge.events.connecting")}
          </Badge>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="grid gap-3 p-3">
          <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">{t("bridge.agents")}</CardTitle>
            <CardDescription>{t("bridge.agents.select")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Popover open={agentPopoverOpen} onOpenChange={setAgentPopoverOpen}>
              <PopoverTrigger asChild>
                <Button variant="outline" role="combobox" aria-expanded={agentPopoverOpen} className="justify-between">
                  {selectedAgentIds.length
                    ? `${t("bridge.agents.select")} (${selectedAgentIds.length})`
                    : t("bridge.agents.select")}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[360px] p-3" align="start">
                <ScrollArea className="h-56 pr-2">
                  {agents.length ? (
                    <div className="space-y-2">
                      {agents.map((a) => (
                        <label
                          key={a.agent_id}
                          className="flex items-center gap-3 rounded-md px-2 py-2 hover:bg-muted/50"
                        >
                          <Checkbox
                            checked={selectedAgentIds.includes(a.agent_id)}
                            onCheckedChange={() => {
                              const next = selectedAgentIds.includes(a.agent_id)
                                ? selectedAgentIds.filter((x) => x !== a.agent_id)
                                : [...selectedAgentIds, a.agent_id];
                              setSelectedAgentIds(next);
                              if (conversationId) {
                                setConversationBridgeAgentIds(conversationId, next.length ? next : null);
                              }
                              setActiveAgentId((prev) => {
                                if (prev && next.includes(prev)) return prev;
                                return next[0] ?? null;
                              });
                            }}
                          />
                          <span className="text-sm">{a.agent_id}</span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground py-2">{t("bridge.agents.empty")}</div>
                  )}
                </ScrollArea>
              </PopoverContent>
            </Popover>

            <div className="text-xs text-muted-foreground">{t("bridge.agents.multi_help")}</div>

            <Select value={activeAgentId ?? ""} onValueChange={(v) => setActiveAgentId(v || null)} disabled={!selectedAgentIds.length}>
              <SelectTrigger>
                <SelectValue placeholder={t("bridge.agents.active")} />
              </SelectTrigger>
              <SelectContent>
                {selectedAgentIds.length ? (
                  selectedAgentIds.map((id) => (
                    <SelectItem key={id} value={id}>
                      {id}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value="__empty" disabled>
                    {t("bridge.agents.empty")}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">{t("bridge.tools")}</CardTitle>
            <CardDescription>{t("bridge.tools.select")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Select value={toolName ?? ""} onValueChange={(v) => setToolName(v || null)} disabled={!activeAgentId}>
              <SelectTrigger>
                <SelectValue placeholder={t("bridge.tools.select")} />
              </SelectTrigger>
              <SelectContent>
                {tools.length ? (
                  tools.map((tool) => (
                    <SelectItem key={tool.name} value={tool.name}>
                      {tool.name}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value="__empty" disabled>
                    {t("bridge.tools.empty")}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center justify-between text-sm">
              <span>{t("bridge.invoke")}</span>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={clear}>
                  {t("bridge.events.clear")}
                </Button>
                <Button variant="outline" size="sm" onClick={cancelActive} disabled={!activeReqId || cancel.submitting}>
                  {t("bridge.invoke.cancel")}
                </Button>
                <Button size="sm" onClick={submit} disabled={!activeAgentId || !toolName || invoke.submitting}>
                  {t("bridge.invoke.submit")}
                </Button>
              </div>
            </CardTitle>
            <CardDescription>{t("bridge.invoke.args")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              value={argsText}
              onChange={(e) => setArgsText(e.target.value)}
              className="min-h-24 font-mono text-xs"
            />
            <div className="text-xs text-muted-foreground">
              {activeReqId ? `${t("bridge.req_id")}: ${activeReqId}` : ""}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">{t("bridge.events")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-72 rounded-md border bg-background/60 p-3">
              <div className="space-y-1 font-mono text-xs">
                {logLines.length ? (
                  logLines.map((line) => (
                    <div
                      key={line.key}
                      className={
                        line.tone === "stderr"
                          ? "whitespace-pre-wrap text-destructive"
                          : line.tone === "muted"
                            ? "whitespace-pre-wrap text-muted-foreground"
                            : "whitespace-pre-wrap"
                      }
                    >
                      {line.text}
                    </div>
                  ))
                ) : (
                  <div className="text-muted-foreground">{t("bridge.events.empty")}</div>
                )}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
        </div>
      </div>
    </div>
  );
}
