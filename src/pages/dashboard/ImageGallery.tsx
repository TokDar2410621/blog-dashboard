import { useState, useCallback } from "react";
import { useImages, useUploadImage } from "@/hooks/useDashboard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Upload,
  Copy,
  Search,
  Image as ImageIcon,
  Loader2,
  Check,
} from "lucide-react";
import { toast } from "sonner";

export default function ImageGallery() {
  const { data: images = [], isLoading } = useImages();
  const uploadImage = useUploadImage();
  const [search, setSearch] = useState("");
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleUpload = useCallback(
    async (files: FileList | null) => {
      if (!files || files.length === 0) return;
      for (const file of Array.from(files)) {
        try {
          await uploadImage.mutateAsync(file);
          toast.success(`${file.name} uploade!`);
        } catch {
          toast.error(`Erreur upload: ${file.name}`);
        }
      }
    },
    [uploadImage]
  );

  const handleCopy = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedUrl(url);
    toast.success("URL copiee!");
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const imageList = Array.isArray(images)
    ? images
    : images.resources || images.results || [];

  const filteredImages = search
    ? imageList.filter((img: { public_id?: string; url?: string }) =>
        (img.public_id || img.url || "")
          .toLowerCase()
          .includes(search.toLowerCase())
      )
    : imageList;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Images</h1>
        <p className="text-muted-foreground">
          Gerez vos images uploadees sur Cloudinary
        </p>
      </div>

      {/* Upload Zone */}
      <div
        className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
          dragOver
            ? "border-primary bg-primary/5"
            : "border-muted-foreground/25 hover:border-primary/50"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {uploadImage.isPending ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">Upload en cours...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Glissez-deposez ou{" "}
              <label className="text-primary cursor-pointer hover:underline">
                parcourez
                <input
                  type="file"
                  className="hidden"
                  accept="image/*"
                  multiple
                  onChange={(e) => handleUpload(e.target.files)}
                />
              </label>
            </p>
          </div>
        )}
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Rechercher une image..."
          className="pl-9"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Gallery */}
      {isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="aspect-video" />
          ))}
        </div>
      ) : filteredImages.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <ImageIcon className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">
              {isLoading
                ? "Chargement..."
                : "Aucune image. Verifiez que le backend supporte /api/images/."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {filteredImages.map(
            (
              img: {
                public_id?: string;
                url?: string;
                secure_url?: string;
                width?: number;
                height?: number;
                format?: string;
              },
              i: number
            ) => {
              const url = img.secure_url || img.url || "";
              return (
                <Card
                  key={img.public_id || i}
                  className="group overflow-hidden cursor-pointer hover:border-primary/50 transition-colors"
                >
                  <div className="aspect-video relative overflow-hidden bg-muted">
                    <img
                      src={url}
                      alt={img.public_id || "Image"}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                      <Button
                        size="sm"
                        variant="secondary"
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={() => handleCopy(url)}
                      >
                        {copiedUrl === url ? (
                          <>
                            <Check className="h-3 w-3 mr-1" />
                            Copie!
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3 mr-1" />
                            Copier URL
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                  <CardContent className="p-2">
                    <p className="text-xs text-muted-foreground truncate">
                      {img.public_id || url.split("/").pop()}
                    </p>
                    {img.width && img.height && (
                      <p className="text-xs text-muted-foreground">
                        {img.width}x{img.height} {img.format || ""}
                      </p>
                    )}
                  </CardContent>
                </Card>
              );
            }
          )}
        </div>
      )}
    </div>
  );
}
