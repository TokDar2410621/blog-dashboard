import { Badge } from "@/components/ui/badge";
import { useTranslation } from "react-i18next";
import { POST_STATUS_VARIANT, type PostStatus } from "@/lib/constants";

export function PostStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const variant = POST_STATUS_VARIANT[status as PostStatus] || "secondary";
  const label = t(`status.${status}`, status);
  return <Badge variant={variant}>{label}</Badge>;
}
