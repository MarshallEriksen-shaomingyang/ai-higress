"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Eye, EyeOff, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useI18n } from "@/lib/i18n-context";
import {
  DEFAULT_MESSAGE_RENDER_OPTIONS,
  type MessageRenderOptions,
} from "@/lib/chat/message-render-options";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type MessageRole = "user" | "assistant" | "system";

interface MessageContentProps {
  content: string;
  role: MessageRole;
  options?: Partial<MessageRenderOptions>;
  className?: string;
}

type Segment =
  | { type: "text"; content: string }
  | { type: "think"; content: string };

function splitByThinkTags(input: string): Segment[] {
  const segments: Segment[] = [];
  const pattern = /<think>([\s\S]*?)<\/think>/gi;

  let lastIndex = 0;
  let match: RegExpExecArray | null = pattern.exec(input);

  while (match) {
    const matchStart = match.index;
    const matchEnd = pattern.lastIndex;

    if (matchStart > lastIndex) {
      const before = input.slice(lastIndex, matchStart);
      if (before) segments.push({ type: "text", content: before });
    }

    const thinkContent = match[1] ?? "";
    if (thinkContent) segments.push({ type: "think", content: thinkContent.trim() });

    lastIndex = matchEnd;
    match = pattern.exec(input);
  }

  if (lastIndex < input.length) {
    const rest = input.slice(lastIndex);
    if (rest) segments.push({ type: "text", content: rest });
  }

  return segments.length > 0 ? segments : [{ type: "text", content: input }];
}

function CodeBlock({
  code,
  language,
  className,
}: {
  code: string;
  language?: string;
  className?: string;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(timer);
  }, [copied]);

  return (
    <div className={cn("mt-2 rounded-md border bg-muted/30", className)}>
      <div className="flex items-center justify-between gap-2 border-b px-2 py-1.5">
        <div className="min-w-0 text-xs text-muted-foreground">
          {language ? language : t("chat.message.code")}
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={handleCopy}
          aria-label={copied ? t("chat.message.copied") : t("chat.message.copy_code")}
        >
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
        </Button>
      </div>
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed">
        <code className="font-mono">{code}</code>
      </pre>
    </div>
  );
}

function MarkdownContent({
  content,
  enableMath,
}: {
  content: string;
  enableMath: boolean;
}) {
  return (
    <ReactMarkdown
      remarkPlugins={enableMath ? [remarkGfm, remarkMath] : [remarkGfm]}
      rehypePlugins={enableMath ? [rehypeKatex] : []}
      components={{
        a: ({ children, href }) => (
          <a
            href={href}
            className="underline underline-offset-2"
            target="_blank"
            rel="noreferrer"
          >
            {children}
          </a>
        ),
        code: ({ children, className, node, ...props }) => {
          const raw = String(children ?? "");
          const langMatch = /language-(\w+)/.exec(className || "");
          const language = langMatch?.[1];
          const isInline = !(className || "").includes("language-");

          if (isInline) {
            return (
              <code
                className="rounded bg-muted/50 px-1 py-0.5 font-mono text-xs"
                {...props}
              >
                {children}
              </code>
            );
          }

          return <CodeBlock code={raw.replace(/\n$/, "")} language={language} />;
        },
        table: ({ children }) => (
          <div className="mt-2 overflow-x-auto rounded-md border">
            <Table>{children}</Table>
          </div>
        ),
        thead: ({ children }) => <TableHeader>{children}</TableHeader>,
        tbody: ({ children }) => <TableBody>{children}</TableBody>,
        tr: ({ children }) => <TableRow>{children}</TableRow>,
        th: ({ children }) => <TableHead>{children}</TableHead>,
        td: ({ children }) => <TableCell>{children}</TableCell>,
        h1: ({ children }) => <h1 className="mt-3 text-base font-semibold first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="mt-3 text-sm font-semibold first:mt-0">{children}</h2>,
        h3: ({ children }) => <h3 className="mt-3 text-sm font-medium first:mt-0">{children}</h3>,
        p: ({ children }) => <p className="mt-2 first:mt-0">{children}</p>,
        ul: ({ children }) => <ul className="mt-2 list-disc pl-5">{children}</ul>,
        ol: ({ children }) => <ol className="mt-2 list-decimal pl-5">{children}</ol>,
        blockquote: ({ children }) => (
          <blockquote className="mt-2 border-l-2 pl-3 text-muted-foreground">
            {children}
          </blockquote>
        ),
        hr: () => <div className="my-3 h-px w-full bg-border" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

function unwrapThinkTags(input: string) {
  return input.replace(/<think>([\s\S]*?)<\/think>/gi, (_, inner: string) => inner ?? "");
}

export function MessageContent({ content, role, options, className }: MessageContentProps) {
  const { t } = useI18n();

  const resolved = useMemo(() => {
    return { ...DEFAULT_MESSAGE_RENDER_OPTIONS, ...(options ?? {}) };
  }, [options]);

  const segments = useMemo(() => {
    if (role !== "assistant") {
      return [{ type: "text" as const, content }];
    }
    if (!resolved.collapse_think) {
      return [{ type: "text" as const, content: unwrapThinkTags(content) }];
    }
    return splitByThinkTags(content);
  }, [content, role, resolved.collapse_think]);

  const enableMarkdown = resolved.enable_markdown;
  const enableMath = resolved.enable_math;

  const renderBody = (raw: string, preserveNewlines: boolean) => {
    if (!enableMarkdown) {
      return <div className={preserveNewlines ? "whitespace-pre-wrap" : undefined}>{raw}</div>;
    }
    return <MarkdownContent content={raw} enableMath={enableMath} />;
  };

  const thinkSegments = segments.filter((s) => s.type === "think") as Array<
    Extract<Segment, { type: "think" }>
  >;
  const textSegments = segments.filter((s) => s.type === "text") as Array<
    Extract<Segment, { type: "text" }>
  >;

  const mergedText = textSegments.map((s) => s.content).join("").trim();
  const mergedThink = thinkSegments.map((s) => s.content).join("\n\n").trim();

  const [showThink, setShowThink] = useState(() => resolved.default_show_think);

  useEffect(() => {
    setShowThink(resolved.default_show_think);
  }, [resolved.default_show_think, content]);

  return (
    <div className={cn("text-sm break-words", className)}>
      {role === "assistant" && mergedThink ? (
        <div className="mb-2 rounded-md border bg-muted/20">
          <div className="flex items-center justify-between gap-2 px-2 py-1.5">
            <div className="min-w-0 text-xs text-muted-foreground">
              {t("chat.message.thoughts")}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowThink((v) => !v)}
              aria-label={showThink ? t("chat.message.hide_thoughts") : t("chat.message.show_thoughts")}
            >
              {showThink ? (
                <>
                  <EyeOff className="mr-2 size-4" />
                  {t("chat.message.hide")}
                </>
              ) : (
                <>
                  <Eye className="mr-2 size-4" />
                  {t("chat.message.show")}
                </>
              )}
            </Button>
          </div>
          {showThink ? (
            <div className="border-t px-3 py-2 text-xs leading-relaxed">
              {renderBody(mergedThink, true)}
            </div>
          ) : null}
        </div>
      ) : null}

      {mergedText ? (
        <div>{renderBody(mergedText, role === "user")}</div>
      ) : null}
    </div>
  );
}
