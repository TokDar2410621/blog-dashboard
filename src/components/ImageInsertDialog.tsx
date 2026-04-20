import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { searchPexels, uploadInlineImage } from "@/lib/api-client";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Search,
  Upload,
  Loader2,
  Check,
  ImageIcon,
} from "lucide-react";

interface PexelsPhoto {
  id: number;
  url: string;
  thumb: string;
  alt: string;
  photographer: string;
}

interface ImageInsertDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInsert: (markdown: string) => void;
  initialQuery?: string;
}

export function ImageInsertDialog({
  open,
  onOpenChange,
  onInsert,
  initialQuery,
}: ImageInsertDialogProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"pexels" | "upload">("pexels");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PexelsPhoto[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedUrl, setSelectedUrl] = useState("");
  const [altText, setAltText] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const didAutoSearch = useRef(false);

  useEffect(() => {
    if (open && initialQuery && !didAutoSearch.current) {
      setQuery(initialQuery);
      setTab("pexels");
      didAutoSearch.current = true;
      // Auto-search after state is set
      (async () => {
        setLoading(true);
        try {
          const data = await searchPexels(initialQuery);
          setResults(data.photos || []);
        } catch {
          // Silently handle
        } finally {
          setLoading(false);
        }
      })();
    }
    if (!open) {
      didAutoSearch.current = false;
    }
  }, [open, initialQuery]);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await searchPexels(query);
      setResults(data.photos || []);
    } catch {
      // Silently handle
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const data = await uploadInlineImage(file);
      setSelectedUrl(data.url);
      setAltText(file.name.replace(/\.[^.]+$/, ""));
    } catch {
      // Silently handle
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleInsert = () => {
    if (!selectedUrl) return;
    const alt = altText.trim() || "image";
    onInsert(`\n![${alt}](${selectedUrl})\n`);
    handleClose();
  };

  const handleClose = () => {
    setSelectedUrl("");
    setAltText("");
    setResults([]);
    setQuery("");
    onOpenChange(false);
  };

  const selectPhoto = (photo: PexelsPhoto) => {
    setSelectedUrl(photo.url);
    setAltText(photo.alt || query);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ImageIcon className="h-5 w-5" />
            {t("imageDialog.title")}
          </DialogTitle>
          <DialogDescription>
            {t("imageDialog.description")}
          </DialogDescription>
        </DialogHeader>

        {/* Tab buttons */}
        <div className="flex gap-2">
          <Button
            type="button"
            variant={tab === "pexels" ? "default" : "outline"}
            size="sm"
            onClick={() => setTab("pexels")}
          >
            <Search className="h-3.5 w-3.5 mr-1.5" />
            Pexels
          </Button>
          <Button
            type="button"
            variant={tab === "upload" ? "default" : "outline"}
            size="sm"
            onClick={() => setTab("upload")}
          >
            <Upload className="h-3.5 w-3.5 mr-1.5" />
            Upload
          </Button>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {tab === "pexels" && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t("imageDialog.searchPlaceholder")}
                  className="h-8 text-sm"
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={handleSearch}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Search className="h-4 w-4" />
                  )}
                </Button>
              </div>
              {results.length > 0 && (
                <div className="grid grid-cols-3 gap-2">
                  {results.map((photo) => (
                    <button
                      key={photo.id}
                      type="button"
                      className={`relative group rounded-md overflow-hidden border-2 transition-all ${
                        selectedUrl === photo.url
                          ? "border-primary ring-2 ring-primary/30"
                          : "border-transparent hover:border-primary/50"
                      }`}
                      onClick={() => selectPhoto(photo)}
                    >
                      <img
                        src={photo.thumb}
                        alt={photo.alt}
                        className="w-full h-24 object-cover"
                      />
                      {selectedUrl === photo.url && (
                        <div className="absolute inset-0 bg-primary/20 flex items-center justify-center">
                          <Check className="h-5 w-5 text-primary-foreground drop-shadow" />
                        </div>
                      )}
                      <div className="absolute bottom-0 inset-x-0 bg-black/60 text-white text-[10px] px-1 py-0.5 truncate opacity-0 group-hover:opacity-100 transition-opacity">
                        {photo.photographer}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === "upload" && (
            <div className="space-y-4">
              <div
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => fileInputRef.current?.click()}
              >
                {uploading ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">{t("imageDialog.uploading")}</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <Upload className="h-8 w-8 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      {t("imageDialog.clickToUpload")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("imageDialog.fileTypes")}
                    </p>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </div>
            </div>
          )}
        </div>

        {/* Preview + insert */}
        {selectedUrl && (
          <div className="border-t pt-4 space-y-3">
            <div className="flex gap-3 items-start">
              <img
                src={selectedUrl}
                alt="Preview"
                className="w-24 h-16 object-cover rounded-md shrink-0"
              />
              <div className="flex-1 space-y-2">
                <div className="space-y-1">
                  <Label className="text-xs">{t("imageDialog.altText")}</Label>
                  <Input
                    value={altText}
                    onChange={(e) => setAltText(e.target.value)}
                    placeholder={t("imageDialog.altPlaceholder")}
                    className="h-8 text-sm"
                  />
                </div>
              </div>
            </div>
            <Button onClick={handleInsert} className="w-full" size="sm">
              <Check className="h-4 w-4 mr-1.5" />
              {t("imageDialog.insert")}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
