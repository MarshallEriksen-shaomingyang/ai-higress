"use client";

import { useCallback } from "react";
import { Slate, Editable } from "slate-react";
import { Text } from "slate";
import type { Descendant, Editor, NodeEntry, Range } from "slate";
import type { RefObject, ClipboardEvent, KeyboardEvent } from "react";
import type { RenderLeafProps } from "slate-react";
import type { Text as TextType } from "slate";
import { cn } from "@/lib/utils";

// 匹配斜杠命令的正则
const SLASH_COMMAND_REGEX = /^\/[a-zA-Z]*$/;

interface ChatEditorProps {
  editor: Editor;
  editorRef: RefObject<HTMLDivElement | null>;
  initialValue: Descendant[];
  disabled: boolean;
  isSending: boolean;
  placeholder: string;
  onKeyDown: (event: KeyboardEvent) => void;
  onPaste: (event: ClipboardEvent) => void;
  onChange?: (value: Descendant[]) => void;
  className?: string;
  isSlashCommand?: boolean;
}

// 自定义 Leaf 渲染，用于高亮斜杠命令
interface CustomLeafProps extends RenderLeafProps {
  leaf: TextType & { slashCommand?: boolean };
}

function Leaf({ attributes, children, leaf }: CustomLeafProps) {
  if (leaf.slashCommand) {
    return (
      <span
        {...attributes}
        className="text-primary font-medium bg-primary/10 rounded px-0.5"
      >
        {children}
      </span>
    );
  }
  return <span {...attributes}>{children}</span>;
}

export function ChatEditor({
  editor,
  editorRef,
  initialValue,
  disabled,
  isSending,
  placeholder,
  onKeyDown,
  onPaste,
  onChange,
  className,
  isSlashCommand = false,
}: ChatEditorProps) {
  // 装饰器：标记斜杠命令文本
  const decorate = useCallback(
    ([node, path]: NodeEntry): Range[] => {
      const ranges: Range[] = [];

      if (!Text.isText(node)) return ranges;

      const text = node.text.trim();

      // 只有当文本是斜杠命令格式且处于斜杠命令状态时才高亮
      if (isSlashCommand && SLASH_COMMAND_REGEX.test(text)) {
        ranges.push({
          anchor: { path, offset: 0 },
          focus: { path, offset: node.text.length },
          slashCommand: true,
        } as Range & { slashCommand: boolean });
      }

      return ranges;
    },
    [isSlashCommand]
  );

  const renderLeaf = useCallback(
    (props: RenderLeafProps) => <Leaf {...props} leaf={props.leaf as CustomLeafProps["leaf"]} />,
    []
  );

  return (
    <div
      ref={editorRef}
      className={cn("flex-1 min-h-0 px-3 pt-3 pb-2 overflow-y-auto min-h-[72px]", className)}
    >
      <Slate editor={editor} initialValue={initialValue} onChange={onChange}>
        <Editable
          placeholder={placeholder}
          readOnly={disabled || isSending}
          aria-disabled={disabled || isSending}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          decorate={decorate}
          renderLeaf={renderLeaf}
          className={cn(
            "w-full h-full resize-none text-sm outline-none",
            "placeholder:text-muted-foreground",
            (disabled || isSending) && "cursor-not-allowed opacity-50"
          )}
        />
      </Slate>
    </div>
  );
}
