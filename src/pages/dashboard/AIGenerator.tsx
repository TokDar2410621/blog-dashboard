import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useGenerateArticle } from "@/hooks/useDashboard";
import { MarkdownPreview } from "@/components/MarkdownPreview";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Sparkles, Loader2, Send, Pencil, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function AIGenerator() {
  const navigate = useNavigate();
  const generateArticle = useGenerateArticle();

  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [searchMethod, setSearchMethod] = useState("serper");
  const [articleType, setArticleType] = useState("news");
  const [length, setLength] = useState("medium");
  const [keywords, setKeywords] = useState("");
  const [dryRun, setDryRun] = useState(false);

  const [result, setResult] = useState<{
    output: string;
    post_count: number;
  } | null>(null);

  const handleGenerate = async () => {
    const params: Record<string, unknown> = {
      search: searchMethod,
      type: articleType,
      length,
      dry_run: dryRun,
    };
    if (topic) params.topic = topic;
    if (title) params.title = title;
    if (keywords) params.keywords = keywords;

    try {
      const data = await generateArticle.mutateAsync(params);
      setResult(data);
      toast.success(
        dryRun ? "Apercu genere!" : "Article genere et publie!"
      );
    } catch {
      toast.error("Erreur lors de la generation");
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Generer un article</h1>
        <p className="text-muted-foreground">
          Utilisez l'IA pour generer automatiquement un article de blog
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Parametres</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Sujet (optionnel)</Label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Ex: Les tendances IA en 2026"
              />
              <p className="text-xs text-muted-foreground">
                Laissez vide pour un sujet auto-selectionne
              </p>
            </div>

            <div className="space-y-2">
              <Label>Titre force (optionnel)</Label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ex: Mon titre exact"
              />
            </div>

            <div className="space-y-2">
              <Label>Methode de recherche</Label>
              <Select value={searchMethod} onValueChange={setSearchMethod}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="serper">Serper</SelectItem>
                  <SelectItem value="gemini">Gemini</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Type d'article</Label>
              <Select value={articleType} onValueChange={setArticleType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="news">Actualite / Opinion</SelectItem>
                  <SelectItem value="tutorial">Tutoriel</SelectItem>
                  <SelectItem value="comparison">Comparaison</SelectItem>
                  <SelectItem value="guide">Guide</SelectItem>
                  <SelectItem value="review">Review</SelectItem>
                  <SelectItem value="story">Recit personnel</SelectItem>
                  <SelectItem value="local">Annuaire local</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Longueur</Label>
              <Select value={length} onValueChange={setLength}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="short">Court (800-1200 mots)</SelectItem>
                  <SelectItem value="medium">
                    Moyen (1500-2000 mots)
                  </SelectItem>
                  <SelectItem value="long">Long (2500-3500 mots)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Mots-cles SEO (optionnel)</Label>
              <Input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="mot-cle1, mot-cle2, ..."
              />
            </div>

            <div className="flex items-center gap-3">
              <Switch checked={dryRun} onCheckedChange={setDryRun} />
              <Label>Apercu seulement (ne pas publier)</Label>
            </div>

            <Button
              className="w-full"
              size="lg"
              onClick={handleGenerate}
              disabled={generateArticle.isPending}
            >
              {generateArticle.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generation en cours...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generer
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Result */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Resultat</CardTitle>
          </CardHeader>
          <CardContent>
            {generateArticle.isPending ? (
              <div className="flex flex-col items-center justify-center py-12 gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-muted-foreground text-sm">
                  Generation en cours... Cela peut prendre 1-2 minutes
                </p>
              </div>
            ) : result ? (
              <div className="space-y-4">
                <div className="bg-muted/50 rounded-md p-4 max-h-96 overflow-y-auto">
                  <pre className="text-xs whitespace-pre-wrap font-mono">
                    {result.output}
                  </pre>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => navigate("/dashboard/articles")}
                  >
                    <Pencil className="h-4 w-4 mr-2" />
                    Voir les articles
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setResult(null);
                    }}
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Generer un autre
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>Le resultat de la generation apparaitra ici</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
