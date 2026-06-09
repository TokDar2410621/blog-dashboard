import { Rocket } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSettings } from "./useSettings";

export default function Cta() {
  const {
    primaryCtaText, setPrimaryCtaText,
    primaryCtaUrl, setPrimaryCtaUrl,
  } = useSettings();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Rocket className="h-5 w-5" />
          Call-to-action principal
        </CardTitle>
        <CardDescription>
          Phrase d'appel à l'action injectée à la conclusion de chaque
          article généré. Laisse vide pour désactiver. Le générateur
          utilise le texte + l'URL exacts que tu définis ici.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label className="text-sm">Texte du CTA</Label>
          <Input
            value={primaryCtaText}
            onChange={(e) => setPrimaryCtaText(e.target.value)}
            placeholder="Ex: Réserve ta consultation gratuite"
            maxLength={200}
          />
          <p className="text-xs text-muted-foreground">
            Devient le texte d'ancre du lien dans la conclusion. {primaryCtaText.length}/200.
          </p>
        </div>
        <div className="space-y-2">
          <Label className="text-sm">URL du CTA</Label>
          <Input
            value={primaryCtaUrl}
            onChange={(e) => setPrimaryCtaUrl(e.target.value)}
            placeholder="https://tonsite.com/contact"
            type="url"
          />
          <p className="text-xs text-muted-foreground">
            Destination du lien (page de contact, formulaire, page produit).
            Les deux champs doivent être remplis pour que le CTA soit injecté.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
