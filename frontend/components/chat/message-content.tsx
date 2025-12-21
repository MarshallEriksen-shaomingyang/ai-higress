"use client";

import { useEffect, useId, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Eye, EyeOff, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
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
  defaultImageAlt,
}: {
  content: string;
  enableMath: boolean;
  defaultImageAlt: string;
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
        img: ({ alt, src }) => {
          if (!src) return null;
          const srcString = typeof src === 'string' ? src : URL.createObjectURL(src);
          const resolvedAlt = alt && alt.trim().length > 0 ? alt : defaultImageAlt;
          return (
            <a href={srcString} target="_blank" rel="noreferrer" className="block">
              <img
                src={srcString}
                alt={resolvedAlt}
                loading="lazy"
                className="mt-2 max-w-full rounded-md border bg-muted/10"
              />
            </a>
          );
        },
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

function autoEmbedImageUrls(markdown: string) {
  // 仅对“单独一行”的图片链接做自动嵌入，避免误伤普通文本中的 URL
  const imageUrlPattern =
    /(^|\n)\s*(https?:\/\/[^\s)]+?\.(?:png|jpe?g|gif|webp|svg))(?:\s*)(?=\n|$)/gi;
  const dataUrlPattern = /(^|\n)\s*(data:image\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+)(?:\s*)(?=\n|$)/gi;

  return markdown
    .replace(imageUrlPattern, (_m, prefix: string, url: string) => `${prefix}![](${url})`)
    .replace(dataUrlPattern, (_m, prefix: string, url: string) => `${prefix}![](${url})`);
}

function splitThinkForCarousel(think: string): string[] {
  const normalized = (think ?? "").replace(/\r\n/g, "\n").trim();
  if (!normalized) return [];

  const paragraphs = normalized
    .split(/\n{2,}/g)
    .map((p) => p.trim())
    .filter(Boolean);
  if (paragraphs.length > 1) return paragraphs;

  const lines = normalized
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  if (lines.length > 1) return lines;

  // 句子级切分（中英文标点），用于超长单段内容
  const sentenceMatches = normalized.match(/[^。！？.!?]+[。！？.!?]+|[^。！？.!?]+$/g);
  const sentences = (sentenceMatches ?? []).map((s) => s.trim()).filter(Boolean);
  if (sentences.length <= 1) return [normalized];

  const grouped: string[] = [];
  for (let index = 0; index < sentences.length; index += 2) {
    grouped.push(sentences.slice(index, index + 2).join(" "));
  }
  return grouped;
}

function toThinkPreviewText(text: string, maxChars = 56) {
  const normalized = (text ?? "").replace(/\s+/g, " ").trim();
  if (normalized.length <= maxChars) return normalized;
  return `${normalized.slice(0, Math.max(0, maxChars - 1))}…`;
}

function ThinkChipPreview({
  items,
  className,
}: {
  items: string[];
  className?: string;
}) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    setIndex(0);
  }, [items]);

  useEffect(() => {
    if (items.length <= 1) return;
    const timer = window.setInterval(() => {
      setIndex((current) => (current + 1) % items.length);
    }, 1800);
    return () => window.clearInterval(timer);
  }, [items.length]);

  const current = toThinkPreviewText(items[index] ?? "");

  return (
    <span
      key={`${index}-${current.length}`}
      className={cn(
        "min-w-0 max-w-[220px] truncate animate-in fade-in-0 duration-200 text-foreground/70",
        className
      )}
      aria-hidden="true"
      title={current}
    >
      {current}
    </span>
  );
}

export function MessageContent({ content, role, options, className }: MessageContentProps) {
  const { t } = useI18n();
  const thinkPanelId = useId();

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
  const defaultImageAlt = t("chat.message.image");

  const renderBody = (raw: string, preserveNewlines: boolean) => {
    if (!enableMarkdown) {
      return <div className={preserveNewlines ? "whitespace-pre-wrap" : undefined}>{raw}</div>;
    }
    return (
      <MarkdownContent
        content={autoEmbedImageUrls(raw)}
        enableMath={enableMath}
        defaultImageAlt={defaultImageAlt}
      />
    );
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

  const thinkCarouselItems = useMemo(() => splitThinkForCarousel(mergedThink), [mergedThink]);

  return (
    <div className={cn("text-sm break-words", className)}>
      {role === "assistant" && mergedThink ? (
        <div className="mb-2">
          <div className="inline-flex items-center gap-2 rounded-full border bg-muted/10 px-2 py-1 text-xs text-muted-foreground">
            <span className="text-foreground/80">{t("chat.message.thoughts")}</span>
            <span className="h-3 w-px bg-border" aria-hidden="true" />
            {!showThink ? <ThinkChipPreview items={thinkCarouselItems} /> : null}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="h-6 w-6"
                  onClick={() => setShowThink((v) => !v)}
                  aria-label={showThink ? t("chat.message.hide_thoughts") : t("chat.message.show_thoughts")}
                  aria-expanded={showThink}
                  aria-controls={thinkPanelId}
                >
                  {showThink ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </Button>
              </TooltipTrigger>
              <TooltipContent sideOffset={6}>
                {showThink ? t("chat.message.hide_thoughts") : t("chat.message.show_thoughts")}
              </TooltipContent>
            </Tooltip>
          </div>

          {showThink ? (
            <div
              id={thinkPanelId}
              className="mt-2 rounded-md border-l-2 bg-muted/10 px-3 py-2 text-xs leading-relaxed"
            >
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
