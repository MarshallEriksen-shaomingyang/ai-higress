"use client";

import { useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { useI18n } from "@/lib/i18n-context";
import { useBridgeAgents, useBridgeTools, useBridgeInvoke, useBridgeCancel } from "@/lib/swr/use-bridge";
import { useBridgeEvents } from "@/lib/hooks/use-bridge-events";
import { BridgeConfigGeneratorClient } from "./bridge-config-generator-client";
import { BRIDGE_TOOL_TIMEOUT_MS } from "@/config/timeouts";

export function BridgeDashboardClient() {
  const { t } = useI18n();

  const { agents } = useBridgeAgents();
  const [agentId, setAgentId] = useState<string | null>(null);
  const { tools } = useBridgeTools(agentId);
  const [toolName, setToolName] = useState<string | null>(null);

  const [argsText, setArgsText] = useState<string>(t("bridge.invoke.args_placeholder") || "{}");
  const [activeReqId, setActiveReqId] = useState<string | null>(null);

  const invoke = useBridgeInvoke();
  const cancel = useBridgeCancel();
  const events = useBridgeEvents(400);

  const filteredEvents = useMemo(() => {
    return events.events.filter((e) => {
      if (agentId && e.agent_id && e.agent_id !== agentId) return false;
      if (activeReqId && e.req_id && e.req_id !== activeReqId) return false;
      return true;
    });
  }, [events.events, agentId, activeReqId]);

  const submit = async () => {
    if (!agentId || !toolName) return;
    let args: Record<string, any> = {};
    if (argsText.trim()) {
      try {
        args = JSON.parse(argsText);
      } catch {
        return;
      }
    }
    const resp = await invoke.trigger({
      agent_id: agentId,
      tool_name: toolName,
      arguments: args,
      stream: true,
      timeout_ms: BRIDGE_TOOL_TIMEOUT_MS,
    });
    setActiveReqId(resp.req_id);
  };

  const cancelActive = async () => {
    if (!agentId || !activeReqId) return;
    await cancel.trigger({ agent_id: agentId, req_id: activeReqId, reason: "user_cancel" });
  };

  return (
    <div className="mx-auto w-full max-w-5xl space-y-4">
      <div className="space-y-1">
        <div className="text-xl font-medium">{t("bridge.title")}</div>
        <div className="text-sm text-muted-foreground">{t("bridge.subtitle")}</div>
      </div>

      <Tabs defaultValue="tools" className="w-full">
        <TabsList>
          <TabsTrigger value="tools">{t("bridge.tabs.tools")}</TabsTrigger>
          <TabsTrigger value="config">{t("bridge.tabs.config")}</TabsTrigger>
        </TabsList>

        <TabsContent value="tools" className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{t("bridge.agents")}</span>
                  <Badge variant={events.connected ? "default" : "secondary"}>
                    {events.connected ? t("bridge.events.connected") : t("bridge.events.connecting")}
                  </Badge>
                </CardTitle>
                <CardDescription>{t("bridge.agents.select")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Select value={agentId ?? ""} onValueChange={(v) => setAgentId(v || null)}>
                  <SelectTrigger>
                    <SelectValue placeholder={t("bridge.agents.select")} />
                  </SelectTrigger>
                  <SelectContent>
                    {agents.length ? (
                      agents.map((a) => (
                        <SelectItem key={a.agent_id} value={a.agent_id}>
                          {a.agent_id}
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
              <CardHeader>
                <CardTitle>{t("bridge.tools")}</CardTitle>
                <CardDescription>{t("bridge.tools.select")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Select value={toolName ?? ""} onValueChange={(v) => setToolName(v || null)} disabled={!agentId}>
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
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{t("bridge.invoke")}</span>
                <div className="flex items-center gap-2">
                  <Button variant="outline" onClick={events.clear}>
                    {t("bridge.events.clear")}
                  </Button>
                  <Button variant="outline" onClick={cancelActive} disabled={!activeReqId || cancel.submitting}>
                    {t("bridge.invoke.cancel")}
                  </Button>
                  <Button onClick={submit} disabled={!agentId || !toolName || invoke.submitting}>
                    {t("bridge.invoke.submit")}
                  </Button>
                </div>
              </CardTitle>
              <CardDescription>{t("bridge.invoke.args")}</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <Textarea value={argsText} onChange={(e) => setArgsText(e.target.value)} className="min-h-32 font-mono text-xs" />
                <div className="text-xs text-muted-foreground">
                  {activeReqId ? `${t("bridge.req_id")}: ${activeReqId}` : ""}
                </div>
              </div>

              <div className="min-h-32">
                <ScrollArea className="h-64 rounded-md border bg-background/60 p-3">
                  <div className="space-y-2 font-mono text-xs">
                    {filteredEvents.map((e, idx) => (
                      <div key={`${e.ts ?? 0}-${idx}`} className="whitespace-pre-wrap">
                        <span className="text-muted-foreground">{e.type}</span>
                        {e.req_id ? <span className="text-muted-foreground"> · {e.req_id}</span> : null}
                        {"\n"}
                        <span>{JSON.stringify(e.payload ?? {}, null, 2)}</span>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="config">
          <BridgeConfigGeneratorClient />
        </TabsContent>
      </Tabs>
    </div>
  );
}
