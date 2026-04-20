import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import * as api from "@/lib/api-client";
import { QK, STALE_TIME } from "@/lib/constants";

function useSiteId(): number {
  const { siteId } = useParams<{ siteId: string }>();
  return parseInt(siteId || "0", 10);
}

export function useSites() {
  return useQuery({
    queryKey: QK.SITES,
    queryFn: api.fetchSites,
    staleTime: STALE_TIME.SITES,
  });
}

export function useSite() {
  const siteId = useSiteId();
  return useQuery({
    queryKey: QK.site(siteId),
    queryFn: () => api.fetchSite(siteId),
    enabled: !!siteId,
    staleTime: STALE_TIME.SITES,
  });
}

export function useUpdateSite() {
  const siteId = useSiteId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => api.updateSite(siteId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.site(siteId) });
      qc.invalidateQueries({ queryKey: QK.SITES });
    },
  });
}

export function useDashboardStats() {
  const siteId = useSiteId();
  return useQuery({
    queryKey: QK.DASHBOARD.stats(siteId),
    queryFn: () => api.fetchDashboardStats(siteId),
    enabled: !!siteId,
    staleTime: STALE_TIME.STATS,
  });
}

export function useAllPosts(page = 1) {
  const siteId = useSiteId();
  return useQuery({
    queryKey: QK.DASHBOARD.posts(siteId, page),
    queryFn: () => api.fetchAllPosts(siteId, page),
    enabled: !!siteId,
    staleTime: STALE_TIME.POSTS,
  });
}

export function usePost(slug: string) {
  const siteId = useSiteId();
  return useQuery({
    queryKey: QK.DASHBOARD.post(siteId, slug),
    queryFn: () => api.fetchPost(siteId, slug),
    enabled: !!siteId && !!slug,
    staleTime: STALE_TIME.POSTS,
  });
}

export function useCategories() {
  const siteId = useSiteId();
  return useQuery({
    queryKey: QK.DASHBOARD.categories(siteId),
    queryFn: () => api.fetchCategories(siteId),
    enabled: !!siteId,
    staleTime: STALE_TIME.CATEGORIES,
  });
}

export function useTags() {
  const siteId = useSiteId();
  return useQuery({
    queryKey: QK.DASHBOARD.tags(siteId),
    queryFn: () => api.fetchTags(siteId),
    enabled: !!siteId,
    staleTime: STALE_TIME.TAGS,
  });
}

export function useCreatePost() {
  const siteId = useSiteId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Record<string, unknown>) => api.createPost(siteId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.posts(siteId) });
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.stats(siteId) });
    },
  });
}

export function useUpdatePost() {
  const siteId = useSiteId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, data }: { slug: string; data: Record<string, unknown> }) =>
      api.updatePost(siteId, slug, data),
    onMutate: async ({ slug, data }) => {
      await qc.cancelQueries({ queryKey: QK.DASHBOARD.post(siteId, slug) });
      const previous = qc.getQueryData(QK.DASHBOARD.post(siteId, slug));
      qc.setQueryData(QK.DASHBOARD.post(siteId, slug), (old: Record<string, unknown> | undefined) =>
        old ? { ...old, ...data } : old
      );
      return { previous, slug };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        qc.setQueryData(QK.DASHBOARD.post(siteId, context.slug), context.previous);
      }
    },
    onSettled: (_data, _err, variables) => {
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.posts(siteId) });
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.post(siteId, variables.slug) });
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.stats(siteId) });
    },
  });
}

export function useDeletePost() {
  const siteId = useSiteId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.deletePost(siteId, slug),
    onMutate: async (slug) => {
      await qc.cancelQueries({ queryKey: QK.DASHBOARD.posts(siteId) });
      const previousPosts = qc.getQueriesData({ queryKey: QK.DASHBOARD.posts(siteId) });
      // Optimistically remove the post from all paginated lists
      qc.setQueriesData(
        { queryKey: QK.DASHBOARD.posts(siteId) },
        (old: { count: number; results: { slug: string }[]; next: number | null; previous: number | null } | undefined) => {
          if (!old) return old;
          return {
            ...old,
            count: old.count - 1,
            results: old.results.filter((p) => p.slug !== slug),
          };
        }
      );
      return { previousPosts };
    },
    onError: (_err, _slug, context) => {
      // Restore all paginated queries
      context?.previousPosts.forEach(([key, data]) => {
        qc.setQueryData(key, data);
      });
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.posts(siteId) });
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.stats(siteId) });
    },
  });
}

export function useGenerateArticle() {
  const siteId = useSiteId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: Record<string, unknown>) => api.generateArticle(siteId, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.posts(siteId) });
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.stats(siteId) });
    },
  });
}

export function useImages() {
  const siteId = useSiteId();
  return useQuery({
    queryKey: QK.DASHBOARD.images(siteId),
    queryFn: () => api.fetchImages(siteId),
    enabled: !!siteId,
    staleTime: STALE_TIME.IMAGES,
  });
}

export function useUploadImage() {
  const siteId = useSiteId();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.uploadImage(siteId, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: QK.DASHBOARD.images(siteId) });
    },
  });
}
