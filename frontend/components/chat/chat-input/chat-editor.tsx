"use client";

import { Slate, Editable } from "slate-react";
import type { Descendant, Editor } from "slate";
import type { RefObject, ClipboardEvent, KeyboardEvent } from "react";
import { cn } from "@/lib/utils";

interface ChatEditorProps {
  editor: Editor;
  editorRef: RefObject<HTMLDivElement | null>;
  initialValue: Descendant[];
  disabled: boolean;
  isSending: boolean;
  placeholder: string;
  onKeyDown: (event: KeyboardEvent) => void;
  onPaste: (event: ClipboardEvent) => void;
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
}: ChatEditorProps) {
  return (
    <div ref={editorRef} className="flex-1 px-3 pt-3 pb-2 overflow-y-auto">
      <Slate editor={editor} initialValue={initialValue}>
        <Editable
          placeholder={placeholder}
          readOnly={disabled || isSending}
          aria-disabled={disabled || isSending}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
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
