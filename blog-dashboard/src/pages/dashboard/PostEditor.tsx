import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { usePost, useCreatePost, useUpdatePost, useCategories } from "@/hooks/useDashboard";
import { MarkdownEditor } from "@/components/MarkdownEditor";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { SEOPreview } from "@/components/SEOPreview";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Save, Send, Loader2 } from "lucide-react";
import { toast } from "sonner";

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

export default function PostEditor() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const isEditing = !!slug;

  const { data: existingPost, isLoading: loadingPost } = usePost(slug || "");
  const { data: categories = [] } = useCategories();
  const createPost = useCreatePost();
  const updatePost = useUpdatePost();

  // Form state
  const [title, setTitle] = useState("");
  const [postSlug, setPostSlug] = useState("");
  const [excerpt, setExcerpt] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [coverImage, setCoverImage] = useState("");
  const [status, setStatus] = useState("draft");
  const [featured, setFeatured] = useState(false);
  const [autoSlug, setAutoSlug] = useState(true);

  // Load existing post data
  useEffect(() => {
    if (existingPost && isEditing) {
      setTitle(existingPost.title || "");
      setPostSlug(existingPost.slug || "");
      setExcerpt(existingPost.excerpt || "");
      setContent(existingPost.content || "");
      setCategory(existingPost.category || "");
      setTagsInput(
        (existingPost.tags || []).join(", ")
      );
      setCoverImage(existingPost.cover_image || "");
      setStatus(existingPost.status || "published");
      setFeatured(existingPost.featured || false);
      setAutoSlug(false);
    }
  }, [existingPost, isEditing]);

  // Auto-generate slug from title
  useEffect(() => {
    if (autoSlug && !isEditing) {
      setPostSlug(slugify(title));
    }
  }, [title, autoSlug, isEditing]);

  const handleSave = async (publishStatus?: string) => {
    const data: Record<string, unknown> = {
      title,
      slug: postSlug,
      excerpt,
      content,
      category,
      tags_input: tagsInput,
      cover_image: coverImage,
      status: publishStatus || status,
      featured,
    };

    try {
      if (isEditing) {
        await updatePost.mutateAsync({ slug: slug!, data });
        toast.success("Article mis a jour!");
      } else {
        await createPost.mutateAsync(data);
        toast.success("Article cree!");
        navigate("/dashboard/articles");
      }
    } catch (err) {
      toast.error(
        "Erreur: " + (err instanceof Error ? err.message : "Inconnue")
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
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/dashboard/articles")}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-xl font-bold">
            {isEditing ? "Modifier l'article" : "Nouvel article"}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => handleSave("draft")}
            disabled={isSaving}
          >
            <Save className="h-4 w-4 mr-2" />
            Brouillon
          </Button>
          <Button
            onClick={() => handleSave("published")}
            disabled={isSaving}
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            ) : (
              <Send className="h-4 w-4 mr-2" />
            )}
            Publier
          </Button>
        </div>
      </div>

      {/* Editor Layout */}
      <ResizablePanelGroup className="min-h-[calc(100vh-140px)]">
        {/* Left: Editor */}
        <ResizablePanel defaultSize={55} minSize={35}>
          <div className="pr-4 space-y-4 overflow-y-auto h-full">
            {/* Title */}
            <div className="space-y-2">
              <Label>Titre</Label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Titre de l'article"
                className="text-lg font-semibold"
              />
            </div>

            {/* Slug */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Slug</Label>
                {!isEditing && (
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Switch
                      checked={autoSlug}
                      onCheckedChange={setAutoSlug}
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
              />
            </div>

            {/* Excerpt */}
            <div className="space-y-2">
              <Label>Extrait (meta description)</Label>
              <Textarea
                value={excerpt}
                onChange={(e) => setExcerpt(e.target.value)}
                placeholder="Resume en 160 caracteres..."
                rows={2}
              />
              <p className="text-xs text-muted-foreground">
                {excerpt.length}/160 caracteres
              </p>
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Categorie</Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger>
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
              <div className="space-y-2">
                <Label>Statut</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Brouillon</SelectItem>
                    <SelectItem value="published">Publie</SelectItem>
                    <SelectItem value="scheduled">Planifie</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Tags */}
            <div className="space-y-2">
              <Label>Tags (separes par virgule)</Label>
              <Input
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="React, Django, IA..."
              />
            </div>

            {/* Cover Image */}
            <div className="space-y-2">
              <Label>Image de couverture (URL)</Label>
              <Input
                value={coverImage}
                onChange={(e) => setCoverImage(e.target.value)}
                placeholder="https://..."
              />
              {coverImage && (
                <img
                  src={coverImage}
                  alt="Cover"
                  className="w-full h-32 object-cover rounded-md"
                />
              )}
            </div>

            {/* Featured */}
            <div className="flex items-center gap-3">
              <Switch checked={featured} onCheckedChange={setFeatured} />
              <Label>Article en vedette</Label>
            </div>

            {/* Markdown Editor */}
            <div className="space-y-2">
              <Label>Contenu</Label>
              <MarkdownEditor value={content} onChange={setContent} />
            </div>
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Right: Preview */}
        <ResizablePanel defaultSize={45} minSize={25}>
          <div className="pl-4 overflow-y-auto h-full">
            <Tabs defaultValue="preview">
              <TabsList className="w-full">
                <TabsTrigger value="preview" className="flex-1">
                  Apercu
                </TabsTrigger>
                <TabsTrigger value="seo" className="flex-1">
                  SEO
                </TabsTrigger>
              </TabsList>

              <TabsContent value="preview" className="mt-4">
                {coverImage && (
                  <img
                    src={coverImage}
                    alt="Cover"
                    className="w-full h-48 object-cover rounded-md mb-4"
                  />
                )}
                <h1 className="text-2xl font-bold mb-2">
                  {title || "Titre de l'article"}
                </h1>
                {excerpt && (
                  <p className="text-muted-foreground mb-4 italic">
                    {excerpt}
                  </p>
                )}
                <MarkdownPreview content={content} />
              </TabsContent>

              <TabsContent value="seo" className="mt-4">
                <SEOPreview
                  title={title}
                  slug={postSlug}
                  description={excerpt}
                  coverImage={coverImage}
                />
              </TabsContent>
            </Tabs>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}
