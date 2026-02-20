import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as api from "@/lib/api-client";

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard", "stats"],
    queryFn: api.fetchDashboardStats,
    staleTime: 1000 * 60 * 2,
  });
}

export function useAllPosts(page = 1) {
  return useQuery({
    queryKey: ["dashboard", "posts", page],
    queryFn: () => api.fetchAllPosts(page),
    staleTime: 1000 * 60,
  });
}

export function usePost(slug: string) {
  return useQuery({
    queryKey: ["dashboard", "post", slug],
    queryFn: () => api.fetchPost(slug),
    enabled: !!slug,
    staleTime: 1000 * 60,
  });
}

export function useCategories() {
  return useQuery({
    queryKey: ["dashboard", "categories"],
    queryFn: api.fetchCategories,
    staleTime: 1000 * 60 * 10,
  });
}

export function useTags() {
  return useQuery({
    queryKey: ["dashboard", "tags"],
    queryFn: api.fetchTags,
    staleTime: 1000 * 60 * 10,
  });
}

export function useCreatePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createPost,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard", "posts"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
  });
}

export function useUpdatePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      slug,
      data,
    }: {
      slug: string;
      data: Record<string, unknown>;
    }) => api.updatePost(slug, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard", "posts"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "post"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
  });
}

export function useDeletePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.deletePost,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard", "posts"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
  });
}

export function useGenerateArticle() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.generateArticle,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard", "posts"] });
      qc.invalidateQueries({ queryKey: ["dashboard", "stats"] });
    },
  });
}

export function useUploadImage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.uploadImage,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard", "images"] });
    },
  });
}

export function useImages() {
  return useQuery({
    queryKey: ["dashboard", "images"],
    queryFn: api.fetchImages,
    staleTime: 1000 * 60 * 5,
  });
}
