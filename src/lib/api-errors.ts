import type { TFunction } from "i18next";
import { ApiError } from "@/lib/api-client";

/** User-facing message for API failures (uses `errors.*` and falls back to `message`) */
export function getApiErrorMessage(error: unknown, t: TFunction): string {
  if (error instanceof ApiError && error.code) {
    const key = `errors.${error.code}`;
    const translated = t(key);
    if (translated !== key) return translated;
  }
  if (error instanceof Error && error.message) return error.message;
  return t("errors.GENERIC");
}
