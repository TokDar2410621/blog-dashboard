import { Download, FileSpreadsheet, FileJson } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export type ExportFormat = "csv" | "json";

type ExportButtonProps = {
  onExport: (format: ExportFormat) => void;
  /** Disable the trigger when there is nothing to export. */
  disabled?: boolean;
  /** Visible button label. Defaults to "Exporter". */
  label?: string;
  /** Optional extra className passed to the button. */
  className?: string;
  /** Button size, mirrors shadcn `Button` sizes. */
  size?: "default" | "sm" | "lg";
  /** Button variant, mirrors shadcn `Button` variants. */
  variant?: "default" | "outline" | "secondary" | "ghost";
};

export function ExportButton({
  onExport,
  disabled,
  label = "Exporter",
  className,
  size = "sm",
  variant = "outline",
}: ExportButtonProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant={variant}
          size={size}
          disabled={disabled}
          className={className}
        >
          <Download className="h-4 w-4 mr-2" />
          {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => onExport("csv")}>
          <FileSpreadsheet className="h-4 w-4 mr-2" />
          Exporter CSV
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => onExport("json")}>
          <FileJson className="h-4 w-4 mr-2" />
          Exporter JSON
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default ExportButton;
