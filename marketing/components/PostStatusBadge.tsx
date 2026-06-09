import { Badge } from "@/components/ui/badge";
import { POST_STATUS_VARIANT, type PostStatus } from "@/lib/constants";

const STATUS_LABELS_FR: Record<string, string> = {
  draft: "Brouillon",
  published: "Publié",
  scheduled: "Planifié",
};

export function PostStatusBadge({ status }: { status: string }) {
  const variant = POST_STATUS_VARIANT[status as PostStatus] || "secondary";
  const label = STATUS_LABELS_FR[status] || status;
  return <Badge variant={variant}>{label}</Badge>;
}
