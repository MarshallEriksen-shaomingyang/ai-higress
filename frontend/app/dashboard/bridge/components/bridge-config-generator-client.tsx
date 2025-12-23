"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { useI18n } from "@/lib/i18n-context";
import { useBridgeAgentToken } from "@/lib/swr/use-bridge";
import { useAuthStore } from "@/lib/stores/auth-store";

// Polyfill for crypto.randomUUID in environments where it's not available
function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback implementation
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

type MCPServerForm = {
  id: string;
  name: string;
  transport: "command" | "streamable" | "sse";
  command: string;
  argsText: string;
  envText: string;
  url: string;
  headersText: string;
};

function defaultTunnelUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_BRIDGE_TUNNEL_URL;
  if (envUrl && envUrl.trim()) return envUrl.trim();

  // Heuristic defaults:
  // - Prefer using API base URL hostname to avoid requiring users to type it.
  // - For non-TLS dev environments (http), default to the Go Tunnel Gateway port (:8088).
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window !== "undefined" ? window.location.origin : process.env.NEXT_PUBLIC_BASE_URL);

  const base = apiBaseUrl?.trim();
  if (base) {
    try {
      const u = new URL(base);
      const wsProto = u.protocol === "https:" ? "wss:" : "ws:";
      const ws = new URL(`${wsProto}//${u.host}`);
      ws.pathname = "/bridge/tunnel";
      ws.search = "";
      ws.hash = "";
      if (wsProto === "ws:") {
        ws.hostname = u.hostname;
        ws.port = "8088";
      }
      return ws.toString();
    } catch {
      // fall through
    }
  }

  return "";
}

function yamlQuoted(value: string): string {
  return JSON.stringify(String(value ?? ""));
}

function splitLines(value: string): string[] {
  return (value || "")
    .split("\n")
    .map((v) => v.trim())
    .filter(Boolean);
}

function parseEnvJSON(value: string): Record<string, string> {
  if (!value.trim()) return {};
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("env must be an object");
  }
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(parsed as Record<string, any>)) {
    if (!k) continue;
    out[String(k)] = String(v ?? "");
  }
  return out;
}

function parseHeadersJSON(value: string): Record<string, string> {
  if (!value.trim()) return {};
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("headers must be an object");
  }
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(parsed as Record<string, any>)) {
    if (!k) continue;
    out[String(k)] = String(v ?? "");
  }
  return out;
}

function buildConfigYaml(input: {
  serverUrl: string;
  token: string;
  agentId: string;
  agentLabel: string;
  reconnectInitial: string;
  reconnectMax: string;
  chunkBufferBytes: number;
  chunkMaxFrameBytes: number;
  servers: Array<{
    name: string;
    type?: "command" | "streamable" | "sse";
    command?: string;
    args?: string[];
    env?: Record<string, string>;
    url?: string;
    headers?: Record<string, string>;
  }>;
}): string {
  const lines: string[] = [];
  lines.push(`version: ${yamlQuoted("1.0")}`);
  lines.push("");
  lines.push("server:");
  lines.push(`  url: ${yamlQuoted(input.serverUrl)}`);
  lines.push(`  token: ${yamlQuoted(input.token)}`);
  lines.push(`  reconnect_initial: ${yamlQuoted(input.reconnectInitial)}`);
  lines.push(`  reconnect_max: ${yamlQuoted(input.reconnectMax)}`);
  lines.push("");
  lines.push("agent:");
  lines.push(`  id: ${yamlQuoted(input.agentId)}`);
  lines.push(`  label: ${yamlQuoted(input.agentLabel)}`);
  lines.push(`  chunk_buffer_bytes: ${Math.max(1, Math.floor(input.chunkBufferBytes || 0))}`);
  lines.push(`  chunk_max_frame_bytes: ${Math.max(1, Math.floor(input.chunkMaxFrameBytes || 0))}`);
  lines.push("");
  lines.push("mcp_servers:");

  if (!input.servers.length) {
    lines.push("  []");
    return lines.join("\n");
  }

  for (const s of input.servers) {
    lines.push(`  - name: ${yamlQuoted(s.name)}`);

    if (s.type && s.type !== "command") {
      lines.push(`    type: ${yamlQuoted(s.type)}`);
    }

    if (s.url) {
      lines.push(`    url: ${yamlQuoted(s.url)}`);
    }
    if (s.command) {
      lines.push(`    command: ${yamlQuoted(s.command)}`);
    }

    const args = s.args || [];
    if (s.command) {
      lines.push("    args:");
      if (args.length) {
        for (const arg of args) {
          lines.push(`      - ${yamlQuoted(arg)}`);
        }
      } else {
        lines.push("      []");
      }
    }

    const envEntries = Object.entries(s.env || {}).filter(([k]) => k);
    if (envEntries.length) {
      lines.push("    env:");
      for (const [k, v] of envEntries) {
        lines.push(`      ${k}: ${yamlQuoted(v)}`);
      }
    }

    const headerEntries = Object.entries(s.headers || {}).filter(([k]) => k);
    if (headerEntries.length) {
      lines.push("    headers:");
      for (const [k, v] of headerEntries) {
        lines.push(`      ${k}: ${yamlQuoted(v)}`);
      }
    }
    lines.push("");
  }

  return lines.join("\n").trimEnd() + "\n";
}

type StoredAgentToken = {
  agent_id: string;
  token: string;
  expires_at?: string;
  updated_at?: string;
};

function tokenStorageKey(userId: string, agentId: string): string {
  return `ai_bridge:bridge_agent_token:${userId}:${agentId}`;
}

function lastAgentIdStorageKey(userId: string): string {
  return `ai_bridge:bridge_last_agent_id:${userId}`;
}

function isExpired(expiresAt: string | undefined): boolean {
  if (!expiresAt) return false;
  const ts = Date.parse(expiresAt);
  if (!Number.isFinite(ts)) return false;
  return Date.now() >= ts;
}

export function BridgeConfigGeneratorClient() {
  const { t } = useI18n();
  const agentToken = useBridgeAgentToken();
  const userId = useAuthStore((s) => s.user?.id) ?? null;

  const [serverUrl, setServerUrl] = useState(() => defaultTunnelUrl());
  const [token, setToken] = useState("");
  const [agentId, setAgentId] = useState("my-agent");
  const [agentLabel, setAgentLabel] = useState("My Agent");
  const agentIdTouchedRef = useRef(false);
  const tokenTouchedRef = useRef(false);

  const [reconnectInitial, setReconnectInitial] = useState("1s");
  const [reconnectMax, setReconnectMax] = useState("60s");
  const [chunkBufferBytes, setChunkBufferBytes] = useState<number>(4 * 1024 * 1024);
  const [chunkMaxFrameBytes, setChunkMaxFrameBytes] = useState<number>(16 * 1024);

  const [servers, setServers] = useState<MCPServerForm[]>([
    {
      id: generateUUID(),
      name: "filesystem",
      transport: "command",
      command: "npx",
      argsText: "-y\n@modelcontextprotocol/server-filesystem\n/Users/me/Documents",
      envText: "",
      url: "",
      headersText: "",
    },
  ]);

  const computed = useMemo(() => {
    const parsedServers = servers
      .map((s) => {
        const name = s.name.trim();
        if (!name) return null;

        if (s.transport === "command") {
          const command = s.command.trim();
          if (!command) return null;
          const args = splitLines(s.argsText);
          const env = parseEnvJSON(s.envText);
          return {
            name,
            type: "command" as const,
            command,
            args,
            env,
          };
        }

        const url = s.url.trim();
        if (!url) return null;
        const headers = parseHeadersJSON(s.headersText);
        return {
          name,
          type: s.transport,
          url,
          headers,
        };
      })
      .filter(Boolean) as Array<{
      name: string;
      type: "command" | "streamable" | "sse";
      command?: string;
      args?: string[];
      env?: Record<string, string>;
      url?: string;
      headers?: Record<string, string>;
    }>;

    return buildConfigYaml({
      serverUrl,
      token,
      agentId,
      agentLabel,
      reconnectInitial,
      reconnectMax,
      chunkBufferBytes,
      chunkMaxFrameBytes,
      servers: parsedServers,
    });
  }, [
    agentId,
    agentLabel,
    chunkBufferBytes,
    chunkMaxFrameBytes,
    reconnectInitial,
    reconnectMax,
    serverUrl,
    servers,
    token,
  ]);

  const download = () => {
    try {
      const url = serverUrl.trim();
      if (!url) {
        toast.error(t("bridge.error.missing_server_url"));
        return;
      }
      if (!/^wss?:\/\//i.test(url)) {
        toast.error(t("bridge.error.invalid_server_url"));
        return;
      }
      for (const s of servers) {
        if (s.transport === "command") {
          parseEnvJSON(s.envText);
        } else {
          parseHeadersJSON(s.headersText);
        }
      }
    } catch {
      toast.error(t("bridge.error.invalid_json"));
      return;
    }

    const blob = new Blob([computed], { type: "application/x-yaml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "config.yaml";
    a.click();
    URL.revokeObjectURL(url);
  };

  const generateToken = async (opts?: { silent?: boolean; reset?: boolean }) => {
    try {
      const resp = await agentToken.trigger({
        agent_id: agentId.trim() || undefined,
        reset: opts?.reset ?? false,
      });
      if (resp?.agent_id) setAgentId(resp.agent_id);
      if (resp?.token) setToken(resp.token);
      if (userId && resp?.agent_id && resp?.token) {
        try {
          localStorage.setItem(lastAgentIdStorageKey(userId), resp.agent_id);
          localStorage.setItem(
            tokenStorageKey(userId, resp.agent_id),
            JSON.stringify({
              agent_id: resp.agent_id,
              token: resp.token,
              expires_at: resp.expires_at,
              updated_at: new Date().toISOString(),
            } satisfies StoredAgentToken)
          );
        } catch {
          // ignore storage errors
        }
      }
      if (!opts?.silent) {
        toast.success(
          opts?.reset ? t("bridge.config.token_reset_success") : t("bridge.config.token_generated")
        );
      }
    } catch (err: any) {
      if (!opts?.silent) toast.error(err?.message || t("bridge.error.generate_token_failed"));
    }
  };

  // Load last used agent_id (per user) for smoother UX.
  useEffect(() => {
    if (!userId) return;
    if (agentIdTouchedRef.current) return;
    try {
      const stored = localStorage.getItem(lastAgentIdStorageKey(userId));
      if (stored && stored.trim()) setAgentId(stored.trim());
    } catch {
      // ignore
    }
  }, [userId]);

  // Prefill token from local storage if available and not expired.
  useEffect(() => {
    if (!userId) return;
    const normalizedAgentId = agentId.trim();
    if (!normalizedAgentId) return;

    try {
      localStorage.setItem(lastAgentIdStorageKey(userId), normalizedAgentId);
    } catch {
      // ignore
    }

    if (tokenTouchedRef.current) return;
    if (token.trim()) return;

    try {
      const raw = localStorage.getItem(tokenStorageKey(userId, normalizedAgentId));
      if (!raw) return;
      const parsed = JSON.parse(raw) as StoredAgentToken;
      if (!parsed?.token || typeof parsed.token !== "string") return;
      if (isExpired(parsed.expires_at)) return;
      setToken(parsed.token);
    } catch {
      // ignore
    }
  }, [agentId, token, userId]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{t("bridge.config.title")}</CardTitle>
          <CardDescription>{t("bridge.config.description")}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="grid gap-2">
            <div className="text-sm font-medium">{t("bridge.config.server_url")}</div>
            <Input
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              placeholder={t("bridge.config.server_url_placeholder")}
            />
            <div className="text-xs text-muted-foreground">{t("bridge.config.server_url_help")}</div>
          </div>
          <div className="grid gap-2">
            <div className="text-sm font-medium">{t("bridge.config.token")}</div>
            <div className="flex gap-2">
              <Input
                value={token}
                onChange={(e) => {
                  tokenTouchedRef.current = true;
                  setToken(e.target.value);
                }}
                onBlur={() => {
                  if (!userId) return;
                  const normalizedAgentId = agentId.trim();
                  const normalizedToken = token.trim();
                  if (!normalizedAgentId || !normalizedToken) return;
                  try {
                    localStorage.setItem(lastAgentIdStorageKey(userId), normalizedAgentId);
                    localStorage.setItem(
                      tokenStorageKey(userId, normalizedAgentId),
                      JSON.stringify({
                        agent_id: normalizedAgentId,
                        token: normalizedToken,
                        updated_at: new Date().toISOString(),
                      } satisfies StoredAgentToken)
                    );
                  } catch {
                    // ignore
                  }
                }}
                placeholder={t("bridge.config.token_placeholder")}
              />
              <Button
                type="button"
                variant="outline"
                onClick={() => void generateToken({ reset: true })}
                disabled={agentToken.submitting}
              >
                {agentToken.submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="ml-2">{t("bridge.config.token_generating")}</span>
                  </>
                ) : (
                  t("bridge.config.token_reset")
                )}
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="grid gap-2">
              <div className="text-sm font-medium">{t("bridge.config.agent_id")}</div>
              <Input
                value={agentId}
                onChange={(e) => {
                  agentIdTouchedRef.current = true;
                  setAgentId(e.target.value);
                }}
                onBlur={() => {
                  if (!userId) return;
                  const normalizedAgentId = agentId.trim();
                  if (!normalizedAgentId) return;
                  try {
                    localStorage.setItem(lastAgentIdStorageKey(userId), normalizedAgentId);
                  } catch {
                    // ignore
                  }
                }}
              />
            </div>
            <div className="grid gap-2">
              <div className="text-sm font-medium">{t("bridge.config.agent_label")}</div>
              <Input value={agentLabel} onChange={(e) => setAgentLabel(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="grid gap-2">
              <div className="text-sm font-medium">{t("bridge.config.reconnect_initial")}</div>
              <Input value={reconnectInitial} onChange={(e) => setReconnectInitial(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <div className="text-sm font-medium">{t("bridge.config.reconnect_max")}</div>
              <Input value={reconnectMax} onChange={(e) => setReconnectMax(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="grid gap-2">
              <div className="text-sm font-medium">{t("bridge.config.chunk_buffer_bytes")}</div>
              <Input
                value={String(chunkBufferBytes)}
                onChange={(e) => setChunkBufferBytes(Number(e.target.value || 0))}
              />
            </div>
            <div className="grid gap-2">
              <div className="text-sm font-medium">{t("bridge.config.chunk_max_frame_bytes")}</div>
              <Input
                value={String(chunkMaxFrameBytes)}
                onChange={(e) => setChunkMaxFrameBytes(Number(e.target.value || 0))}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{t("bridge.config.mcp_servers")}</span>
            <Button
              variant="outline"
              onClick={() =>
                setServers((prev) => [
                  ...prev,
                  {
                    id: generateUUID(),
                    name: "",
                    transport: "command",
                    command: "",
                    argsText: "",
                    envText: "",
                    url: "",
                    headersText: "",
                  },
                ])
              }
            >
              {t("bridge.config.add_server")}
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {servers.map((s, idx) => (
            <Card key={s.id}>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between text-sm">
                  <span>
                    {t("bridge.config.server_name")} #{idx + 1}
                  </span>
                  <Button
                    variant="ghost"
                    onClick={() => setServers((prev) => prev.filter((x) => x.id !== s.id))}
                    disabled={servers.length <= 1}
                  >
                    {t("bridge.config.remove_server")}
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <div className="grid gap-2">
                    <div className="text-sm font-medium">{t("bridge.config.server_name")}</div>
                    <Input
                      value={s.name}
                      onChange={(e) =>
                        setServers((prev) =>
                          prev.map((x) => (x.id === s.id ? { ...x, name: e.target.value } : x))
                        )
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <div className="text-sm font-medium">{t("bridge.config.server_transport")}</div>
                    <Select
                      value={s.transport}
                      onValueChange={(value) =>
                        setServers((prev) =>
                          prev.map((x) =>
                            x.id === s.id
                              ? {
                                  ...x,
                                  transport: value as MCPServerForm["transport"],
                                }
                              : x
                          )
                        )
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder={t("bridge.config.server_transport")} />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="command">{t("bridge.config.transport_command")}</SelectItem>
                        <SelectItem value="streamable">{t("bridge.config.transport_streamable")}</SelectItem>
                        <SelectItem value="sse">{t("bridge.config.transport_sse")}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {s.transport === "command" ? (
                  <>
                    <div className="grid gap-2">
                      <div className="text-sm font-medium">{t("bridge.config.server_command")}</div>
                      <Input
                        value={s.command}
                        onChange={(e) =>
                          setServers((prev) =>
                            prev.map((x) => (x.id === s.id ? { ...x, command: e.target.value } : x))
                          )
                        }
                      />
                    </div>
                    <div className="grid gap-2">
                      <div className="text-sm font-medium">{t("bridge.config.server_args")}</div>
                      <Textarea
                        value={s.argsText}
                        onChange={(e) =>
                          setServers((prev) =>
                            prev.map((x) => (x.id === s.id ? { ...x, argsText: e.target.value } : x))
                          )
                        }
                        className="min-h-20 font-mono text-xs"
                      />
                    </div>
                    <div className="grid gap-2">
                      <div className="text-sm font-medium">{t("bridge.config.server_env")}</div>
                      <Textarea
                        value={s.envText}
                        onChange={(e) =>
                          setServers((prev) =>
                            prev.map((x) => (x.id === s.id ? { ...x, envText: e.target.value } : x))
                          )
                        }
                        placeholder={t("bridge.config.env_placeholder")}
                        className="min-h-16 font-mono text-xs"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div className="grid gap-2">
                      <div className="text-sm font-medium">{t("bridge.config.server_remote_url")}</div>
                      <Input
                        value={s.url}
                        onChange={(e) =>
                          setServers((prev) =>
                            prev.map((x) => (x.id === s.id ? { ...x, url: e.target.value } : x))
                          )
                        }
                        placeholder="https://example.com/mcp"
                      />
                    </div>
                    <div className="grid gap-2">
                      <div className="text-sm font-medium">{t("bridge.config.server_headers")}</div>
                      <Textarea
                        value={s.headersText}
                        onChange={(e) =>
                          setServers((prev) =>
                            prev.map((x) =>
                              x.id === s.id ? { ...x, headersText: e.target.value } : x
                            )
                          )
                        }
                        placeholder={t("bridge.config.headers_placeholder")}
                        className="min-h-16 font-mono text-xs"
                      />
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{t("bridge.config.preview")}</span>
            <Button onClick={download}>{t("bridge.config.download")}</Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea value={computed} readOnly className="min-h-72 font-mono text-xs" />
        </CardContent>
      </Card>
    </div>
  );
}
