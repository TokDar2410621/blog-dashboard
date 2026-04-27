import { useState, useEffect, useRef, useMemo } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { usePost, useCreatePost, useUpdatePost, useCategories, useSites } from "@/hooks/useDashboard";
import { searchPexels, searchSerperImages, generateCoverImage, uploadInlineImage } from "@/lib/api-client";
import { markdownTemplates, visualTemplates } from "@/lib/templates";
import TurndownService from "turndown";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { ImageInsertDialog } from "@/components/ImageInsertDialog";
import { SEOPreview } from "@/components/SEOPreview";
import { SEOAnalyzer } from "@/components/SEOAnalyzer";
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

export default function PostEditor() {
  const { t, i18n } = useTranslation();
  const { slug, siteId } = useParams<{ slug: string; siteId: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
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
  const [imageTab, setImageTab] = useState<"pexels" | "serper" | "ai">("pexels");
  const [serperQuery, setSerperQuery] = useState("");
  const [serperResults, setSerperResults] = useState<{ id: number; url: string; thumb: string; alt: string; photographer: string }[]>([]);
  const [serperLoading, setSerperLoading] = useState(false);

  // Inline image insert dialog
  const [imageDialogOpen, setImageDialogOpen] = useState(false);
  const cursorPosRef = useRef(0);
  const replacingImageRef = useRef<string | null>(null);

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
      toast.success(t("editor.imageUploaded"));
    } catch {
      setContent(prev => prev.replace(placeholder, ""));
      toast.error(t("editor.imageUploadError"));
    }
  };

  const handlePexelsSearch = async () => {
    if (!pexelsQuery.trim()) return;
    setPexelsLoading(true);
    try {
      const data = await searchPexels(pexelsQuery);
      setPexelsResults(data.photos || []);
    } catch (err) {
      toast.error(t("editor.pexelsError") + (err instanceof Error ? err.message : "Inconnue"));
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
      navigate(`${base}/articles/${created.slug}`);
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
      setTagsInput(data.tags.join(", "));
      toast.success(`${data.tags.length} tags générés`);
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
      toast.error(t("editor.aiError") + (err instanceof Error ? err.message : "Inconnue"));
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
      if (existingPost.scheduled_at) {
        setScheduledAt(new Date(existingPost.scheduled_at).toISOString().slice(0, 16));
      }
      setAutoSlug(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [existingPost, isEditing]);

  useEffect(() => {
    if (autoSlug && !isEditing) {
      // Client-side slug preview only — backend generates the canonical slug
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
    const tplType = searchParams.get(QUERY_PARAM.TPL_TYPE);
    const tplId = searchParams.get(QUERY_PARAM.TPL_ID);
    if (!tplType || !tplId) return;

    if (tplType === TEMPLATE_TYPE.MARKDOWN) {
      const tpl = markdownTemplates.find((t) => t.id === tplId);
      if (tpl) {
        const lang = i18n.language as "fr" | "en";
        setContent(lang === "en" ? tpl.content_en : tpl.content_fr);
      }
    } else if (tplType === TEMPLATE_TYPE.VISUAL) {
      const tpl = visualTemplates.find((t) => t.id === tplId);
      if (tpl) {
        // Visual template sets a CSS class - stored in content metadata
        setContent(`<!-- template:${tpl.cssClass} -->\n\n`);
      }
    }
  }, [searchParams, isEditing, i18n.language]);

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
    if (finalStatus === POST_STATUS.SCHEDULED && scheduledAt) {
      data.scheduled_at = new Date(scheduledAt).toISOString();
    }

    try {
      if (isEditing) {
        await updatePost.mutateAsync({ slug: slug!, data });
        toast.success(t("editor.updated"));
      } else {
        await createPost.mutateAsync(data);
        toast.success(t("editor.created"));
        navigate(`${base}/articles`);
      }
    } catch (err) {
      toast.error(
        t("editor.saveError") + (err instanceof Error ? err.message : "Inconnue")
      );
    }
  };

  const isSaving = createPost.isPending || updatePost.isPending;

  if (isEditing && loadingPost) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-3rem)] flex flex-col">
      {/* Sticky Header */}
      <div className="flex items-center justify-between pb-3 border-b border-border shrink-0">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(`${base}/articles`)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-lg font-bold">
              {isEditing ? t("editor.editPost") : t("editor.newPost")}
            </h1>
            {postSlug && (
              <p className="text-xs text-muted-foreground">/{postSlug}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
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
            {t("editor.draft")}
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
            {t("editor.publish")}
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
          {t("editor.tabEditor")}
        </Button>
        <Button
          variant={view === "seo" ? "default" : "ghost"}
          size="sm"
          onClick={() => setView("seo")}
          className="h-7 text-xs"
        >
          <Search className="h-3.5 w-3.5 mr-1" />
          {t("editor.tabSeo")}
        </Button>
        <Button
          variant={view === "settings" ? "default" : "ghost"}
          size="sm"
          onClick={() => setView("settings")}
          className="h-7 text-xs"
        >
          <Settings2 className="h-3.5 w-3.5 mr-1" />
          {t("editor.tabSettings")}
        </Button>
      </div>

      {/* Main content */}
      <div className="flex-1 min-h-0">
        {/* Split view: Editor + Preview */}
        {view === "edit" && (
          <ResizablePanelGroup orientation="horizontal" className="h-full rounded-lg border">
            {/* Left panel: editor */}
            <ResizablePanel defaultSize={50} minSize={30}>
              <div className="h-full flex flex-col overflow-y-auto">
                <div className="p-4 space-y-3 shrink-0">
                  <Input
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder={t("editor.titlePlaceholder")}
                    className="text-xl font-bold h-12 border-0 px-0 focus-visible:ring-0 bg-transparent placeholder:text-muted-foreground/50"
                  />
                  <Textarea
                    value={excerpt}
                    onChange={(e) => setExcerpt(e.target.value)}
                    placeholder={t("editor.excerptPlaceholder")}
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

            <ResizableHandle withHandle />

            {/* Right panel: live preview */}
            <ResizablePanel defaultSize={50} minSize={25}>
              <div className="h-full overflow-y-auto p-6">
                <div className="flex items-center gap-2 mb-4 text-xs text-muted-foreground">
                  <Eye className="h-3.5 w-3.5" />
                  {t("editor.livePreview")}
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
          </ResizablePanelGroup>
        )}

        {/* SEO view */}
        {view === "seo" && (
          <div className="h-full overflow-y-auto pt-4">
            <div className="max-w-2xl space-y-6">
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
              <SEOPreview
                title={title}
                slug={postSlug}
                description={excerpt}
                coverImage={coverImage}
                siteUrl={currentSite?.domain || ""}
              />
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
                      {t("editor.publication")}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="px-4 pb-4 space-y-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs">{t("editor.status")}</Label>
                      <Select
                        value={status}
                        onValueChange={(v) => setStatus(v as PostStatus)}
                      >
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={POST_STATUS.DRAFT}>{t("editor.statusDraft")}</SelectItem>
                          <SelectItem value={POST_STATUS.PUBLISHED}>{t("editor.statusPublished")}</SelectItem>
                          <SelectItem value={POST_STATUS.SCHEDULED}>{t("editor.statusScheduled")}</SelectItem>
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
                          {t("editor.scheduledAt")}
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
                      <Label className="text-xs">{t("editor.category")}</Label>
                      <Select value={category} onValueChange={setCategory}>
                        <SelectTrigger className="h-8 text-sm">
                          <SelectValue placeholder={t("editor.categoryPlaceholder")} />
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
                        {t("editor.featured")}
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
                        <Label className="text-xs">{t("editor.slug")}</Label>
                        {!isEditing && (
                          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                            <Switch
                              checked={autoSlug}
                              onCheckedChange={setAutoSlug}
                              className="scale-75"
                            />
                            {t("editor.slugAuto")}
                          </label>
                        )}
                      </div>
                      <Input
                        value={postSlug}
                        onChange={(e) => {
                          setAutoSlug(false);
                          setPostSlug(e.target.value);
                        }}
                        placeholder={t("editor.slugPlaceholder")}
                        className="h-8 text-sm font-mono"
                      />
                    </CardContent>
                  </Card>

                  {/* Tags */}
                  <Card>
                    <CardContent className="p-4 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs">{t("editor.tags")}</Label>
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
                        placeholder={t("editor.tagsPlaceholder")}
                        className="h-8 text-sm"
                      />
                      <p className="text-xs text-muted-foreground">{t("editor.tagsSeparator")}</p>
                    </CardContent>
                  </Card>
                </div>
              </div>

              {/* Row 2: Image de couverture */}
              <Card>
                <CardHeader className="py-3 px-4">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <ImageIcon className="h-4 w-4" />
                    {t("editor.coverImage")}
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4 space-y-4">
                  <div className="flex gap-4 items-start">
                    <div className="flex-1 space-y-2">
                      <Input
                        value={coverImage}
                        onChange={(e) => setCoverImage(e.target.value)}
                        placeholder={t("editor.coverImageUrl")}
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
                    <div className="flex gap-2 mb-3">
                      <Button
                        type="button"
                        variant={imageTab === "pexels" ? "default" : "outline"}
                        size="sm"
                        onClick={() => setImageTab("pexels")}
                      >
                        <Search className="h-3.5 w-3.5 mr-1.5" />
                        {t("editor.pexels")}
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
                        {t("editor.generateAi")}
                      </Button>
                    </div>

                    {/* Pexels Search */}
                    {imageTab === "pexels" && (
                      <div className="space-y-3">
                        <div className="flex gap-2">
                          <Input
                            value={pexelsQuery}
                            onChange={(e) => setPexelsQuery(e.target.value)}
                            placeholder={t("editor.pexelsPlaceholder")}
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
                                <div className="absolute bottom-0 inset-x-0 bg-black/60 text-white text-[10px] px-1 py-0.5 truncate opacity-0 group-hover:opacity-100 transition-opacity">
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
                                <div className="absolute bottom-0 inset-x-0 bg-black/60 text-white text-[10px] px-1 py-0.5 truncate opacity-0 group-hover:opacity-100 transition-opacity">
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
                            placeholder={t("editor.aiPromptPlaceholder")}
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
                            {t("editor.aiGenerating")}
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
                                toast.success(t("editor.imageAppliedToast"));
                              }}
                              disabled={coverImage === aiImageUrl}
                            >
                              <Check className="h-4 w-4 mr-1.5" />
                              {coverImage === aiImageUrl ? t("editor.imageApplied") : t("editor.useImage")}
                            </Button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>

              <div className="text-xs text-muted-foreground">
                {t("editor.excerptCount", { count: excerpt.length })}
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
                Ajoutez des liens pour donner du contexte à l'IA
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
                  Générer l'article
                </>
              )}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
