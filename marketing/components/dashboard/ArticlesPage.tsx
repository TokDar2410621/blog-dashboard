"use client";

import { useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, AlertCircle, Clock } from "lucide-react";
import { useAllPosts, useDeletePost, useSite } from "@/hooks/useDashboard";
import { TemplateSelector } from "@/components/dashboard/TemplateSelector";
import { fetchProofAttribution, type ProofAttribution } from "@/lib/api-client";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Plus,
  MoreHorizontal,
  Pencil,
  ExternalLink,
  Trash2,
  Search,
  Eye,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import type { PostListItem } from "@/lib/schemas";
import { ExportButton } from "@/components/ui/ExportButton";
import { exportToCsv, exportToJson, type ExportColumn } from "@/lib/csv-export";
import { POST_STATUS_VARIANT, type PostStatus } from "@/lib/constants";
import { STATUS_LABELS, formatArticleCount } from "@/lib/articles-helpers";

/** Status badge for a post row (port of src/components/PostStatusBadge.tsx). */
function PostStatusBadge({ status }: { status: string }) {
  const variant = POST_STATUS_VARIANT[status as PostStatus] || "secondary";
  const label = STATUS_LABELS[status] ?? status;
  return <Badge variant={variant}>{label}</Badge>;
}

// --- ProofBadge (port of src/components/ProofBadge.tsx) ---

type ProofBadgeVariant = "won" | "unindexed" | "pending" | "empty";

function proofVariant(
  attribution: ProofAttribution | null,
  publishedAt: string | null
): ProofBadgeVariant {
  if (attribution && attribution.indexed && attribution.delta_vs_baseline?.impressions > 0) {
    return "won";
  }
  if (attribution && !attribution.indexed) return "unindexed";
  if (publishedAt) {
    const ageDays = Math.floor(
      (Date.now() - new Date(publishedAt).getTime()) / (1000 * 60 * 60 * 24)
    );
    if (ageDays < 30) return "pending";
  }
  return "empty";
}

function ProofBadge({
  attribution,
  publishedAt,
}: {
  attribution: ProofAttribution | null;
  publishedAt: string | null;
}) {
  const v = proofVariant(attribution, publishedAt);

  if (v === "won" && attribution) {
    const delta = attribution.delta_vs_baseline.impressions;
    const formatted =
      Math.abs(delta) >= 1000 ? `${(delta / 1000).toFixed(1)}k` : String(delta);
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-primary/10 text-primary"
        title={`+${delta} impressions GSC vs baseline (mesure J+${attribution.days_since_publish})`}
      >
        <TrendingUp className="h-3 w-3" />
        +{formatted} J+{attribution.days_since_publish}
      </span>
    );
  }

  if (v === "unindexed") {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400"
        title="Pas encore indexe par Google"
      >
        <AlertCircle className="h-3 w-3" />
        Pas indexe
      </span>
    );
  }

  if (v === "pending") {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-muted text-muted-foreground"
        title="Le premier check d'attribution arrive a J+30 apres publication"
      >
        <Clock className="h-3 w-3" />
        J+30
      </span>
    );
  }

  return (
    <span
      className="text-[11px] text-muted-foreground/60"
      title="Pas de baseline GSC pour cet article"
    >
      -
    </span>
  );
}

/** Articles list page (port of src/pages/dashboard/PostList.tsx). */
export default function ArticlesPage() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [templateOpen, setTemplateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ slug: string; title: string } | null>(null);
  const { data, isLoading } = useAllPosts(page);
  const deletePost = useDeletePost();
  const router = useRouter();
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const base = `/dashboard/${siteId}`;
  const { data: site } = useSite();

  // URL publique d'un article: {domaine public}/blog/{slug} (cf. _gridar_known_urls backend).
  const publicArticleUrl = (slug: string): string | null => {
    const raw = (site?.public_blog_domain || site?.domain || "")
      .trim()
      .replace(/^https?:\/\//, "")
      .replace(/\/+$/, "");
    return raw ? `https://${raw}/blog/${slug}` : null;
  };

  const posts: PostListItem[] = data?.results ?? [];
  const totalCount = data?.count ?? posts.length;
  const hasNext = !!data?.next;
  const hasPrev = page > 1;

  const attributionQuery = useQuery({
    queryKey: ["proof-attribution-list", siteId],
    queryFn: () => fetchProofAttribution(Number(siteId)),
    enabled: !!siteId,
    staleTime: 5 * 60 * 1000,
  });

  const attributionBySlug = useMemo(() => {
    const map = new Map<string, ProofAttribution>();
    for (const a of attributionQuery.data?.attributions ?? []) {
      const existing = map.get(a.post_slug);
      if (!existing || a.days_since_publish > existing.days_since_publish) {
        map.set(a.post_slug, a);
      }
    }
    return map;
  }, [attributionQuery.data]);

  const filteredPosts = search
    ? posts.filter((p: { title: string }) =>
        p.title.toLowerCase().includes(search.toLowerCase())
      )
    : posts;

  const handleDelete = (slug: string, title: string) => {
    setDeleteTarget({ slug, title });
  };

  const POST_COLUMNS: ExportColumn<PostListItem>[] = [
    { key: "title", label: "Titre" },
    { key: "slug", label: "Slug" },
    { key: "status", label: "Statut" },
    { key: "category", label: "Categorie" },
    { key: "language", label: "Langue" },
    { key: "view_count", label: "Vues" },
    { key: "featured", label: "Mis en avant" },
    { key: "created_at", label: "Date de creation" },
  ];

  const handleExportPosts = (format: "csv" | "json") => {
    if (filteredPosts.length === 0) {
      toast.info("Aucun article a exporter");
      return;
    }
    const filename = `articles-${siteId}-${new Date()
      .toISOString()
      .slice(0, 10)}.${format}`;
    if (format === "csv") exportToCsv(filename, filteredPosts, POST_COLUMNS);
    else exportToJson(filename, filteredPosts, POST_COLUMNS);
  };

  const confirmDelete = () => {
    if (!deleteTarget) return;
    const slug = deleteTarget.slug;
    setDeleteTarget(null);
    deletePost.mutate(slug, {
      onSuccess: () => toast.success("Article supprimé"),
      onError: () => toast.error("Erreur lors de la suppression"),
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Articles</h1>
        <div className="flex items-center gap-2">
          <ExportButton
            onExport={handleExportPosts}
            disabled={filteredPosts.length === 0}
          />
          <Button onClick={() => setTemplateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Nouvel article
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Rechercher un article..."
          className="pl-9"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Titre</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Catégorie</TableHead>
                  <TableHead className="text-right">Vues</TableHead>
                  <TableHead className="text-right">Preuve</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="w-10"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPosts.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={7}
                      className="text-center py-8 text-muted-foreground"
                    >
                      Aucun article trouvé
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredPosts.map((post: PostListItem) => {
                    // Group translations: posts with same translation_group
                    const translations = post.translation_group
                      ? filteredPosts.filter(
                          (p) => p.translation_group === post.translation_group
                        )
                      : [];
                    return (
                      <TableRow key={post.slug}>
                        <TableCell className="font-medium max-w-xs truncate">
                          <div className="flex items-center gap-2">
                            <span className="truncate">{post.title}</span>
                            {translations.length > 1 && (
                              <span
                                className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-mono shrink-0"
                                title={`Disponible en ${translations.map((t) => t.language?.toUpperCase()).join(", ")}`}
                              >
                                {translations.map((t) => t.language?.toUpperCase()).join("/")}
                              </span>
                            )}
                            {translations.length <= 1 && post.language && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono shrink-0">
                                {post.language.toUpperCase()}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <PostStatusBadge
                            status={post.status || "published"}
                          />
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {post.category || "-"}
                        </TableCell>
                        <TableCell className="text-right">
                          <span className="flex items-center justify-end gap-1">
                            <Eye className="h-3 w-3" />
                            {post.view_count ?? 0}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <ProofBadge
                            attribution={attributionBySlug.get(post.slug) ?? null}
                            publishedAt={post.created_at}
                          />
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {new Date(post.created_at).toLocaleDateString("fr-CA")}
                        </TableCell>
                        <TableCell>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <Button variant="ghost" size="icon">
                                <MoreHorizontal className="h-4 w-4" />
                              </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem
                                onClick={() =>
                                  router.push(
                                    `${base}/articles/${post.slug}`
                                  )
                                }
                              >
                                <Pencil className="h-4 w-4 mr-2" />
                                Modifier
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => {
                                  const url = publicArticleUrl(post.slug);
                                  if (!url) {
                                    toast.error(
                                      "Domaine du site non configuré"
                                    );
                                    return;
                                  }
                                  window.open(
                                    url,
                                    "_blank",
                                    "noopener,noreferrer"
                                  );
                                }}
                              >
                                <ExternalLink className="h-4 w-4 mr-2" />
                                Voir sur le site
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() =>
                                  handleDelete(post.slug, post.title)
                                }
                              >
                                <Trash2 className="h-4 w-4 mr-2" />
                                Supprimer
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {formatArticleCount(totalCount)}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={!hasPrev}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm">Page {page}</span>
          <Button
            variant="outline"
            size="sm"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <TemplateSelector
        open={templateOpen}
        onOpenChange={setTemplateOpen}
        onSelectMarkdown={(tpl) =>
          router.push(`${base}/articles/nouveau?tpl_type=markdown&tpl_id=${tpl.id}`)
        }
        onSelectVisual={(tpl) =>
          router.push(`${base}/articles/nouveau?tpl_type=visual&tpl_id=${tpl.id}`)
        }
        onSelectAI={(tpl) =>
          router.push(`${base}/generer?tpl_id=${tpl.id}`)
        }
        onSelectBlank={() => router.push(`${base}/articles/nouveau`)}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {`Supprimer "${deleteTarget?.title ?? ""}" ?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est irréversible. L&apos;article sera retiré du site
              définitivement.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className={cn(buttonVariants({ variant: "destructive" }))}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
