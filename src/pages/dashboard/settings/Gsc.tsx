import { Search, BarChart3, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSettings } from "./useSettings";

export default function Gsc() {
  const {
    siteId,
    domain,
    gscPropertyUrl, setGscPropertyUrl,
    gscConnecting,
    handleConnectGsc,
  } = useSettings();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Search className="h-5 w-5" />
          Google Search Console
        </CardTitle>
        <CardDescription>
          URL exacte de ta property GSC (avec le slash final). Étape requise
          avant de pouvoir voir les positions réelles de tes articles.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="space-y-1">
          <Label className="text-sm">Property URL</Label>
          <Input
            value={gscPropertyUrl}
            onChange={(e) => setGscPropertyUrl(e.target.value)}
            placeholder="https://tonsite.com/  ou  sc-domain:tonsite.com"
            type="text"
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground break-words">
            Deux formats supportés :
            <br />
            - <strong>URL prefix</strong> (couvre exactement un sous-domaine + protocole) :{" "}
            <code className="text-foreground">https://tonsite.com/</code> (slash final)
            <br />
            - <strong>Domain</strong> (couvre tous les sous-domaines + http/https) :{" "}
            <code className="text-foreground">sc-domain:tonsite.com</code>
            <br />
            Copie-colle l&apos;URL exacte affichée dans Search Console.
          </p>
        </div>

        <Button
          type="button"
          variant="outline"
          onClick={handleConnectGsc}
          disabled={gscConnecting || !siteId}
        >
          {gscConnecting ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : (
            <BarChart3 className="h-4 w-4 mr-2" />
          )}
          Connecter Google Search Console
        </Button>

        <div className="rounded-md border border-border/50 bg-muted/30 p-3 text-xs space-y-2">
          <p className="font-semibold">Étapes une-fois :</p>
          <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
            <li>
              <a
                href="https://search.google.com/search-console/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
              >
                search.google.com/search-console
              </a>{" "}
              -&gt; Add property -&gt; URL prefix -&gt; <code className="break-all">https://{domain || "tonsite.com"}/</code>
            </li>
            <li>Verify ownership (DNS TXT, balise HTML ou Google Analytics)</li>
            <li>Copie l&apos;URL exacte ci-dessus, sauvegarde, puis clique &laquo; Connecter Google Search Console &raquo; pour le OAuth.</li>
          </ol>
        </div>
      </CardContent>
    </Card>
  );
}
