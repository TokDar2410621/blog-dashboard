import { Badge } from "@/components/ui/badge";

const statusConfig: Record<
  string,
  { label: string; variant: "default" | "secondary" | "outline" | "destructive" }
> = {
  published: { label: "Publie", variant: "default" },
  draft: { label: "Brouillon", variant: "secondary" },
  scheduled: { label: "Planifie", variant: "outline" },
};

export function PostStatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || {
    label: status,
    variant: "secondary" as const,
  };
  return <Badge variant={config.variant}>{config.label}</Badge>;
}
