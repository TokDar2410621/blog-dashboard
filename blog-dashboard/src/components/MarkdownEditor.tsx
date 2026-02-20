import { useRef, useCallback } from "react";
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
} from "lucide-react";

interface MarkdownEditorProps {
  value: string;
  onChange: (value: string) => void;
  onImageInsert?: () => void;
  placeholder?: string;
}

export function MarkdownEditor({
  value,
  onChange,
  onImageInsert,
  placeholder = "Ecrivez votre article en Markdown...",
}: MarkdownEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const insertAtCursor = useCallback(
    (before: string, after = "", placeholder = "") => {
      const textarea = textareaRef.current;
      if (!textarea) return;

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
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
          onImageInsert();
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
    <div className="border rounded-md overflow-hidden">
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
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="min-h-[400px] border-0 rounded-none resize-y focus-visible:ring-0 font-mono text-sm"
      />
    </div>
  );
}
