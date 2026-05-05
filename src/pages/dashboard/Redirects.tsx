import { useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowRight,
  Plus,
  Trash2,
  Loader2,
  Move,
  MousePointerClick,
} from "lucide-react";
import { toast } from "sonner";

type RedirectItem = {
  id: number;
  from_slug: string;
  to_slug: string;
  language: string;
  hit_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export default function Redirects() {
  const { t } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const qc = useQueryClient();

  const [fromSlug, setFromSlug] = useState("");
  const [toSlug, setToSlug] = useState("");
  const [language, setLanguage] = useState("fr");

  const list = useQuery({
    queryKey: ["redirects", siteId],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/redirects/`);
      if (!res.ok) throw new Error("fetch failed");
      return (await res.json()).results as RedirectItem[];
    },
  });

  const add = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/redirects/`, {
        method: "POST",
        body: JSON.stringify({
          from_slug: fromSlug.trim(),
          to_slug: toSlug.trim(),
          language,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || t("redirects.addError"));
      }
      return res.json();
    },
    onSuccess: () => {
      setFromSlug("");
      setToSlug("");
      qc.invalidateQueries({ queryKey: ["redirects", siteId] });
      toast.success(t("redirects.added"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const remove = useMutation({
    mutationFn: async (id: number) => {
      const res = await authFetch(`/sites/${siteId}/redirects/${id}/`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        throw new Error(t("redirects.deleteError"));
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["redirects", siteId] });
      toast.success(t("redirects.deleted"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">{t("redirects.title")}</h1>
        <p className="text-muted-foreground">{t("redirects.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Plus className="h-5 w-5 text-primary" />
            {t("redirects.addTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr_auto_auto] gap-3 items-end">
            <div className="space-y-1">
              <label className="text-xs font-medium">
                {t("redirects.fromSlug")}
              </label>
              <Input
                value={fromSlug}
                onChange={(e) => setFromSlug(e.target.value)}
                placeholder={t("redirects.fromSlugPlaceholder")}
              />
            </div>
            <div className="hidden md:flex items-center justify-center pb-2">
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">
                {t("redirects.toSlug")}
              </label>
              <Input
                value={toSlug}
                onChange={(e) => setToSlug(e.target.value)}
                placeholder={t("redirects.toSlugPlaceholder")}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">
                {t("redirects.language")}
              </label>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fr">FR</SelectItem>
                  <SelectItem value="en">EN</SelectItem>
                  <SelectItem value="es">ES</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => add.mutate()}
              disabled={add.isPending || !fromSlug.trim() || !toSlug.trim()}
            >
              {add.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  {t("redirects.add")}
                </>
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            {t("redirects.autoHint")}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {list.isLoading ? (
            <div className="p-6 space-y-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          ) : !list.data?.length ? (
            <div className="p-12 text-center text-muted-foreground">
              <Move className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>{t("redirects.empty")}</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("redirects.fromSlug")}</TableHead>
                  <TableHead className="w-8"></TableHead>
                  <TableHead>{t("redirects.toSlug")}</TableHead>
                  <TableHead className="w-16">{t("redirects.language")}</TableHead>
                  <TableHead className="w-20 text-right">
                    <MousePointerClick className="h-4 w-4 inline" />
                  </TableHead>
                  <TableHead>{t("redirects.updated")}</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.data.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">
                      {r.from_slug}
                    </TableCell>
                    <TableCell>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                    </TableCell>
                    <TableCell className="font-mono text-xs">{r.to_slug}</TableCell>
                    <TableCell>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase">
                        {r.language}
                      </span>
                    </TableCell>
                    <TableCell className="text-right font-mono text-sm">
                      {r.hit_count}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(r.updated_at).toLocaleDateString("fr-CA")}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          if (confirm(t("redirects.confirmDelete"))) {
                            remove.mutate(r.id);
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
