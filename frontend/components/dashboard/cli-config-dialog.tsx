"use client"

import { useEffect, useState, type ClipboardEvent } from "react"
import dynamic from "next/dynamic"
import { Copy, Check, Terminal, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { useI18n } from "@/lib/i18n-context"
import { useCliConfig } from "@/lib/swr"

// 动态加载 Select 组件
const Select = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.Select })), { ssr: false })
const SelectContent = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectContent })), { ssr: false })
const SelectItem = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectItem })), { ssr: false })
const SelectTrigger = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectTrigger })), { ssr: false })
const SelectValue = dynamic(() => import("@/components/ui/select").then(mod => ({ default: mod.SelectValue })), { ssr: false })

interface CliConfigDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  apiKeyId: string
}

type ClientType = "claude" | "codex"
type PlatformType = "windows" | "mac" | "linux"

export function CliConfigDialog({
  open,
  onOpenChange,
  apiKeyId,
}: CliConfigDialogProps) {
  const { t } = useI18n()
  const [client, setClient] = useState<ClientType>("claude")
  const [platform, setPlatform] = useState<PlatformType>("mac")
  const [copied, setCopied] = useState(false)
  const [apiKeyToken, setApiKeyToken] = useState("")

  // 使用 SWR Hook 获取配置信息
  const { config, error, loading } = useCliConfig(open ? apiKeyId : null)

  // 脚本 URL 使用前端环境变量（当前访问的后端地址）
  const scriptBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || (typeof window !== "undefined" ? window.location.origin : "")
  const apiUrl = config?.api_url || ""
  const tokenValue = apiKeyToken.trim() || "YOUR_API_KEY"
  const tokenReady = apiKeyToken.trim().length > 0
  const scriptUrl = `${scriptBaseUrl}/api/v1/cli/install?client=${client}&platform=${platform}&key=${encodeURIComponent(tokenValue)}&url=${encodeURIComponent(apiUrl)}`
  
  const command = platform === "windows"
    ? `irm "${scriptUrl}" | iex`
    : `curl -fsSL "${scriptUrl}" | bash`

  const displayCommand = platform === "windows"
    ? `irm "${scriptUrl}" |\n  iex`
    : `curl -fsSL "${scriptUrl}" |\n  bash`

  useEffect(() => {
    if (!open) {
      return
    }
    setCopied(false)
    setApiKeyToken("")
  }, [open, apiKeyId])

  const handleCopy = async () => {
    if (!tokenReady) {
      return
    }
    await navigator.clipboard.writeText(command)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleCommandCopy = (event: ClipboardEvent<HTMLElement>) => {
    // 允许 UI 里分行展示，但无论用户如何复制（按钮/选中复制），都写入单行可执行命令。
    event.clipboardData.setData("text/plain", command)
    event.preventDefault()
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            {t("cliConfig.title")}
          </DialogTitle>
          <DialogDescription>
            {t("cliConfig.description")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {loading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">{t("cliConfig.loading")}</span>
            </div>
          )}

          {error && (
            <div className="bg-red-50 dark:bg-red-950 p-3 rounded-md text-sm">
              <p className="font-medium text-red-800 dark:text-red-200">
                ❌ {error.message || t("cliConfig.loadError")}
              </p>
            </div>
          )}

          {!loading && !error && (
            <>
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{t("cliConfig.clientLabel")}</Label>
                  <Select value={client} onValueChange={(v) => setClient(v as ClientType)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="claude">{t("cliConfig.claudeCli")}</SelectItem>
                      <SelectItem value="codex">{t("cliConfig.codexCli")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>{t("cliConfig.platformLabel")}</Label>
                  <Select value={platform} onValueChange={(v) => setPlatform(v as PlatformType)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="mac">{t("cliConfig.macOS")}</SelectItem>
                      <SelectItem value="linux">{t("cliConfig.linux")}</SelectItem>
                      <SelectItem value="windows">{t("cliConfig.windows")}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t("cliConfig.apiKeyLabel")}</Label>
                <Input
                  value={apiKeyToken}
                  onChange={(e) => setApiKeyToken(e.target.value)}
                  placeholder={t("cliConfig.apiKeyPlaceholder", {
                    prefix: config?.key_prefix || "",
                  })}
                  autoComplete="off"
                  spellCheck={false}
                />
                <p className="text-xs text-muted-foreground">
                  {t("cliConfig.apiKeyHelp", { prefix: config?.key_prefix || "" })}
                </p>
              </div>

              <div className="space-y-2">
                <Label>{t("cliConfig.commandLabel")}</Label>
                <div className="relative">
                  <pre className="bg-muted p-3 rounded-md text-sm pr-12 whitespace-pre-wrap break-all">
                    <code onCopy={handleCommandCopy}>{displayCommand}</code>
                  </pre>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="absolute top-2 right-2"
                    onClick={handleCopy}
                    disabled={!tokenReady}
                    title={copied ? t("cliConfig.copied") : t("cliConfig.copy")}
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-green-600" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {!tokenReady && (
                  <p className="text-xs text-muted-foreground">
                    {t("cliConfig.apiKeyRequired")}
                  </p>
                )}
              </div>

              <div className="bg-blue-50 dark:bg-blue-950 p-3 rounded-md text-sm space-y-2">
                <p className="font-medium">{t("cliConfig.instructions.title")}</p>
                <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                  <li>{t("cliConfig.instructions.step1")}</li>
                  <li>{platform === "windows" ? t("cliConfig.instructions.step2Windows") : t("cliConfig.instructions.step2")}</li>
                  <li>{t("cliConfig.instructions.step3")}</li>
                  <li>{t("cliConfig.instructions.step4")}</li>
                </ol>
              </div>

              <div className="bg-green-50 dark:bg-green-950 p-3 rounded-md text-sm">
                <p className="text-green-800 dark:text-green-200">
                  {t("cliConfig.mergeNotice")}
                </p>
              </div>

              {platform === "windows" && (
                <div className="bg-yellow-50 dark:bg-yellow-950 p-3 rounded-md text-sm">
                  <p className="text-yellow-800 dark:text-yellow-200">
                    {t("cliConfig.windowsWarning")}
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
