import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useAllPosts, useDeletePost } from "@/hooks/useDashboard";
import { PostStatusBadge } from "@/components/PostStatusBadge";
import { ProofBadge } from "@/components/ProofBadge";
import { TemplateSelector } from "@/components/TemplateSelector";
import { fetchProofAttribution, type ProofAttribution } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
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
import { buttonVariants } from "@/components/ui/button";
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

export default function PostList() {
  const { t, i18n } = useTranslation();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [templateOpen, setTemplateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ slug: string; title: string } | null>(null);
  const { data, isLoading } = useAllPosts(page);
  const deletePost = useDeletePost();
  const navigate = useNavigate();
  const { siteId } = useParams<{ siteId: string }>();
  const base = `/dashboard/${siteId}`;

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
      onSuccess: () => toast.success(t("posts.deleted")),
      onError: () => toast.error(t("posts.deleteError")),
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("posts.title")}</h1>
        <div className="flex items-center gap-2">
          <ExportButton
            onExport={handleExportPosts}
            disabled={filteredPosts.length === 0}
          />
          <Button onClick={() => setTemplateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            {t("posts.newPost")}
          </Button>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={t("posts.searchPlaceholder")}
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
                  <TableHead>{t("posts.tableTitle")}</TableHead>
                  <TableHead>{t("posts.tableStatus")}</TableHead>
                  <TableHead>{t("posts.tableCategory")}</TableHead>
                  <TableHead className="text-right">{t("posts.tableViews")}</TableHead>
                  <TableHead className="text-right">{t("posts.tableProof", "Preuve")}</TableHead>
                  <TableHead>{t("posts.tableDate")}</TableHead>
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
                      {t("posts.empty")}
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
                                title={`Disponible en ${translations.map(t => t.language?.toUpperCase()).join(", ")}`}
                              >
                                {translations.map(t => t.language?.toUpperCase()).join("/")}
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
                          {new Date(post.created_at).toLocaleDateString(
                            i18n.language === "fr" ? "fr-CA" : "en-CA"
                          )}
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
                                  navigate(
                                    `${base}/articles/${post.slug}`
                                  )
                                }
                              >
                                <Pencil className="h-4 w-4 mr-2" />
                                {t("posts.edit")}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() =>
                                  navigate(
                                    `${base}/articles/${post.slug}`
                                  )
                                }
                              >
                                <ExternalLink className="h-4 w-4 mr-2" />
                                {t("posts.viewOnSite")}
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() =>
                                  handleDelete(post.slug, post.title)
                                }
                              >
                                <Trash2 className="h-4 w-4 mr-2" />
                                {t("posts.delete")}
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
          {t("posts.articleCount", { count: totalCount })}
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
          <span className="text-sm">{t("common.page")} {page}</span>
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
          navigate(`${base}/articles/nouveau?tpl_type=markdown&tpl_id=${tpl.id}`)
        }
        onSelectVisual={(tpl) =>
          navigate(`${base}/articles/nouveau?tpl_type=visual&tpl_id=${tpl.id}`)
        }
        onSelectAI={(tpl) =>
          navigate(`${base}/generer?tpl_id=${tpl.id}`)
        }
        onSelectBlank={() => navigate(`${base}/articles/nouveau`)}
      />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {t("posts.deleteConfirm", { title: deleteTarget?.title ?? "" })}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {t("posts.deleteConfirmDesc")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("common.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className={cn(buttonVariants({ variant: "destructive" }))}
            >
              {t("posts.delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
