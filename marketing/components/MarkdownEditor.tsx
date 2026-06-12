"use client";

import { useRef, useCallback, useState } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Bold,
  Italic,
  Heading2,
  Heading3,
  Link,
  Image,
  Code,
  Quote,
  List,
  Upload,
} from "lucide-react";

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  onImageInsert?: (cursorPos: number) => void;
  onImageDrop?: (file: File, cursorPos: number) => void;
  placeholder?: string;
}

export function MarkdownEditor({
  value,
  onChange,
  onImageInsert,
  onImageDrop,
  placeholder,
}: MarkdownEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragCounter = useRef(0);
  // Cached cursor position - updated on every selection change so it survives
  // focus loss to toolbar buttons or other UI. Toolbar actions read this
  // instead of selectionStart so the insertion always lands where the user
  // last had their caret, not at position 0 if the textarea was never focused.
  const lastSelection = useRef({ start: 0, end: 0 });

  const trackSelection = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    lastSelection.current = {
      start: textarea.selectionStart,
      end: textarea.selectionEnd,
    };
  }, []);

  const insertAtCursor = useCallback(
    (before: string, after = "", placeholder = "") => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      const start = lastSelection.current.start;
      const end = lastSelection.current.end;
      const selected = value.substring(start, end);
      const text = selected || placeholder;

      const newValue =
        value.substring(0, start) +
        before +
        text +
        after +
        value.substring(end);

      onChange(newValue);

      // Restore cursor position
      setTimeout(() => {
        textarea.focus();
        const cursorPos = start + before.length + text.length;
        textarea.setSelectionRange(cursorPos, cursorPos);
      }, 0);
    },
    [value, onChange]
  );

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (e.dataTransfer.types.includes("Files")) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current === 0) {
      setIsDragging(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    dragCounter.current = 0;

    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/") && onImageDrop) {
      const textarea = textareaRef.current;
      const pos = textarea ? textarea.selectionStart : value.length;
      onImageDrop(file, pos);
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (!onImageDrop) return;
    const item = Array.from(e.clipboardData.items).find((i) =>
      i.type.startsWith("image/")
    );
    if (!item) return;
    const file = item.getAsFile();
    if (!file) return;
    e.preventDefault();
    const textarea = textareaRef.current;
    const pos = textarea ? textarea.selectionStart : value.length;
    onImageDrop(file, pos);
  };

  const tools = [
    {
      icon: Bold,
      label: "Gras",
      action: () => insertAtCursor("**", "**", "texte"),
    },
    {
      icon: Italic,
      label: "Italique",
      action: () => insertAtCursor("*", "*", "texte"),
    },
    { type: "separator" as const },
    {
      icon: Heading2,
      label: "Titre H2",
      action: () => insertAtCursor("\n## ", "", "Titre"),
    },
    {
      icon: Heading3,
      label: "Titre H3",
      action: () => insertAtCursor("\n### ", "", "Sous-titre"),
    },
    { type: "separator" as const },
    {
      icon: Link,
      label: "Lien",
      action: () => insertAtCursor("[", "](url)", "texte du lien"),
    },
    {
      icon: Image,
      label: "Image",
      action: () => {
        if (onImageInsert) {
          onImageInsert(lastSelection.current.start);
        } else {
          insertAtCursor("![", "](url)", "description");
        }
      },
    },
    { type: "separator" as const },
    {
      icon: Code,
      label: "Code",
      action: () => insertAtCursor("\n```\n", "\n```\n", "code ici"),
    },
    {
      icon: Quote,
      label: "Citation",
      action: () => insertAtCursor("\n> ", "", "citation"),
    },
    {
      icon: List,
      label: "Liste",
      action: () => insertAtCursor("\n- ", "", "element"),
    },
  ];

  return (
    <div
      className={`border rounded-md overflow-hidden relative transition-colors ${
        isDragging ? "border-primary border-dashed bg-primary/5" : ""
      }`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Toolbar */}
      <div className="flex items-center gap-1 p-2 bg-muted/50 border-b flex-wrap">
        {tools.map((tool, i) =>
          "type" in tool && tool.type === "separator" ? (
            <Separator key={i} orientation="vertical" className="h-6 mx-1" />
          ) : (
            <Button
              key={i}
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={"action" in tool ? tool.action : undefined}
              title={"label" in tool ? tool.label : ""}
            >
              {"icon" in tool && <tool.icon className="h-4 w-4" />}
            </Button>
          )
        )}
      </div>

      {/* Editor */}
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          trackSelection();
        }}
        onSelect={trackSelection}
        onKeyUp={trackSelection}
        onMouseUp={trackSelection}
        onBlur={trackSelection}
        onPaste={handlePaste}
        placeholder={placeholder || "Écrivez votre article en Markdown..."}
        className="min-h-[400px] border-0 rounded-none resize-y focus-visible:ring-0 font-mono text-sm"
      />

      {/* Drag overlay */}
      {isDragging && (
        <div className="absolute inset-0 bg-primary/10 flex items-center justify-center pointer-events-none z-10">
          <div className="flex flex-col items-center gap-2 text-primary">
            <Upload className="h-8 w-8" />
            <p className="text-sm font-medium">Déposez l'image ici</p>
          </div>
        </div>
      )}
    </div>
  );
}
