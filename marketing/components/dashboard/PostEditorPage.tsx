"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { usePost, useCreatePost, useUpdatePost, useCategories, useSites } from "@/hooks/useDashboard";
import { searchPexels, searchSerperImages, generateCoverImage, uploadInlineImage } from "@/lib/api-client";
import { markdownTemplates, visualTemplates } from "@/lib/templates";
import TurndownService from "turndown";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { ImageInsertDialog } from "@/components/ImageInsertDialog";
import { SEOPreview } from "@/components/SEOPreview";
import { SEOAnalyzer } from "@/components/SEOAnalyzer";
import { ReadabilityCard } from "@/components/ReadabilityCard";
import { LexiconCard } from "@/components/LexiconCard";
import { PlagiarismCard } from "@/components/PlagiarismCard";
import { ScorePanel } from "@/components/editor/ScorePanel";
import {
  buildTermUsage,
  computeCompositeScore,
  type TermSeed,
} from "@/components/editor/contentScore";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft, Save, Send, Loader2, Search, Settings2, Star,
  ImageIcon, Sparkles, Check, PenLine, Eye, CalendarClock, Wand2, Globe, Plus, X,
  ThumbsUp, ThumbsDown,
  Languages,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  POST_STATUS,
  QUERY_PARAM,
  TEMPLATE_TYPE,
  type PostStatus,
} from "@/lib/constants";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";

function normalizePostStatus(
  value: string | undefined,
  fallback: PostStatus = POST_STATUS.PUBLISHED
): PostStatus {
  if (
    value === POST_STATUS.DRAFT ||
    value === POST_STATUS.PUBLISHED ||
    value === POST_STATUS.SCHEDULED
  ) {
    return value;
  }
  return fallback;
}

export function PostEditorPage({ slug }: { slug?: string }) {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const searchParams = useSearchParams();
  const router = useRouter();
  const isEditing = !!slug;
  const base = `/dashboard/${siteId}`;

  const { data: existingPost, isLoading: loadingPost } = usePost(slug || "");
  const { data: categories = [] } = useCategories();
  const { data: sites = [] } = useSites();
  const currentSite = sites.find((s: { id: number }) => s.id === Number(siteId));
  const createPost = useCreatePost();
  const updatePost = useUpdatePost();

  const [title, setTitle] = useState("");
  const [postSlug, setPostSlug] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [coverImage, setCoverImage] = useState("");
  const [status, setStatus] = useState<PostStatus>(POST_STATUS.DRAFT);
  const [featured, setFeatured] = useState(false);
  const [scheduledAt, setScheduledAt] = useState("");
  const [autoSlug, setAutoSlug] = useState(true);
  const [view, setView] = useState<"edit" | "seo" | "settings">("edit");
  const [mobilePanel, setMobilePanel] = useState<"edit" | "preview" | "score">("edit");
  const [language, setLanguage] = useState<string>("fr");
  const [translationGroup, setTranslationGroup] = useState<string>("");
  const [translating, setTranslating] = useState(false);

  // Cover image library state
  const [pexelsQuery, setPexelsQuery] = useState("");
  const [pexelsResults, setPexelsResults] = useState<{ id: number; url: string; thumb: string; alt: string; photographer: string }[]>([]);
  const [pexelsLoading, setPexelsLoading] = useState(false);
  const [aiPrompt, setAiPrompt] = useState("");
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiPreview, setAiPreview] = useState("");
  const [aiImageUrl, setAiImageUrl] = useState("");
  // RAG feedback loop: captured from /generate-inline response when AI
  // produced the article, then passed to /sites/<id>/posts/ on save so the
  // chunk IDs are persisted on HostedPost.memory_chunks_used. After publish,
  // the user can rate the article and feedback flows back to those chunks.
  const [memoryChunksUsed, setMemoryChunksUsed] = useState<number[]>([]);
  const [feedbackRating, setFeedbackRating] = useState<number>(0);
  const [feedbackPending, setFeedbackPending] = useState(false);
  const [imageTab, setImageTab] = useState<"pexels" | "serper" | "ai">("pexels");
  const [serperQuery, setSerperQuery] = useState("");
  const [serperResults, setSerperResults] = useState<{ id: number; url: string; thumb: string; alt: string; photographer: string }[]>([]);
  const [serperLoading, setSerperLoading] = useState(false);

  // Inline image insert dialog
  const [imageDialogOpen, setImageDialogOpen] = useState(false);
  const cursorPosRef = useRef(0);
  const replacingImageRef = useRef<string | null>(null);

  // ----- Content Score (right rail, Surfer/Clearscope-style) ---------------
  // Debounce the raw editor inputs that feed the score so we don't recompute
  // on every keystroke. 600ms matches the brief.
  const [debouncedScoreInputs, setDebouncedScoreInputs] = useState({
    title: "",
    excerpt: "",
    content: "",
    slug: "",
    coverImage: "",
    tagsInput: "",
    language: "fr",
  });
  useEffect(() => {
    const handle = setTimeout(() => {
      setDebouncedScoreInputs({
        title,
        excerpt,
        content,
        slug: postSlug,
        coverImage,
        tagsInput,
        language,
      });
    }, 600);
    return () => clearTimeout(handle);
  }, [title, excerpt, content, postSlug, coverImage, tagsInput, language]);

  // Active highlighted term in the inline editor (clicked from TermTracker).
  const [activeTerm, setActiveTerm] = useState<string | null>(null);

  // Term seeds: derived from tags input (primary = first tag, importance
  // descending). TODO(v2): when gridar_get_brief returns recommended_terms,
  // merge them in with their volume/relevance scores.
  const termSeeds: TermSeed[] = useMemo(() => {
    const tags = debouncedScoreInputs.tagsInput
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    return tags.slice(0, 10).map((term, idx) => ({
      term,
      // Linear decay so the first tag stays the most important.
      importance: 1 - idx * 0.08,
    }));
  }, [debouncedScoreInputs.tagsInput]);

  const primaryKeyword = termSeeds[0]?.term ?? "";
  const secondaryKeywords = termSeeds.slice(1).map((s) => s.term);

  // Composite score - memoized off the debounced inputs.
  const composite = useMemo(() => {
    return computeCompositeScore({
      title: debouncedScoreInputs.title,
      excerpt: debouncedScoreInputs.excerpt,
      content: debouncedScoreInputs.content,
      slug: debouncedScoreInputs.slug,
      coverImage: debouncedScoreInputs.coverImage,
      keyword: primaryKeyword,
      secondaryKeywords,
      language: debouncedScoreInputs.language,
    });
  }, [debouncedScoreInputs, primaryKeyword, secondaryKeywords]);

  const termUsages = useMemo(
    () => buildTermUsage(debouncedScoreInputs.content, termSeeds),
    [debouncedScoreInputs.content, termSeeds],
  );

  // Score trend: last 7 scores in sessionStorage keyed by slug.
  const trendKey = postSlug ? `gridar.score.trend.${postSlug}` : null;
  const [trend, setTrend] = useState<number[]>([]);
  useEffect(() => {
    if (!trendKey) return;
    try {
      const raw = sessionStorage.getItem(trendKey);
      if (raw) setTrend(JSON.parse(raw));
      else setTrend([]);
    } catch {
      setTrend([]);
    }
  }, [trendKey]);
  useEffect(() => {
    if (!trendKey) return;
    if (composite.total <= 0) return;
    // Only append when score actually changes - avoids polluting trend on
    // every focus change.
    setTrend((prev) => {
      if (prev.length > 0 && prev[prev.length - 1] === composite.total) {
        return prev;
      }
      const next = [...prev, composite.total].slice(-7);
      try {
        sessionStorage.setItem(trendKey, JSON.stringify(next));
      } catch {
        /* ignore quota errors */
      }
      return next;
    });
  }, [composite.total, trendKey]);

  const handleImageInsert = (markdown: string) => {
    if (replacingImageRef.current) {
      // Replace mode: swap old image URL with new one
      const oldSrc = replacingImageRef.current;
      // Match ![any alt](oldSrc) and replace with new markdown
      const escaped = oldSrc.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const regex = new RegExp(`!\\[[^\\]]*\\]\\(${escaped}\\)`);
      setContent(prev => prev.replace(regex, markdown.trim()));
      replacingImageRef.current = null;
    } else {
      // Insert mode: add at cursor position
      const pos = cursorPosRef.current;
      const newContent =
        content.substring(0, pos) + markdown + content.substring(pos);
      setContent(newContent);
    }
  };

  const [imageDialogQuery, setImageDialogQuery] = useState("");

  const handlePreviewImageClick = (src: string) => {
    replacingImageRef.current = src;
    // Extract alt text from markdown: ![alt text](src)
    const escaped = src.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = content.match(new RegExp(`!\\[([^\\]]*)\\]\\(${escaped}\\)`));
    setImageDialogQuery(match?.[1] || "");
    setImageDialogOpen(true);
  };

  const handleImageDrop = async (file: File, cursorPos: number) => {
    const placeholder = `\n![Uploading...]()\n`;
    const before = content.substring(0, cursorPos);
    const after = content.substring(cursorPos);
    setContent(before + placeholder + after);

    try {
      const data = await uploadInlineImage(file);
      const cleanName = file.name.replace(/\.[^.]+$/, "");
      setContent(prev => prev.replace(placeholder, `\n![${cleanName}](${data.url})\n`));
      toast.success("Image uploadée!");
    } catch {
      setContent(prev => prev.replace(placeholder, ""));
      toast.error("Erreur upload image");
    }
  };

  const handlePexelsSearch = async () => {
    if (!pexelsQuery.trim()) return;
    setPexelsLoading(true);
    try {
      const data = await searchPexels(pexelsQuery);
      setPexelsResults(data.photos || []);
    } catch (err) {
      toast.error("Erreur Pexels: " + (err instanceof Error ? err.message : "Inconnue"));
    } finally {
      setPexelsLoading(false);
    }
  };

  const handleSerperSearch = async () => {
    if (!serperQuery.trim()) return;
    setSerperLoading(true);
    try {
      const data = await searchSerperImages(serperQuery);
      setSerperResults(data.photos || []);
    } catch (err) {
      toast.error("Erreur Serper: " + (err instanceof Error ? err.message : "Inconnue"));
    } finally {
      setSerperLoading(false);
    }
  };

  // AI Generate dialog
  const [aiDialogOpen, setAiDialogOpen] = useState(false);
  const [aiTopic, setAiTopic] = useState("");
  const [aiUrls, setAiUrls] = useState<string[]>([""]);
  const [aiType, setAiType] = useState("news");
  const [aiLength, setAiLength] = useState("medium");
  const [aiKeywords, setAiKeywords] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  const handleAiGenerateArticle = async () => {
    if (!aiTopic && !title) {
      toast.error("Ajoutez un sujet ou un titre");
      return;
    }
    setAiLoading(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const urls = aiUrls.filter((u) => u.trim());
      const res = await authFetch(`/sites/${siteId}/generate-inline/`, {
        method: "POST",
        body: JSON.stringify({
          topic: aiTopic || title,
          title: title || undefined,
          type: aiType,
          length: aiLength,
          keywords: aiKeywords || undefined,
          context_urls: urls.length > 0 ? urls : undefined,
          language,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur génération");
      }
      const data = await res.json();
      // Fill the editor with generated content
      if (data.title && !title) setTitle(data.title);
      if (data.excerpt) setExcerpt(data.excerpt);
      if (data.content) setContent(data.content);
      if (data.tags) setTagsInput(data.tags.join(", "));
      if (data.cover_image) setCoverImage(data.cover_image);
      if (data.slug && !isEditing) setPostSlug(data.slug);
      if (Array.isArray(data.memory_chunks_used)) {
        setMemoryChunksUsed(data.memory_chunks_used);
      }
      setAiDialogOpen(false);
      toast.success("Article généré !");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setAiLoading(false);
    }
  };

  const handleTranslate = async (targetLang: string) => {
    if (!title || !content) {
      toast.error("Ajoutez un titre et du contenu pour traduire");
      return;
    }
    if (targetLang === language) return;
    setTranslating(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch("/translate/", {
        method: "POST",
        body: JSON.stringify({
          title,
          excerpt,
          content,
          source_language: language,
          target_language: targetLang,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur traduction");
      }
      const data = await res.json();
      // Create a new post with same translation_group
      const groupId = translationGroup || crypto.randomUUID();
      if (!translationGroup) setTranslationGroup(groupId);

      const { authFetch: af } = await import("@/lib/api-client");
      // Mirror the source article's status so the translation is immediately
      // available on the public frontend when the user switches language.
      // (Drafts get translated as drafts, scheduled stay scheduled, etc.)
      const createRes = await af(`/sites/${siteId}/posts/`, {
        method: "POST",
        body: JSON.stringify({
          title: data.title,
          slug: data.slug,
          excerpt: data.excerpt,
          content: data.content,
          category,
          tags_input: tagsInput.split(",").map((t: string) => t.trim()).filter(Boolean),
          cover_image: coverImage,
          status,
          featured,
          language: targetLang,
          translation_group: groupId,
        }),
      });
      if (!createRes.ok) {
        const err = await createRes.json().catch(() => ({}));
        throw new Error(err.detail || err.error || "Erreur création traduction");
      }
      const created = await createRes.json();

      // Also patch the current post to link it to the group
      if (isEditing && !translationGroup) {
        await updatePost.mutateAsync({
          slug: slug!,
          data: { translation_group: groupId },
        });
      }

      toast.success(`Traduction ${targetLang.toUpperCase()} créée !`);
      router.push(`${base}/articles/${created.slug}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setTranslating(false);
    }
  };

  const [tagsGenerating, setTagsGenerating] = useState(false);
  const handleGenerateTags = async () => {
    if (!title && !content) {
      toast.error("Ajoutez un titre ou du contenu pour générer des tags");
      return;
    }
    setTagsGenerating(true);
    try {
      const res = await import("@/lib/api-client").then(m =>
        m.authFetch("/generate-tags/", {
          method: "POST",
          body: JSON.stringify({ title, content: content.slice(0, 2000), excerpt }),
        })
      );
      if (!res.ok) throw new Error("Erreur génération");
      const data = await res.json();
      const tags = Array.isArray(data.tags) ? data.tags : [];
      if (tags.length === 0) {
        toast.info("Aucun tag généré");
        return;
      }
      setTagsInput(tags.join(", "));
      toast.success(`${tags.length} tags générés`);
    } catch (err) {
      toast.error("Erreur: " + (err instanceof Error ? err.message : "Inconnue"));
    } finally {
      setTagsGenerating(false);
    }
  };

  const handleAiGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setAiGenerating(true);
    setAiPreview("");
    setAiImageUrl("");
    try {
      const data = await generateCoverImage(aiPrompt);
      const byteCharacters = atob(data.image);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: data.mime_type });
      setAiPreview(URL.createObjectURL(blob));
      setAiImageUrl(data.image_url);
    } catch (err) {
      toast.error("Erreur génération: " + (err instanceof Error ? err.message : "Inconnue"));
    } finally {
      setAiGenerating(false);
    }
  };

  // HTML → Markdown converter
  const turndown = useMemo(() => {
    const td = new TurndownService({
      headingStyle: "atx",
      codeBlockStyle: "fenced",
      bulletListMarker: "-",
    });
    // Keep figure/figcaption as images
    td.addRule("figure", {
      filter: "figure",
      replacement: (_content, node) => {
        const img = (node as HTMLElement).querySelector("img");
        const caption = (node as HTMLElement).querySelector("figcaption");
        if (img) {
          const alt = caption?.textContent || img.getAttribute("alt") || "";
          const src = img.getAttribute("src") || "";
          return `\n![${alt}](${src})\n`;
        }
        return _content;
      },
    });
    return td;
  }, []);

  function htmlToMarkdown(html: string): string {
    // Check if content is HTML (has tags beyond simple markdown inline)
    const isHtml = /<(article|div|section|figure|p|h[1-6]|ul|ol|table)\b/i.test(html);
    if (!isHtml) return html;
    return turndown.turndown(html);
  }

  useEffect(() => {
    if (existingPost && isEditing) {
      setTitle(existingPost.title || "");
      setPostSlug(existingPost.slug || "");
      setExcerpt(existingPost.excerpt || "");
      setContent(htmlToMarkdown(existingPost.content || ""));
      setCategory(existingPost.category || "");
      setTagsInput((existingPost.tags || []).join(", "));
      setCoverImage(existingPost.cover_image || "");
      setStatus(normalizePostStatus(existingPost.status));
      setFeatured(existingPost.featured || false);
      setLanguage((existingPost as { language?: string }).language || "fr");
      setTranslationGroup((existingPost as { translation_group?: string }).translation_group || "");
      setMemoryChunksUsed(
        (existingPost as { memory_chunks_used?: number[] }).memory_chunks_used || []
      );
      setFeedbackRating(
        (existingPost as { feedback_rating?: number }).feedback_rating || 0
      );
      if (existingPost.scheduled_at) {
        setScheduledAt(new Date(existingPost.scheduled_at).toISOString().slice(0, 16));
      }
      setAutoSlug(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingPost, isEditing]);

  useEffect(() => {
    if (autoSlug && !isEditing) {
      // Client-side slug preview only - backend generates the canonical slug
      const preview = title
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/(^-|-$)/g, "");
      setPostSlug(preview);
    }
  }, [title, autoSlug, isEditing]);

  // Template pre-fill from query params
  useEffect(() => {
    if (isEditing) return;
    const tplType = searchParams?.get(QUERY_PARAM.TPL_TYPE);
    const tplId = searchParams?.get(QUERY_PARAM.TPL_ID);
    if (!tplType || !tplId) return;

    if (tplType === TEMPLATE_TYPE.MARKDOWN) {
      const tpl = markdownTemplates.find((t) => t.id === tplId);
      if (tpl) {
        // Dashboard UI is FR (the SPA picked content_fr/content_en from i18n).
        setContent(tpl.content_fr);
      }
    } else if (tplType === TEMPLATE_TYPE.VISUAL) {
      const tpl = visualTemplates.find((t) => t.id === tplId);
      if (tpl) {
        // Visual template sets a CSS class - stored in content metadata
        setContent(`<!-- template:${tpl.cssClass} -->\n\n`);
      }
    }
  }, [searchParams, isEditing]);

  const handleSave = async (publishStatus?: string) => {
    const finalStatus = publishStatus || status;
    const data: Record<string, unknown> = {
      title,
      slug: postSlug,
      excerpt,
      content,
      category,
      tags_input: tagsInput.split(",").map((t: string) => t.trim()).filter(Boolean),
      cover_image: coverImage,
      status: finalStatus,
      featured,
      language,
    };
    if (translationGroup) data.translation_group = translationGroup;
    if (memoryChunksUsed.length > 0) data.memory_chunks_used = memoryChunksUsed;
    if (finalStatus === POST_STATUS.SCHEDULED && scheduledAt) {
      data.scheduled_at = new Date(scheduledAt).toISOString();
    }

    try {
      if (isEditing) {
        await updatePost.mutateAsync({ slug: slug!, data });
        toast.success("Article mis à jour!");
      } else {
        await createPost.mutateAsync(data);
        toast.success("Article créé!");
        router.push(`${base}/articles`);
      }
    } catch (err) {
      toast.error(
        "Erreur: " + (err instanceof Error ? err.message : "Inconnue")
      );
    }
  };

  const isSaving = createPost.isPending || updatePost.isPending;

  // RAG feedback loop: bump SiteMemory.feedback_score on the chunks that
  // contributed to this article. Only meaningful for AI-generated posts that
  // have already been saved (we need a slug to address the post).
  const handleFeedback = async (newRating: 1 | -1) => {
    if (!isEditing || !slug) {
      toast.error("Sauvegarde l'article avant de noter.");
      return;
    }
    if (memoryChunksUsed.length === 0) {
      toast.info("Cet article n'a pas ete genere avec la memoire RAG.");
      return;
    }
    // Toggle off if clicking the same rating twice.
    const rating = feedbackRating === newRating ? 0 : newRating;
    setFeedbackPending(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch(
        `/sites/${siteId}/posts/${slug}/feedback/`,
        { method: "POST", body: JSON.stringify({ rating }) }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur feedback");
      }
      setFeedbackRating(rating);
      toast.success(
        rating === 1
          ? "Bon article. Les chunks utilises sont boostes pour les prochaines generations."
          : rating === -1
          ? "Mauvais article. Les chunks utilises sont penalises."
          : "Feedback annule."
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setFeedbackPending(false);
    }
  };

  if (isEditing && loadingPost) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="h-[calc(100dvh-3rem)] flex flex-col">
      <PageBreadcrumb
        trail={[
          { label: "Articles", href: `${base}/articles` },
          {
            label: title
              ? title.length > 40
                ? `${title.slice(0, 40)}...`
                : title
              : isEditing
              ? "Modifier l'article"
              : "Nouvel article",
          },
        ]}
      />
      {/* Sticky Header */}
      <div className="flex flex-wrap items-center justify-between gap-y-2 pb-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => router.push(`${base}/articles`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-lg font-bold">
              {isEditing ? "Modifier l'article" : "Nouvel article"}
            </h1>
            {postSlug && (
              <p className="text-xs text-muted-foreground">/{postSlug}</p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isEditing && memoryChunksUsed.length > 0 && (
            <div className="flex items-center gap-1 border rounded-md px-1.5 py-0.5 mr-1">
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground mr-1">
                Article IA
              </span>
              <Button
                type="button"
                variant={feedbackRating === 1 ? "default" : "ghost"}
                size="icon"
                className="h-7 w-7"
                disabled={feedbackPending}
                onClick={() => handleFeedback(1)}
                title="Bon article - booste les chunks RAG utilises"
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </Button>
              <Button
                type="button"
                variant={feedbackRating === -1 ? "destructive" : "ghost"}
                size="icon"
                className="h-7 w-7"
                disabled={feedbackPending}
                onClick={() => handleFeedback(-1)}
                title="Mauvais article - penalise les chunks RAG utilises"
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setAiDialogOpen(true)}
          >
            <Wand2 className="h-4 w-4 mr-1.5" />
            Générer avec IA
          </Button>
          {isEditing && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" disabled={translating}>
                  {translating ? (
                    <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                  ) : (
                    <Languages className="h-4 w-4 mr-1.5" />
                  )}
                  Traduire
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {(["fr", "en", "es"] as const)
                  .filter((l) => l !== language)
                  .map((l) => (
                    <DropdownMenuItem key={l} onClick={() => handleTranslate(l)}>
                      <Languages className="h-4 w-4 mr-2" />
                      Traduire en {l.toUpperCase()}
                    </DropdownMenuItem>
                  ))}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleSave(POST_STATUS.DRAFT)}
            disabled={isSaving}
          >
            <Save className="h-4 w-4 mr-1.5" />
            Brouillon
          </Button>
          <Button
            size="sm"
            onClick={() => handleSave(POST_STATUS.PUBLISHED)}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <Send className="h-4 w-4 mr-1.5" />
            )}
            Publier
          </Button>
        </div>
      </div>

      {/* View selector */}
      <div className="flex items-center gap-1.5 pt-3 pb-2 shrink-0">
        <Button
          variant={view === "edit" ? "default" : "ghost"}
          size="sm"
          onClick={() => setView("edit")}
          className="h-7 text-xs"
        >
          <PenLine className="h-3.5 w-3.5 mr-1" />
          Éditeur
        </Button>
        <Button
          variant={view === "seo" ? "default" : "ghost"}
          size="sm"
          onClick={() => setView("seo")}
          className="h-7 text-xs"
        >
          <Search className="h-3.5 w-3.5 mr-1" />
          SEO
        </Button>
        <Button
          variant={view === "settings" ? "default" : "ghost"}
          size="sm"
          onClick={() => setView("settings")}
          className="h-7 text-xs"
        >
          <Settings2 className="h-3.5 w-3.5 mr-1" />
          Paramètres
        </Button>
      </div>

      {/* Main content */}
      <div className="flex-1 min-h-0">
        {/* Split view: Editor + Preview */}
        {view === "edit" && (
          <div className="h-full flex flex-col">
            <div className="flex md:hidden items-center gap-1.5 pb-2 shrink-0">
              <Button
                variant={mobilePanel === "edit" ? "default" : "ghost"}
                size="sm"
                onClick={() => setMobilePanel("edit")}
                className="h-7 text-xs"
              >
                <PenLine className="h-3.5 w-3.5 mr-1" />
                Éditeur
              </Button>
              <Button
                variant={mobilePanel === "preview" ? "default" : "ghost"}
                size="sm"
                onClick={() => setMobilePanel("preview")}
                className="h-7 text-xs"
              >
                <Eye className="h-3.5 w-3.5 mr-1" />
                Aperçu en direct
              </Button>
              <Button
                variant={mobilePanel === "score" ? "default" : "ghost"}
                size="sm"
                onClick={() => setMobilePanel("score")}
                className="h-7 text-xs"
              >
                <Star className="h-3.5 w-3.5 mr-1" />
                Score
              </Button>
            </div>
          <ResizablePanelGroup orientation="horizontal" className="flex-1 min-h-0 rounded-lg border">
            {/* Left panel: editor */}
            <ResizablePanel defaultSize={40} minSize={25} className={mobilePanel === "edit" ? "" : "hidden md:block"}>
              <div
                className="h-full flex flex-col overflow-y-auto"
                data-active-term={activeTerm || undefined}
              >
                <div className="p-4 space-y-3 shrink-0">
                  <Input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Titre de l'article..."
                    className="text-xl font-bold h-12 border-0 px-0 focus-visible:ring-0 bg-transparent placeholder:text-muted-foreground/50"
                  />
                  <Textarea
                    value={excerpt}
                    onChange={(e) => setExcerpt(e.target.value)}
                    placeholder="Extrait / meta description (160 car.)..."
                    rows={2}
                    className="resize-none border-0 px-0 focus-visible:ring-0 bg-transparent text-muted-foreground placeholder:text-muted-foreground/40 text-sm"
                  />
                </div>
                <div className="flex-1 px-4 pb-4">
                  <MarkdownEditor
                    value={content}
                    onChange={setContent}
                    onImageInsert={(pos) => {
                      cursorPosRef.current = pos;
                      setImageDialogOpen(true);
                    }}
                    onImageDrop={handleImageDrop}
                  />
                </div>
              </div>
            </ResizablePanel>

            <ResizableHandle withHandle className="hidden md:flex" />

            {/* Center panel: live preview */}
            <ResizablePanel defaultSize={35} minSize={20} className={mobilePanel === "preview" ? "" : "hidden md:block"}>
              <div className="h-full overflow-y-auto p-6">
                <div className="flex items-center gap-2 mb-4 text-xs text-muted-foreground">
                  <Eye className="h-3.5 w-3.5" />
                  Aperçu en direct
                </div>
                {coverImage && (
                  <img
                    src={coverImage}
                    alt="Cover"
                    className="w-full h-48 object-cover rounded-lg mb-6"
                  />
                )}
                {title && (
                  <h1 className="text-2xl font-bold mb-3">{title}</h1>
                )}
                {excerpt && (
                  <p className="text-muted-foreground mb-6 italic">
                    {excerpt}
                  </p>
                )}
                <MarkdownPreview content={content} onImageClick={handlePreviewImageClick} />
              </div>
            </ResizablePanel>

            <ResizableHandle withHandle className="hidden md:flex" />

            {/* Right panel: Content Score gauge + term tracker (sticky rail) */}
            <ResizablePanel defaultSize={25} minSize={18} className={mobilePanel === "score" ? "" : "hidden md:block"}>
              <ScorePanel
                title={debouncedScoreInputs.title}
                excerpt={debouncedScoreInputs.excerpt}
                content={debouncedScoreInputs.content}
                slug={debouncedScoreInputs.slug}
                coverImage={debouncedScoreInputs.coverImage}
                keyword={primaryKeyword}
                secondaryKeywords={secondaryKeywords}
                language={debouncedScoreInputs.language}
                terms={termUsages}
                trend={trend}
                precomputed={composite}
                activeTerm={activeTerm}
                onTermClick={(term) =>
                  setActiveTerm((prev) => (prev === term ? null : term))
                }
              />
            </ResizablePanel>
          </ResizablePanelGroup>
          </div>
        )}

        {/* SEO view */}
        {view === "seo" && (
          <div className="h-full overflow-y-auto pt-4">
            <div className="max-w-2xl">
              <Tabs defaultValue="audit">
                <TabsList className="w-full">
                  <TabsTrigger value="audit" className="flex-1">Audit</TabsTrigger>
                  <TabsTrigger value="readability" className="flex-1">Lisibilite</TabsTrigger>
                  <TabsTrigger value="preview" className="flex-1">Apercu Google</TabsTrigger>
                </TabsList>

                <TabsContent value="audit" className="mt-4">
                  <SEOAnalyzer
                    title={title}
                    excerpt={excerpt}
                    content={content}
                    slug={postSlug}
                    coverImage={coverImage}
                    keyword={tagsInput.split(",")[0]?.trim() || ""}
                    siteId={siteId ? Number(siteId) : undefined}
                    currentSlug={postSlug}
                    articleUrl={
                      currentSite?.domain && postSlug
                        ? `https://${currentSite.domain.replace(/^https?:\/\//, "").replace(/\/$/, "")}/blog/${postSlug}`
                        : undefined
                    }
                    author={currentSite?.name || "Admin"}
                    publishedAt={new Date().toISOString()}
                    siteDomain={currentSite?.domain || ""}
                    language={language}
                    onApplyFix={(fixes) => {
                      if (fixes.title) setTitle(fixes.title);
                      if (fixes.excerpt) setExcerpt(fixes.excerpt);
                      if (fixes.content) setContent(fixes.content);
                    }}
                  />
                </TabsContent>

                <TabsContent value="readability" className="mt-4 space-y-6">
                  <ReadabilityCard content={content} language={language} />
                  <LexiconCard content={content} language={language} />
                  <PlagiarismCard title={title} content={content} language={language} />
                </TabsContent>

                <TabsContent value="preview" className="mt-4">
                  <SEOPreview
                    title={title}
                    slug={postSlug}
                    description={excerpt}
                    coverImage={coverImage}
                    siteUrl={currentSite?.domain || ""}
                  />
                </TabsContent>
              </Tabs>
            </div>
          </div>
        )}

        {/* Settings view */}
        {view === "settings" && (
          <div className="h-full overflow-y-auto pt-4">
            <div className="max-w-3xl space-y-4">
              {/* Row 1: Publication + Slug/Tags */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Publication */}
                <Card>
                  <CardHeader className="py-3 px-4">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Settings2 className="h-4 w-4" />
                      Publication
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">Statut</Label>
                      <Select
                        value={status}
                        onValueChange={(v) => setStatus(v as PostStatus)}
                      >
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={POST_STATUS.DRAFT}>Brouillon</SelectItem>
                          <SelectItem value={POST_STATUS.PUBLISHED}>Publié</SelectItem>
                          <SelectItem value={POST_STATUS.SCHEDULED}>Planifié</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs flex items-center gap-1.5">
                        <Languages className="h-3.5 w-3.5" />
                        Langue
                      </Label>
                      <Select value={language} onValueChange={setLanguage}>
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(() => {
                            const all = [
                              { code: "fr", label: "Français" },
                              { code: "en", label: "English" },
                              { code: "es", label: "Español" },
                            ];
                            const allowed =
                              currentSite?.available_languages && currentSite.available_languages.length > 0
                                ? all.filter((l) => currentSite.available_languages!.includes(l.code))
                                : all;
                            return allowed.map((l) => (
                              <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>
                            ));
                          })()}
                        </SelectContent>
                      </Select>
                    </div>
                    {status === POST_STATUS.SCHEDULED && (
                      <div className="space-y-1.5">
                        <Label className="text-xs flex items-center gap-1.5">
                          <CalendarClock className="h-3.5 w-3.5" />
                          Date de publication
                        </Label>
                        <Input
                          type="datetime-local"
                          value={scheduledAt}
                          onChange={(e) => setScheduledAt(e.target.value)}
                          className="h-8 text-sm"
                          min={new Date().toISOString().slice(0, 16)}
                        />
                      </div>
                    )}
                    <div className="space-y-1.5">
                      <Label className="text-xs">Catégorie</Label>
                      <Select value={category} onValueChange={setCategory}>
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue placeholder="Choisir..." />
                        </SelectTrigger>
                        <SelectContent>
                          {categories.map(
                            (cat: { slug: string; name: string }) => (
                              <SelectItem key={cat.slug} value={cat.name}>
                                {cat.name}
                              </SelectItem>
                            )
                          )}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between">
                      <Label className="text-xs flex items-center gap-1.5">
                        <Star className="h-3.5 w-3.5" />
                        En vedette
                      </Label>
                      <Switch checked={featured} onCheckedChange={setFeatured} />
                    </div>
                  </CardContent>
                </Card>

                <div className="space-y-4">
                  {/* Slug */}
                  <Card>
                    <CardContent className="p-4 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs">Slug</Label>
                        {!isEditing && (
                          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                            <Switch
                              checked={autoSlug}
                              onCheckedChange={setAutoSlug}
                              className="scale-75"
                            />
                            Auto
                          </label>
                        )}
                      </div>
                      <Input
                        value={postSlug}
                        onChange={(e) => {
                          setAutoSlug(false);
                          setPostSlug(e.target.value);
                        }}
                        placeholder="titre-de-larticle"
                        className="h-8 text-sm font-mono"
                      />
                    </CardContent>
                  </Card>

                  {/* Tags */}
                  <Card>
                    <CardContent className="p-4 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs">Tags</Label>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-6 text-xs gap-1"
                          onClick={handleGenerateTags}
                          disabled={tagsGenerating}
                        >
                          {tagsGenerating ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Sparkles className="h-3 w-3" />
                          )}
                          Générer
                        </Button>
                      </div>
                      <Input
                        value={tagsInput}
                        onChange={(e) => setTagsInput(e.target.value)}
                        placeholder="React, Django, IA..."
                        className="h-8 text-sm"
                      />
                      <p className="text-xs text-muted-foreground">Séparés par virgule</p>
                    </CardContent>
                  </Card>
                </div>
              </div>

              {/* Row 2: Image de couverture */}
              <Card>
                <CardHeader className="py-3 px-4">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <ImageIcon className="h-4 w-4" />
                    Image de couverture
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4 space-y-4">
                  <div className="flex gap-4 items-start">
                    <div className="flex-1 space-y-2">
                      <Input
                        value={coverImage}
                        onChange={(e) => setCoverImage(e.target.value)}
                        placeholder="URL de l'image..."
                        className="h-8 text-sm"
                      />
                    </div>
                    {coverImage && (
                      <img
                        src={coverImage}
                        alt="Cover"
                        className="w-32 h-20 object-cover rounded-md shrink-0"
                      />
                    )}
                  </div>

                  <div className="border-t pt-4">
                    <div className="flex flex-wrap gap-2 mb-3">
                      <Button
                        type="button"
                        variant={imageTab === "pexels" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setImageTab("pexels")}
                      >
                        <Search className="h-3.5 w-3.5 mr-1.5" />
                        Pexels
                      </Button>
                      <Button
                        type="button"
                        variant={imageTab === "serper" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setImageTab("serper")}
                      >
                        <Search className="h-3.5 w-3.5 mr-1.5" />
                        Google Images
                      </Button>
                      <Button
                        type="button"
                        variant={imageTab === "ai" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setImageTab("ai")}
                      >
                        <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                        Générer (IA)
                      </Button>
                    </div>

                    {/* Pexels Search */}
                    {imageTab === "pexels" && (
                      <div className="space-y-3">
                        <div className="flex gap-2">
                          <Input
                            value={pexelsQuery}
                            onChange={(e) => setPexelsQuery(e.target.value)}
                            placeholder="Rechercher sur Pexels..."
                            className="h-8 text-sm"
                            onKeyDown={(e) => e.key === "Enter" && handlePexelsSearch()}
                          />
                          <Button
                            type="button"
                            size="sm"
                            onClick={handlePexelsSearch}
                            disabled={pexelsLoading}
                          >
                            {pexelsLoading ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Search className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                        {pexelsResults.length > 0 && (
                          <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
                            {pexelsResults.map((photo) => (
                              <button
                                key={photo.id}
                                type="button"
                                className={`relative group rounded-md overflow-hidden border-2 transition-all ${
                                  coverImage === photo.url
                                    ? "border-primary ring-2 ring-primary/30"
                                    : "border-transparent hover:border-primary/50"
                                }`}
                                onClick={() => setCoverImage(photo.url)}
                              >
                                <img
                                  src={photo.thumb}
                                  alt={photo.alt}
                                  className="w-full h-20 object-cover"
                                />
                                {coverImage === photo.url && (
                                  <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                                    <Check className="h-5 w-5 text-primary-foreground drop-shadow" />
                                  </div>
                                )}
                                <div className="absolute bottom-0 inset-x-0 bg-black/60 text-white text-[10px] px-1 py-0.5 truncate opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                                  {photo.photographer}
                                </div>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Serper (Google Images) Search */}
                    {imageTab === "serper" && (
                      <div className="space-y-3">
                        <div className="flex gap-2">
                          <Input
                            value={serperQuery}
                            onChange={(e) => setSerperQuery(e.target.value)}
                            placeholder="Rechercher sur Google Images..."
                            className="h-8 text-sm"
                            onKeyDown={(e) => e.key === "Enter" && handleSerperSearch()}
                          />
                          <Button
                            type="button"
                            size="sm"
                            onClick={handleSerperSearch}
                            disabled={serperLoading}
                          >
                            {serperLoading ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Search className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                        {serperResults.length > 0 && (
                          <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
                            {serperResults.map((photo) => (
                              <button
                                key={photo.id}
                                type="button"
                                className={`relative group rounded-md overflow-hidden border-2 transition-all ${
                                  coverImage === photo.url
                                    ? "border-primary ring-2 ring-primary/30"
                                    : "border-transparent hover:border-primary/50"
                                }`}
                                onClick={() => setCoverImage(photo.url)}
                              >
                                <img
                                  src={photo.thumb}
                                  alt={photo.alt}
                                  className="w-full h-20 object-cover"
                                />
                                {coverImage === photo.url && (
                                  <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                                    <Check className="h-5 w-5 text-primary-foreground drop-shadow" />
                                  </div>
                                )}
                                <div className="absolute bottom-0 inset-x-0 bg-black/60 text-white text-[10px] px-1 py-0.5 truncate opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                                  {photo.photographer}
                                </div>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* AI Generation */}
                    {imageTab === "ai" && (
                      <div className="space-y-3">
                        <div className="flex gap-2">
                          <Input
                            value={aiPrompt}
                            onChange={(e) => setAiPrompt(e.target.value)}
                            placeholder="Décrivez l'image souhaitée..."
                            className="h-8 text-sm"
                            onKeyDown={(e) => e.key === "Enter" && handleAiGenerate()}
                          />
                          <Button
                            type="button"
                            size="sm"
                            onClick={handleAiGenerate}
                            disabled={aiGenerating}
                          >
                            {aiGenerating ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Sparkles className="h-4 w-4" />
                            )}
                          </Button>
                        </div>
                        {aiGenerating && (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Génération en cours...
                          </div>
                        )}
                        {aiPreview && (
                          <div className="space-y-2">
                            <img
                              src={aiPreview}
                              alt="Generated"
                              className="w-full max-w-md h-48 object-cover rounded-md"
                            />
                            <Button
                              type="button"
                              size="sm"
                              onClick={() => {
                                setCoverImage(aiImageUrl);
                                toast.success("Image appliquée!");
                              }}
                              disabled={coverImage === aiImageUrl}
                            >
                              <Check className="h-4 w-4 mr-1.5" />
                              {coverImage === aiImageUrl ? "Appliquée" : "Utiliser cette image"}
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              <div className="text-xs text-muted-foreground">
                Extrait: {excerpt.length}/160 car.
              </div>
            </div>
          </div>
        )}
      </div>

      <ImageInsertDialog
        open={imageDialogOpen}
        onOpenChange={(open) => {
          setImageDialogOpen(open);
          if (!open) {
            replacingImageRef.current = null;
            setImageDialogQuery("");
          }
        }}
        onInsert={handleImageInsert}
        initialQuery={imageDialogQuery}
        articleContext={{
          title,
          keyword: tagsInput.split(",")[0]?.trim() || "",
          language,
        }}
      />

      {/* AI Article Generation Dialog */}
      <Dialog open={aiDialogOpen} onOpenChange={setAiDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Wand2 className="h-5 w-5" />
              Générer avec IA
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-sm">Sujet</Label>
              <Input
                value={aiTopic}
                onChange={(e) => setAiTopic(e.target.value)}
                placeholder="Ex: Les meilleures pratiques SEO en 2026"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-sm flex items-center gap-1.5">
                <Globe className="h-3.5 w-3.5" />
                URLs de contexte
              </Label>
              <p className="text-xs text-muted-foreground">
                Ajoutez des liens pour donner du contexte à l&apos;IA
              </p>
              {aiUrls.map((url, i) => (
                <div key={i} className="flex gap-2">
                  <Input
                    value={url}
                    onChange={(e) => {
                      const next = [...aiUrls];
                      next[i] = e.target.value;
                      setAiUrls(next);
                    }}
                    placeholder="https://example.com/article"
                    className="text-sm"
                  />
                  {aiUrls.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="shrink-0"
                      onClick={() => setAiUrls(aiUrls.filter((_, j) => j !== i))}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              ))}
              <Button
                variant="ghost"
                size="sm"
                className="text-xs"
                onClick={() => setAiUrls([...aiUrls, ""])}
              >
                <Plus className="h-3 w-3 mr-1" />
                Ajouter une URL
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-sm">Type</Label>
                <Select value={aiType} onValueChange={setAiType}>
                  <SelectTrigger className="text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="news">Actualité</SelectItem>
                    <SelectItem value="tutorial">Tutoriel</SelectItem>
                    <SelectItem value="guide">Guide</SelectItem>
                    <SelectItem value="comparison">Comparatif</SelectItem>
                    <SelectItem value="review">Review</SelectItem>
                    <SelectItem value="story">Story</SelectItem>
                    <SelectItem value="local">Local</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-sm">Longueur</Label>
                <Select value={aiLength} onValueChange={setAiLength}>
                  <SelectTrigger className="text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="short">Court</SelectItem>
                    <SelectItem value="medium">Moyen</SelectItem>
                    <SelectItem value="long">Long</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-sm">Mots-clés SEO</Label>
              <Input
                value={aiKeywords}
                onChange={(e) => setAiKeywords(e.target.value)}
                placeholder="mot1, mot2, mot3"
                className="text-sm"
              />
            </div>

            <Button
              className="w-full"
              onClick={handleAiGenerateArticle}
              disabled={aiLoading}
            >
              {aiLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Génération en cours...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Générer l&apos;article
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
