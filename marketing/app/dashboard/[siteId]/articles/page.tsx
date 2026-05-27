"use client";

import { useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useAllPosts, useDeletePost } from "@/hooks/useDashboard";
import { PostStatusBadge } from "@/components/PostStatusBadge";
import { TemplateSelector } from "@/components/TemplateSelector";
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

export default function PostList() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [templateOpen, setTemplateOpen] = useState(false);
  const { data, isLoading } = useAllPosts(page);
  const deletePost = useDeletePost();
  const router = useRouter();
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const base = `/dashboard/${siteId}`;

  const posts: PostListItem[] = data?.results ?? [];
  const totalCount = data?.count ?? posts.length;
  const hasNext = !!data?.next;
  const hasPrev = page > 1;

  const filteredPosts = search
    ? posts.filter((p) => p.title.toLowerCase().includes(search.toLowerCase()))
    : posts;

  const handleDelete = (slug: string, title: string) => {
    if (!confirm(`Supprimer l'article "${title}" ?`)) return;
    deletePost.mutate(slug, {
      onSuccess: () => toast.success("Article supprime"),
      onError: () => toast.error("Erreur suppression"),
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Articles</h1>
        <Button onClick={() => setTemplateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouvel article
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Chercher dans tes articles..."
          className="pl-9"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

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
                  <TableHead>Categorie</TableHead>
                  <TableHead className="text-right">Vues</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="w-10"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredPosts.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      Aucun article pour le moment.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredPosts.map((post) => {
                    const translations = post.translation_group
                      ? filteredPosts.filter((p) => p.translation_group === post.translation_group)
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
                          <PostStatusBadge status={post.status || "published"} />
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
                                onClick={() => router.push(`${base}/articles/${post.slug}`)}
                              >
                                <Pencil className="h-4 w-4 mr-2" />
                                Editer
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                onClick={() => router.push(`${base}/articles/${post.slug}`)}
                              >
                                <ExternalLink className="h-4 w-4 mr-2" />
                                Voir sur le site
                              </DropdownMenuItem>
                              <DropdownMenuItem
                                className="text-destructive"
                                onClick={() => handleDelete(post.slug, post.title)}
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

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">{totalCount} article(s)</p>
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
        onSelectAI={(tpl) => router.push(`${base}/generer?tpl_id=${tpl.id}`)}
        onSelectBlank={() => router.push(`${base}/articles/nouveau`)}
      />
    </div>
  );
}
