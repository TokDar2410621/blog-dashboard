import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import { Pencil } from "lucide-react";

interface MarkdownPreviewProps {
  content: string;
  onImageClick?: (src: string) => void;
}

export function MarkdownPreview({ content, onImageClick }: MarkdownPreviewProps) {
  if (!content) {
    return (
      <div className="text-muted-foreground text-center py-12">
        L'apercu apparaitra ici...
      </div>
    );
  }

  // Detect if content is HTML
  const isHtml = /<[a-z][\s\S]*>/i.test(content);

  // For pure HTML content, render directly
  if (isHtml && !content.trim().startsWith("#") && !content.trim().startsWith("!")) {
    return (
      <div
        className="prose prose-sm dark:prose-invert max-w-none"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none">
      <ReactMarkdown
        rehypePlugins={[rehypeRaw]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-2xl font-bold mt-6 mb-3">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-xl font-semibold mt-5 mb-2 border-l-4 border-primary pl-3">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>
          ),
          p: ({ children }) => (
            <p className="mb-3 leading-relaxed">{children}</p>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline"
            >
              {children}
            </a>
          ),
          img: ({ src, alt }) =>
            onImageClick ? (
              <span
                className="relative group inline-block my-4 cursor-pointer"
                onClick={() => onImageClick(src || "")}
              >
                <img
                  src={src}
                  alt={alt}
                  className="rounded-md max-w-full"
                  loading="lazy"
                />
                <span className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity rounded-md flex items-center justify-center">
                  <span className="bg-white/90 text-black text-xs font-medium px-3 py-1.5 rounded-full flex items-center gap-1.5">
                    <Pencil className="h-3 w-3" />
                    Changer l'image
                  </span>
                </span>
              </span>
            ) : (
              <img
                src={src}
                alt={alt}
                className="rounded-md max-w-full my-4"
                loading="lazy"
              />
            ),
          code: ({ className, children }) => {
            const isBlock = className?.includes("language-");
            if (isBlock) {
              return (
                <pre className="bg-muted p-4 rounded-md overflow-x-auto my-4">
                  <code className="text-sm">{children}</code>
                </pre>
              );
            }
            return (
              <code className="bg-muted px-1.5 py-0.5 rounded text-sm">
                {children}
              </code>
            );
          },
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-primary/30 pl-4 italic my-4 text-muted-foreground">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
